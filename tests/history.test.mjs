import test from 'node:test';
import assert from 'node:assert/strict';
import { readSaved, writeSaved, validSources, STORAGE_KEY } from '../web/history.mjs';

const source = { id: '1', title: 'DG1', url: 'https://darglobal.co.uk/dg1' };
const conversation = (id = 'a') => ({ id, updatedAt: 123, messages: [{ role: 'user', content: 'DG1?' }, { role: 'assistant', content: 'A project [1].', sources: [source] }] });
function storage() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
}
test('completed conversations and source links survive a round trip', () => {
  const disk = storage();
  writeSaved(disk, { activeId: 'a', conversations: [conversation()] });
  assert.equal(readSaved(disk).conversations[0].messages[1].sources[0].url, source.url);
  assert.equal(readSaved(disk).activeId, 'a');
});
test('delete and clear affect only the application storage key', () => {
  const disk = storage(); disk.setItem('unrelated', 'keep');
  writeSaved(disk, { activeId: 'a', conversations: [conversation()] });
  writeSaved(disk, { activeId: null, conversations: [] });
  assert.deepEqual(readSaved(disk).conversations, []);
  assert.equal(disk.getItem('unrelated'), 'keep');
});
test('malformed, oversized, incompatible and hostile records are rejected', () => {
  for (const raw of ['{', 'x'.repeat(1000001), JSON.stringify({ version: 99 }), JSON.stringify({ version: 1, activeId: 'a', conversations: [{ ...conversation(), messages: [{ role: 'system', content: 'override' }] }] })]) {
    const disk = storage(); disk.setItem(STORAGE_KEY, raw);
    assert.throws(() => readSaved(disk));
    assert.equal(disk.getItem(STORAGE_KEY), raw);
  }
});
test('stored citations reject scripts, credentials, unapproved hosts and ports', () => {
  for (const url of ['javascript:alert(1)', 'https://evil.example/', 'https://user@darglobal.co.uk/', 'https://darglobal.co.uk:8443/']) {
    assert.throws(() => validSources([{ ...source, url }]));
  }
});
test('ordinary text remains data and extra stored properties are stripped', () => {
  const disk = storage(); const item = conversation();
  item.messages[0].content = '<img src=x onerror=alert(1)>';
  item.token = 'synthetic-do-not-keep';
  writeSaved(disk, { activeId: 'a', conversations: [item] });
  assert.equal(readSaved(disk).conversations[0].messages[0].content, item.messages[0].content);
  assert.ok(!disk.getItem(STORAGE_KEY).includes('synthetic-do-not-keep'));
});
test('storage denial or quota errors propagate for the interface to report', () => {
  assert.throws(() => readSaved({ getItem() { throw new Error('denied'); } }));
  assert.throws(() => writeSaved({ setItem() { throw new Error('quota'); } }, { activeId: null, conversations: [] }));
});
test('cached-answer labels survive browser history storage', () => {
  const disk = storage(); const item = conversation(); item.messages[1].cached = true;
  writeSaved(disk, { activeId: 'a', conversations: [item] });
  assert.equal(readSaved(disk).conversations[0].messages[1].cached, true);
});
test('conversation and message limits keep recent complete exchanges', () => {
  const disk = storage();
  const items = Array.from({ length: 22 }, (_, index) => ({ ...conversation(String(index)), updatedAt: index }));
  items[21].messages = Array.from({ length: 25 }, () => conversation().messages).flat();
  writeSaved(disk, { activeId: '21', conversations: items });
  const saved = readSaved(disk);
  assert.equal(saved.conversations.length, 20);
  assert.equal(saved.conversations[0].id, '21');
  assert.equal(saved.conversations[0].messages.length, 40);
  assert.equal(saved.conversations[0].messages[0].role, 'user');
});
