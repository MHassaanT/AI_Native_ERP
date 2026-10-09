const QRCode = require('qrcode');
const baileys = require('@whiskeysockets/baileys');
const { encrypt, decrypt } = require('./crypto');

const makeWASocket = baileys.default || baileys;
const { Browsers, DisconnectReason, initAuthCreds, proto } = baileys;

function getDirectMessageTarget(message) {
  const remoteJid = message?.key?.remoteJid || '';
  const remoteJidAlt = message?.key?.remoteJidAlt || '';
  const phoneJid = remoteJid.endsWith('@s.whatsapp.net')
    ? remoteJid
    : remoteJid.endsWith('@lid') && remoteJidAlt.endsWith('@s.whatsapp.net')
      ? remoteJidAlt
      : '';
  const phone = phoneJid.slice(0, -'@s.whatsapp.net'.length);
  if (!/^\d{7,15}$/.test(phone)) return null;
  return { phone, jid: remoteJid };
}

class ConnectionManager {
  constructor({ pool, erpUrl, internalToken, logger = console }) {
    this.pool = pool;
    this.erpUrl = erpUrl.replace(/\/$/, '');
    this.internalToken = internalToken;
    this.logger = logger;
    this.sessions = new Map();
    this.stopping = false;
  }

  async erpRequest(path, body) {
    const response = await fetch(`${this.erpUrl}/api/v1/internal/whatsapp${path}`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-internal-token': this.internalToken,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) {
      throw new Error(`ERP WhatsApp endpoint returned HTTP ${response.status}.`);
    }
    return response.json();
  }

  async updateStatus(tenantId, status, extra = {}) {
    await this.erpRequest('/connection-status', {
      tenant_id: tenantId,
      status,
      phone_number: extra.phoneNumber || null,
      last_error: extra.error || null,
    });
  }

  async loadAuthState(tenantId) {
    const result = await this.pool.query(
      `SELECT record_type, record_id, encrypted_value
       FROM whatsapp_auth_records WHERE tenant_id = $1`,
      [tenantId],
    );
    const records = new Map(
      result.rows.map((row) => [`${row.record_type}:${row.record_id}`, decrypt(row.encrypted_value)]),
    );
    const creds = records.get('creds:main') || initAuthCreds();
    const keys = {
      get: async (type, ids) => {
        const found = {};
        for (const id of ids) {
          let value = records.get(`${type}:${id}`);
          if (type === 'app-state-sync-key' && value) {
            value = proto.Message.AppStateSyncKeyData.fromObject(value);
          }
          found[id] = value || null;
        }
        return found;
      },
      set: async (data) => {
        const client = await this.pool.connect();
        try {
          await client.query('BEGIN');
          for (const [type, entries] of Object.entries(data)) {
            for (const [id, value] of Object.entries(entries)) {
              if (value == null) {
                await client.query(
                  `DELETE FROM whatsapp_auth_records
                   WHERE tenant_id = $1 AND record_type = $2 AND record_id = $3`,
                  [tenantId, type, String(id)],
                );
                records.delete(`${type}:${id}`);
              } else {
                const encrypted = encrypt(value);
                await client.query(
                  `INSERT INTO whatsapp_auth_records (tenant_id, record_type, record_id, encrypted_value)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (tenant_id, record_type, record_id)
                   DO UPDATE SET encrypted_value = EXCLUDED.encrypted_value, updated_at = clock_timestamp()`,
                  [tenantId, type, String(id), encrypted],
                );
                records.set(`${type}:${id}`, value);
              }
            }
          }
          await client.query('COMMIT');
        } catch (error) {
          await client.query('ROLLBACK');
          throw error;
        } finally {
          client.release();
        }
      },
    };
    return {
      state: { creds, keys },
      saveCreds: async () => {
        const encrypted = encrypt(creds);
        await this.pool.query(
          `INSERT INTO whatsapp_auth_records (tenant_id, record_type, record_id, encrypted_value)
           VALUES ($1, 'creds', 'main', $2)
           ON CONFLICT (tenant_id, record_type, record_id)
           DO UPDATE SET encrypted_value = EXCLUDED.encrypted_value, updated_at = clock_timestamp()`,
          [tenantId, encrypted],
        );
      },
    };
  }

