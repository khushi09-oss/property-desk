import { readSaved, writeSaved, validSources, STORAGE_KEY } from './history.mjs';

const form = document.querySelector('#composer');
const question = document.querySelector('#question');
const thread = document.querySelector('#messages');
const welcome = document.querySelector('#welcome');
const statusLine = document.querySelector('#status');
const errorLine = document.querySelector('#error');
const reset = document.querySelector('#reset');
const send = document.querySelector('#send');
const suggestions = [...document.querySelectorAll('.suggestion')];
const savedList = document.querySelector('#saved-list');
const historyNotice = document.querySelector('#history-notice');
const clearHistory = document.querySelector('#clear-history');
const sidebar = document.querySelector('#sidebar-panel');
const sidebarToggle = document.querySelector('#sidebar-toggle');
const mobileLayout = window.matchMedia('(max-width: 700px)');
let saved = { activeId: null, conversations: [] };
let currentId = null;
let history = [];
let busy = false;

function setSidebar(open) {
  sidebar.hidden = !open;
  document.body.classList.toggle('sidebar-closed', !open);
  sidebarToggle.setAttribute('aria-expanded', String(open));
  sidebarToggle.setAttribute('aria-label', open ? 'Hide sidebar' : 'Show sidebar');
  document.querySelector('.conversation').inert = mobileLayout.matches && open;
  document.querySelector('.composer-area').inert = mobileLayout.matches && open;
}
sidebarToggle.addEventListener('click', () => setSidebar(sidebar.hidden));
setSidebar(!mobileLayout.matches);
mobileLayout.addEventListener('change', () => setSidebar(!sidebar.hidden));

function renderSaved() {
  savedList.replaceChildren();
  for (const item of saved.conversations) {
    const row = document.createElement('li');
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'history-open';
    open.textContent = item.title;
    open.title = item.title;
    if (item.id === currentId) open.setAttribute('aria-current', 'true');
    open.disabled = busy;
    open.addEventListener('click', () => {
      if (busy) return;
      showConversation(item);
      persist(state => ({ ...state, activeId: state.conversations.some(chat => chat.id === item.id) ? item.id : null }));
      if (window.matchMedia('(max-width: 700px)').matches) setSidebar(false);
      question.focus();
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'history-delete';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `Delete conversation: ${item.title}`);
    remove.disabled = busy;
    remove.addEventListener('click', () => {
      if (busy) return;
      const deleted = persist(state => ({ ...state, activeId: state.activeId === item.id ? null : state.activeId, conversations: state.conversations.filter(chat => chat.id !== item.id) }));
      if (deleted && currentId === item.id) newConversation(false);
      renderSaved();
    });
    row.append(open, remove);
    savedList.append(row);
  }
  document.querySelector('#history-empty').hidden = saved.conversations.length > 0;
  clearHistory.disabled = busy || (!saved.conversations.length && !historyNotice.textContent);
}

function persist(change) {
  try {
    saved = writeSaved(window.localStorage, change(readSaved(window.localStorage)));
    historyNotice.textContent = '';
    renderSaved();
    return true;
  } catch {
    historyNotice.textContent = 'History could not be saved or changed. Browser storage may be blocked, full or unreadable. You can still chat in this tab.';
    renderSaved();
    return false;
  }
}

function showConversation(item) {
  currentId = item.id;
  history = item.messages;
  thread.replaceChildren();
  for (const turn of history) message(turn.role, turn.content, turn.sources || [], turn.cached === true);
  welcome.hidden = true;
  errorLine.hidden = true;
  statusLine.textContent = '';
  question.value = '';
  renderSaved();
}

function newConversation(updateStorage = true) {
  currentId = null;
  history = [];
  thread.replaceChildren();
  welcome.hidden = false;
  errorLine.hidden = true;
  statusLine.textContent = '';
  question.value = '';
  if (updateStorage) persist(state => ({ ...state, activeId: null }));
  renderSaved();
  question.focus();
}

clearHistory.addEventListener('click', () => {
  if (busy || !window.confirm('Delete all Property Desk conversations saved in this browser? This cannot be undone.')) return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
    saved = { activeId: null, conversations: [] };
    historyNotice.textContent = '';
    newConversation(false);
    if (mobileLayout.matches) setSidebar(false);
    question.focus();
  } catch {
    historyNotice.textContent = 'Saved history could not be cleared. Check your browser storage settings.';
  }
});

