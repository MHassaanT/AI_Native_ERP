const test = require('node:test');
const assert = require('node:assert/strict');

const { getDirectMessageTarget, getRecipientJid } = require('../src/connection-manager');

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

test('routes LID direct messages when WhatsApp does not provide a phone alias', () => {
  assert.deepEqual(
    getDirectMessageTarget({ key: { remoteJid: '123456789012345@lid' } }),
    { phone: 'lid:123456789012345', jid: '123456789012345@lid' },
  );
});

test('ignores group and malformed direct-chat addresses', () => {
  assert.equal(
    getDirectMessageTarget({ key: { remoteJid: '123@g.us' } }),
    null,
  );
  assert.equal(
    getDirectMessageTarget({ key: { remoteJid: 'not-a-lid@lid' } }),
    null,
  );
  assert.equal(
    getDirectMessageTarget({ key: { remoteJid: '123@s.whatsapp.net' } }),
    null,
  );
});

test('sends replies to LID addresses without treating LIDs as phone numbers', () => {
  assert.equal(getRecipientJid('lid:123456789012345'), '123456789012345@lid');
  assert.equal(getRecipientJid('15551234567'), '15551234567@s.whatsapp.net');
  assert.throws(() => getRecipientJid('lid:not-numeric'));
});