  async connectTenant(tenantId, forceNew = false) {
    if (!tenantId) throw new Error('tenantId is required.');
    const current = this.sessions.get(tenantId);
    if (current?.socket && !forceNew) {
      return {
        status: current.status,
        qr: current.qr,
        phone_number: current.phoneNumber,
      };
    }
    if (current?.socket) current.socket.end(undefined);
    this.sessions.delete(tenantId);
    if (forceNew) {
      await this.pool.query('DELETE FROM whatsapp_auth_records WHERE tenant_id = $1', [tenantId]);
    }
    await this.updateStatus(tenantId, 'CONNECTING');
    let state;
    let saveCreds;
    try {
      ({ state, saveCreds } = await this.loadAuthState(tenantId));
    } catch (error) {
      await this.updateStatus(tenantId, 'ERROR', { error: 'Could not restore encrypted WhatsApp credentials.' });
      throw error;
    }
    const session = { socket: null, status: 'CONNECTING', qr: null, phoneNumber: null, retry: 0 };
    this.sessions.set(tenantId, session);

    const socket = makeWASocket({
      auth: state,
      logger: { level: 'silent', child() { return this; }, trace() {}, debug() {}, info() {}, warn() {}, error() {} },
      browser: Browsers.macOS('Chrome'),
      syncFullHistory: false,
      printQRInTerminal: false,
    });
    session.socket = socket;
    socket.ev.on('creds.update', () => saveCreds().catch((error) => {
      this.logger.error('Baileys credentials save failed:', error.message);
    }));
    socket.ev.on('connection.update', (update) => {
      this.handleConnectionUpdate(tenantId, session, update).catch((error) => {
        this.logger.error(`Baileys connection event failed for ${tenantId}:`, error.message);
      });
    });
    socket.ev.on('messages.upsert', (event) => {
      this.handleMessages(tenantId, session, event).catch((error) => {
        this.logger.error(`WhatsApp inbound handling failed for ${tenantId}:`, error.message);
      });
    });
    return { status: session.status, qr: session.qr, phone_number: null };
  }

  async handleConnectionUpdate(tenantId, session, update) {
    if (update.qr) {
      session.qr = await QRCode.toDataURL(update.qr, { width: 320, margin: 2 });
      session.status = 'QR_PENDING';
      await this.updateStatus(tenantId, 'QR_PENDING');
    }
    if (update.connection === 'open') {
      session.status = 'CONNECTED';
      session.qr = null;
      session.retry = 0;
      session.phoneNumber = session.socket.user?.id?.split(':')[0]?.split('@')[0] || null;
      await this.updateStatus(tenantId, 'CONNECTED', { phoneNumber: session.phoneNumber });
    }
    if (update.connection !== 'close') return;

    const code = update.lastDisconnect?.error?.output?.statusCode;
    session.socket = null;
    if (code === DisconnectReason.loggedOut) {
      session.status = 'DISCONNECTED';
      this.sessions.delete(tenantId);
      await this.pool.query('DELETE FROM whatsapp_auth_records WHERE tenant_id = $1', [tenantId]);
      await this.updateStatus(tenantId, 'DISCONNECTED');
      return;
    }
    if (this.stopping || session.retry >= 5) {
      session.status = 'ERROR';
      await this.updateStatus(tenantId, 'ERROR', { error: 'Connection closed; reconnect required.' });
      return;
    }
    const delay = Math.min(1000 * 2 ** session.retry, 30000);
    session.retry += 1;
    session.status = 'CONNECTING';
    await this.updateStatus(tenantId, 'CONNECTING');
    setTimeout(() => this.connectTenant(tenantId).catch((error) => {
      this.logger.error(`Baileys reconnect failed for ${tenantId}:`, error.message);
    }), delay).unref();
  }

