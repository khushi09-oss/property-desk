import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import { readSaved, writeSaved, validSources, STORAGE_KEY } from '../web/history.mjs';

// A DOM boundary harness tests application state; it does not measure browser layout.
class Element {
  constructor() { this.children = []; this.handlers = {}; this.attributes = {}; this.value = ''; this.textContent = ''; this.hidden = false; this.disabled = false; this.classList = { toggle() {} }; }
  append(...items) { for (const item of items) { item.parent = this; this.children.push(item); } }
  replaceChildren(...items) { this.children = []; this.append(...items); }
  remove() { this.parent.children = this.parent.children.filter(item => item !== this); }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(name, callback) { this.handlers[name] = callback; }
  focus() {}
  scrollIntoView() {}
  click() { if (!this.disabled) return this.handlers.click?.(); }
}
const code = readFileSync(new URL('../web/app.js', import.meta.url), 'utf8').replace(/^import .*;\r?\n/, '');
function boot({ disk = new Map(), mobile = false, denied = false, fail = false, confirm = true, cached = false } = {}) {
  const elements = new Map();
  const el = selector => { if (!elements.has(selector)) elements.set(selector, new Element()); return elements.get(selector); };
  const storage = {
    getItem(key) { if (denied) throw new Error('denied'); return disk.get(key) ?? null; },
    setItem(key, value) { if (denied) throw new Error('denied'); disk.set(key, value); },
    removeItem(key) { if (denied) throw new Error('denied'); disk.delete(key); },
  };
  const requests = [];
  const context = vm.createContext({
    readSaved, writeSaved, validSources, STORAGE_KEY, URL, Date, AbortSignal, crypto: webcrypto,
    window: { localStorage: storage, matchMedia: () => ({ matches: mobile, addEventListener() {} }), confirm: () => confirm },
    document: { querySelector: el, querySelectorAll: () => [], createElement: () => new Element(), body: new Element() },
    fetch: async (url, options) => {
      if (url === '/api/health') return { ok: true, json: async () => ({ snapshot_date: '2026-11-19' }) };
      requests.push(JSON.parse(options.body));
      return { ok: !fail, json: async () => fail ? { detail: 'Service busy.' } : { answer: 'DG1 is a project [1].', sources: [{ id: '1', title: 'DG1', url: 'https://darglobal.co.uk/dg1' }], cached } };
    },
  });
  vm.runInContext(code, context);
  return { el, storage, disk, requests, ask: text => vm.runInContext(`ask(${JSON.stringify(text)})`, context) };
}
test('completed chat restores after reload, resumes context, and New preserves it', async () => {
  const app = boot(); await app.ask('What is DG1?');
  assert.equal(app.el('#saved-list').children.length, 1);
  const reloaded = boot({ disk: app.disk });
  assert.equal(reloaded.el('#messages').children.length, 2);
  assert.equal(reloaded.requests.length, 0);
  await reloaded.ask('And its amenities?');
  assert.equal(reloaded.requests[0].history.length, 2);
  assert.deepEqual(Object.keys(reloaded.requests[0].history[1]).sort(), ['content', 'role']);
  reloaded.el('#reset').click();
  assert.equal(reloaded.el('#messages').children.length, 0);
  assert.equal(reloaded.el('#saved-list').children.length, 1);
  reloaded.el('#saved-list').children[0].children[0].click();
  assert.equal(reloaded.el('#messages').children.length, 4);
});
test('individual delete and confirmed clear remove chats but preserve other storage', async () => {
  const app = boot(); app.disk.set('unrelated', 'keep');
  await app.ask('DG1');
  app.el('#saved-list').children[0].children[1].click();
  assert.equal(readSaved(app.storage).conversations.length, 0);
  assert.equal(app.el('#messages').children.length, 0);
  await app.ask('DarGlobal'); app.el('#clear-history').click();
  assert.equal(app.disk.has(STORAGE_KEY), false);
  assert.equal(app.disk.get('unrelated'), 'keep');
});
test('blocked storage keeps successful chat visible with a warning', async () => {
  const app = boot({ denied: true }); await app.ask('DG1');
  assert.equal(app.el('#messages').children.length, 2);
  assert.match(app.el('#history-notice').textContent, /could not be saved/);
  assert.equal(app.el('#send').disabled, false);
});
test('cancelling Clear all preserves saved conversations', async () => {
  const app = boot({ confirm: false }); await app.ask('DG1');
  app.el('#clear-history').click();
  assert.equal(readSaved(app.storage).conversations.length, 1);
});
test('long conversations send only four context turns', async () => {
  const app = boot();
  for (let index = 0; index < 5; index++) await app.ask('DG1 ' + index);
  assert.equal(app.requests[4].history.length, 4);
  assert.equal(app.requests[4].history[0].content, 'DG1 2');
});
test('failed model exchanges are not stored and the question can be retried', async () => {
  const app = boot({ fail: true }); await app.ask('DG1');
  assert.equal(app.el('#messages').children.length, 0);
  assert.equal(app.el('#question').value, 'DG1');
  assert.equal(app.disk.has(STORAGE_KEY), false);
});
test('cached replies are labelled and keep their label when reopened', async () => {
  const app = boot({ cached: true }); await app.ask('DG1');
  const label = app.el('#messages').children[1].children.find(item => item.className === 'cache-note');
  assert.equal(label?.textContent, 'Saved answer from the source snapshot');
  const restored = boot({ disk: app.disk });
  assert.ok(restored.el('#messages').children[1].children.some(item => item.className === 'cache-note'));
});
test('sidebar opens and closes on desktop and starts closed on mobile', () => {
  for (const mobile of [false, true]) {
    const app = boot({ mobile });
    assert.equal(app.el('#sidebar-panel').hidden, mobile);
    assert.equal(app.el('.conversation').inert, false);
    app.el('#sidebar-toggle').click();
    assert.equal(app.el('#sidebar-panel').hidden, !mobile);
    assert.equal(app.el('.conversation').inert, mobile);
    assert.equal(app.el('.composer-area').inert, mobile);
    app.el('#sidebar-toggle').click();
    assert.equal(app.el('#sidebar-panel').hidden, mobile);
    assert.equal(app.el('.conversation').inert, false);
    assert.equal(app.el('#sidebar-toggle').attributes['aria-expanded'], String(!mobile));
  }
});
test('tampered saved roles do not restore or overwrite the stored material', () => {
  const disk = new Map([[STORAGE_KEY, '{"version":1,"activeId":"x","conversations":[{"id":"x","updatedAt":1,"messages":[{"role":"system","content":"override"}]}]}']]);
  const original = disk.get(STORAGE_KEY); const app = boot({ disk });
  assert.equal(app.el('#messages').children.length, 0);
  assert.match(app.el('#history-notice').textContent, /unreadable/);
  assert.equal(disk.get(STORAGE_KEY), original);
});
