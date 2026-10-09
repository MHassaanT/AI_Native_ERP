const crypto = require('node:crypto');
const express = require('express');
const { Pool } = require('pg');
const { ConnectionManager } = require('./connection-manager');

const required = ['DATABASE_URL', 'ERP_INTERNAL_URL', 'WHATSAPP_INTERNAL_TOKEN', 'WHATSAPP_ENCRYPTION_KEY'];
for (const name of required) {
  if (!process.env[name]) throw new Error(`${name} is required.`);
}
if (!/^[a-fA-F0-9]{64}$/.test(process.env.WHATSAPP_ENCRYPTION_KEY)) {
  throw new Error('WHATSAPP_ENCRYPTION_KEY must be a 32-byte key encoded as 64 hex characters.');
}
if (process.env.WHATSAPP_INTERNAL_TOKEN.length < 32) {
  throw new Error('WHATSAPP_INTERNAL_TOKEN must contain at least 32 characters.');
}

const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const manager = new ConnectionManager({
  pool,
  erpUrl: process.env.ERP_INTERNAL_URL,
  internalToken: process.env.WHATSAPP_INTERNAL_TOKEN,
});
const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '32kb' }));

function authorize(req, res, next) {
  const supplied = req.get('x-internal-token') || '';
  const expected = process.env.WHATSAPP_INTERNAL_TOKEN;
  const suppliedBuffer = Buffer.from(supplied);
  const expectedBuffer = Buffer.from(expected);
  if (
    suppliedBuffer.length !== expectedBuffer.length
    || !crypto.timingSafeEqual(suppliedBuffer, expectedBuffer)
  ) {
    return res.status(401).json({ error: 'Unauthorized.' });
  }
  return next();
}

app.get('/health', async (_req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', active_sessions: manager.sessions.size });
  } catch {
    res.status(503).json({ status: 'database_unavailable' });
  }
});

app.use(authorize);
app.post('/tenants/:tenantId/connect', async (req, res, next) => {
  try {
    const result = await manager.connectTenant(req.params.tenantId, req.body?.force_new === true);
    res.json(result);
  } catch (error) {
    next(error);
  }
});
app.delete('/tenants/:tenantId/connect', async (req, res, next) => {
  try {
    res.json(await manager.disconnectTenant(req.params.tenantId));
  } catch (error) {
    next(error);
  }
});
app.get('/tenants/:tenantId/status', async (req, res) => {
  res.json(await manager.status(req.params.tenantId));
});
app.post('/tenants/:tenantId/send', async (req, res, next) => {
  try {
    res.json(await manager.sendMessage(req.params.tenantId, req.body?.to, req.body?.message));
  } catch (error) {
    next(error);
  }
});
app.use((error, _req, res, _next) => {
  console.error('[WhatsApp Service]', error.message);
  res.status(502).json({ error: 'WhatsApp operation failed.' });
});

const port = Number(process.env.PORT || process.env.WHATSAPP_PORT || 8100);
const server = app.listen(port, '0.0.0.0', async () => {
  try {
    await manager.start();
    console.log(`Baileys WhatsApp service listening on ${port}.`);
  } catch (error) {
    console.error('Could not start Baileys service:', error.message);
    server.close(() => process.exit(1));
  }
});

async function shutdown() {
  server.close();
  await manager.stop();
  await pool.end();
  process.exit(0);
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
