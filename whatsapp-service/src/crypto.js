const crypto = require('node:crypto');
const { BufferJSON } = require('@whiskeysockets/baileys');

function encryptionKey() {
  const value = process.env.WHATSAPP_ENCRYPTION_KEY;
  if (!value || !/^[a-fA-F0-9]{64}$/.test(value)) {
    throw new Error('WHATSAPP_ENCRYPTION_KEY must be a 32-byte key encoded as 64 hex characters.');
  }
  return Buffer.from(value, 'hex');
}

function encrypt(value) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', encryptionKey(), iv);
  const plaintext = Buffer.from(JSON.stringify(value, BufferJSON.replacer), 'utf8');
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  return `${iv.toString('hex')}:${cipher.getAuthTag().toString('hex')}:${ciphertext.toString('hex')}`;
}

function decrypt(value) {
  const parts = String(value).split(':');
  if (parts.length !== 3) throw new Error('Invalid encrypted WhatsApp auth record.');
  const decipher = crypto.createDecipheriv('aes-256-gcm', encryptionKey(), Buffer.from(parts[0], 'hex'));
  decipher.setAuthTag(Buffer.from(parts[1], 'hex'));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(parts[2], 'hex')),
    decipher.final(),
  ]).toString('utf8');
  return JSON.parse(plaintext, BufferJSON.reviver);
}

module.exports = { encrypt, decrypt };