try {
  saved = readSaved(window.localStorage);
  const active = saved.conversations.find(item => item.id === saved.activeId);
  if (active) showConversation(active);
} catch {
  historyNotice.textContent = 'Saved history is unavailable or unreadable. It has not been changed. You can still chat, or use Clear all to remove it.';
}
renderSaved();

function message(role, text, sources = [], cached = false) {
  const section = document.createElement('article');
  section.className = `message ${role}`;
  const speaker = document.createElement('p');
  speaker.className = 'speaker';
  speaker.textContent = role === 'user' ? 'YOU' : 'PROPERTY DESK';
  const answer = document.createElement('p');
  answer.className = 'answer';
  answer.textContent = text.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/^\* /gm, '• ');
  section.append(speaker, answer);
  if (cached && role === 'assistant') {
    const note = document.createElement('p');
    note.className = 'cache-note';
    note.textContent = 'Saved answer from the source snapshot';
    section.append(note);
  }
  if (sources.length) {
    const list = document.createElement('div');
    list.className = 'sources';
    const title = document.createElement('p');
    title.textContent = 'CHECK THE ORIGINAL SOURCES';
    list.append(title);
    for (const source of validSources(sources)) {
      const url = new URL(source.url);
      const link = document.createElement('a');
      link.href = url.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = `[${source.id}] ${source.title} ↗`;
      list.append(link);
    }
    section.append(list);
  }
  thread.append(section);
  return section;
}

function setBusy(value) {
  busy = value;
  send.disabled = value;
  reset.disabled = value;
  question.disabled = value;
  suggestions.forEach(button => { button.disabled = value; });
  thread.setAttribute('aria-busy', String(value));
  renderSaved();
}

async function ask(text) {
  const trimmed = text.trim();
  if (busy || !trimmed) return;
  welcome.hidden = true;
  errorLine.hidden = true;
  const userMessage = message('user', trimmed);
  question.value = '';
  setBusy(true);
  statusLine.textContent = 'Looking through the collected sources…';
  statusLine.scrollIntoView({ block: 'nearest' });
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: trimmed, history: history.slice(-4).map(turn => ({ role: turn.role, content: turn.content.slice(0, 1800) })) }),
      signal: AbortSignal.timeout(45000),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Please check your question and try again.');
    if (typeof payload.answer !== 'string' || !Array.isArray(payload.sources)) throw new Error('The service returned an unexpected response.');
    if (!payload.answer.trim() || payload.answer.length > 12000) throw new Error('The service returned an unexpected answer.');
    const sources = validSources(payload.sources);
    const cached = payload.cached === true;
    const reply = message('assistant', payload.answer, sources, cached);
    const title = saved.conversations.find(item => item.id === currentId)?.title || history[0]?.content || trimmed;
    currentId ||= crypto.randomUUID();
    history = [...history, { role: 'user', content: trimmed }, { role: 'assistant', content: payload.answer, sources, cached }].slice(-40);
    const conversation = { id: currentId, title, updatedAt: Date.now(), messages: history };
    persist(state => ({ activeId: currentId, conversations: [conversation, ...state.conversations.filter(item => item.id !== currentId)] }));
    statusLine.textContent = '';
    reply.scrollIntoView({ block: 'start' });
  } catch (error) {
    userMessage.remove();
    question.value = trimmed;
    errorLine.textContent = error.name === 'TimeoutError' ? 'The request timed out and may still use quota. Retry only if needed.' : error.message;
    errorLine.hidden = false;
    statusLine.textContent = '';
  } finally {
    setBusy(false);
    question.focus({ preventScroll: true });
  }
}

form.addEventListener('submit', event => { event.preventDefault(); ask(question.value); });
question.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); form.requestSubmit(); }
});
suggestions.forEach(button => button.addEventListener('click', () => ask(button.dataset.question)));
reset.addEventListener('click', () => {
  if (busy) return;
  newConversation();
  if (mobileLayout.matches) setSidebar(false);
  question.focus();
});
fetch('/api/health').then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(data => {
  const date = new Date(`${data.snapshot_date}T12:00:00Z`);
  document.querySelector('#snapshot').textContent = `Sources collected · ${date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`;
}).catch(() => { document.querySelector('#snapshot').textContent = 'Source date unavailable'; });
