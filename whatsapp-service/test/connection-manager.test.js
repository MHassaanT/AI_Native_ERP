const test = require('node:test');
const assert = require('node:assert/strict');

const { getDirectMessageTarget } = require('../src/connection-manager');

test('accepts direct messages addressed with a WhatsApp phone JID', () => {
  const message = { key: { remoteJid: '15551234567@s.whatsapp.net' } };
  assert.deepEqual(getDirectMessageTarget(message), {
    phone: '15551234567',
    jid: '15551234567@s.whatsapp.net',
  });
});

test('accepts LID direct messages when WhatsApp supplies the phone JID alias', () => {
  const message = {
    key: {
      remoteJid: '123456789012345@lid',
      remoteJidAlt: '15551234567@s.whatsapp.net',
    },
  };
  assert.deepEqual(getDirectMessageTarget(message), {
    phone: '15551234567',
    jid: '123456789012345@lid',
  });
});

test('ignores group, unresolved LID, and malformed phone addresses', () => {
  assert.equal(
    getDirectMessageTarget({ key: { remoteJid: '123@g.us' } }),
    null,
  );
  assert.equal(
    getDirectMessageTarget({ key: { remoteJid: '123456789012345@lid' } }),
    null,
  );
  assert.equal(
    getDirectMessageTarget({ key: { remoteJid: '123@s.whatsapp.net' } }),
    null,
  );
});