  async handleMessages(tenantId, session, event) {
    if (event.type !== 'notify') return;
    for (const message of event.messages || []) {
      if (message.key.fromMe) continue;
      const target = getDirectMessageTarget(message);
      if (!target) {
        const addressType = (message.key.remoteJid || '').split('@').pop() || 'unknown';
        this.logger.warn(`Ignoring WhatsApp message with unsupported address type: ${addressType}.`);
        continue;
      }
      const { phone, jid } = target;
      const body = message.message || {};
      const text = body.conversation
        || body.extendedTextMessage?.text
        || body.imageMessage?.caption
        || body.documentMessage?.caption
        || body.videoMessage?.caption;
      if (!text || !message.key.id) continue;
      let result;
      try {
        this.logger.info(`Processing inbound WhatsApp message for tenant ${tenantId}.`);
        result = await this.erpRequest('/inbound', {
          tenant_id: tenantId,
          provider_message_id: message.key.id,
          phone_number: phone,
          text: String(text).slice(0, 8000),
          contact_name: message.pushName || null,
        });
      } catch (error) {
        this.logger.error(`ERP could not process WhatsApp message for ${tenantId}:`, error.message);
        try {
          await session.socket.sendMessage(jid, {
            text: 'We received your WhatsApp message, but support is temporarily unavailable. Please try again shortly.',
          });
        } catch (sendError) {
          this.logger.error(`Could not send WhatsApp service notice for ${tenantId}:`, sendError.message);
        }
        continue;
      }
      if (!result.should_send || !result.answer || !result.message_id) continue;
      try {
        const sent = await session.socket.sendMessage(jid, { text: result.answer });
        await this.erpRequest('/delivery', {
          tenant_id: tenantId,
          message_id: result.message_id,
          status: 'SENT',
          provider_message_id: sent?.key?.id || null,
        });
      } catch (error) {
        await this.erpRequest('/delivery', {
          tenant_id: tenantId,
          message_id: result.message_id,
          status: 'FAILED',
          error: error.message,
        });
        throw error;
      }
    }
  }

  async status(tenantId) {
    const session = this.sessions.get(tenantId);
    return {
      status: session?.status || 'DISCONNECTED',
      qr: session?.qr || null,
      phone_number: session?.phoneNumber || null,
    };
  }

  async sendMessage(tenantId, to, message) {
    const session = this.sessions.get(tenantId);
    if (!session?.socket || session.status !== 'CONNECTED') {
      throw new Error('WhatsApp tenant is not connected.');
    }
    const digits = String(to).replace(/\D/g, '');
    if (digits.length < 7 || digits.length > 15 || !message) {
      throw new Error('Valid recipient phone number and message are required.');
    }
    const result = await session.socket.sendMessage(`${digits}@s.whatsapp.net`, { text: message });
    return { message_id: result?.key?.id || null };
  }

  async disconnectTenant(tenantId) {
    const session = this.sessions.get(tenantId);
    if (session?.socket) {
      session.socket.ev.removeAllListeners();
      await session.socket.logout().catch(() => {});
      session.socket.end(undefined);
    }
    this.sessions.delete(tenantId);
    await this.pool.query('DELETE FROM whatsapp_auth_records WHERE tenant_id = $1', [tenantId]);
    await this.updateStatus(tenantId, 'DISCONNECTED');
    return { status: 'DISCONNECTED' };
  }

  async start() {
    if (!process.env.WHATSAPP_ENCRYPTION_KEY) throw new Error('WHATSAPP_ENCRYPTION_KEY is required.');
    const result = await this.pool.query(
      `SELECT tenant_id FROM whatsapp_connections
       WHERE status IN ('CONNECTED', 'CONNECTING', 'QR_PENDING')`,
    );
    for (const row of result.rows) {
      this.connectTenant(row.tenant_id).catch((error) => {
        this.logger.error(`Baileys startup restore failed for ${row.tenant_id}:`, error.message);
      });
    }
  }

  async stop() {
    this.stopping = true;
    for (const [tenantId, session] of this.sessions) {
      session.socket?.end(undefined);
      await this.updateStatus(tenantId, 'DISCONNECTED');
    }
    this.sessions.clear();
  }
}

module.exports = { ConnectionManager, getDirectMessageTarget };
