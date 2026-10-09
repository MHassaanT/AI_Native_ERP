const test = require('node:test');
const assert = require('node:assert/strict');

process.env.WHATSAPP_ENCRYPTION_KEY = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';
const { encrypt, decrypt } = require('../src/crypto');

test('encrypted auth state round-trips without exposing plaintext', () => {
  const value = { token: 'whatsapp-session-secret', counter: 7 };
  const encrypted = encrypt(value);
  assert.equal(decrypt(encrypted).token, value.token);
  assert.equal(encrypted.includes(value.token), false);
});

test('auth state tampering fails closed', () => {
  const encrypted = encrypt({ value: 'secret' });
  const [iv, tag, body] = encrypted.split(':');
  const finalDigit = body.at(-1) === '0' ? '1' : '0';
  const altered = `${iv}:${tag}:${body.slice(0, -1)}${finalDigit}`;
  assert.throws(() => decrypt(altered));
});
