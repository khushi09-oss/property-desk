export const STORAGE_KEY = 'property-desk.history.v1';
const MAX_BYTES = 1000000;
const officialHosts = new Set(['darglobal.co.uk', 'www.darglobal.co.uk', 'wasalt.sa']);

function text(value, maximum) {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum) throw new Error('Invalid saved text.');
  return value;
}

export function validSources(sources) {
  if (!Array.isArray(sources) || sources.length > 8) throw new Error('Invalid source list.');
  return sources.map(source => {
    const url = new URL(text(source.url, 2048));
    if (url.protocol !== 'https:' || !officialHosts.has(url.hostname) || url.username || url.password || url.port) throw new Error('Invalid source link.');
    return { id: text(source.id, 8), title: text(source.title, 500), url: url.href };
  });
}

function cleanConversation(item) {
  if (!Array.isArray(item.messages) || !item.messages.length || item.messages.length % 2) throw new Error('Incomplete conversation.');
  if (!Number.isSafeInteger(item.updatedAt) || item.updatedAt < 0) throw new Error('Invalid saved date.');
  const messages = item.messages.slice(-40).map((turn, index) => {
    const role = index % 2 === 0 ? 'user' : 'assistant';
    if (turn.role !== role) throw new Error('Invalid saved role.');
    return {
      role,
      content: text(turn.content, role === 'user' ? 1200 : 12000),
      ...(role === 'assistant' ? { sources: validSources(turn.sources), cached: turn.cached === true } : {}),
    };
  });
  return { id: text(item.id, 100), title: text(item.title ?? messages[0].content, 1200).slice(0, 80), updatedAt: item.updatedAt, messages };
}

function cleanState(state) {
  if (!Array.isArray(state.conversations)) throw new Error('Invalid saved conversations.');
  const conversations = state.conversations.map(cleanConversation).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 20);
  if (new Set(conversations.map(item => item.id)).size !== conversations.length) throw new Error('Duplicate saved conversations.');
  const activeId = state.activeId;
  if (activeId !== null && !conversations.some(item => item.id === activeId)) throw new Error('Invalid active conversation.');
  return { version: 1, activeId, conversations };
}

export function readSaved(storage) {
  const raw = storage.getItem(STORAGE_KEY);
  if (raw === null) return { version: 1, activeId: null, conversations: [] };
  if (raw.length > MAX_BYTES || new TextEncoder().encode(raw).length > MAX_BYTES) throw new Error('Saved history is too large.');
  const parsed = JSON.parse(raw);
  if (parsed?.version !== 1) throw new Error('Unsupported saved history.');
  return cleanState(parsed);
}

export function writeSaved(storage, state) {
  const clean = cleanState(state);
  const raw = JSON.stringify(clean);
  if (new TextEncoder().encode(raw).length > MAX_BYTES) throw new Error('History storage limit reached.');
  storage.setItem(STORAGE_KEY, raw);
  return clean;
}
