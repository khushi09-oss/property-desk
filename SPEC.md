# Property Desk MVP specification

## Outcome and scope

An English web chatbot answers property and service questions from a bounded, dated DarGlobal/Wasalt snapshot. Factual answers link to official sources and acknowledge missing or conflicting details. Browser-only conversations can be reopened and deleted.

Non-goals: accounts, a server conversation database, purchases, live inventory, investment/tax/visa advice, unrestricted crawling and paid-model fallback.

## Implemented architecture and decisions

- One Python/FastAPI service serves static HTML/CSS/JavaScript and a typed chat API. No frontend framework, model SDK or hosted database is required.
- A reviewed JSON snapshot is validated and indexed in disposable in-memory SQLite FTS5. Broad DarGlobal questions retrieve the company overview before project evidence; the spaced name Dar Global is normalized.
- Use openrouter/free with minimal reasoning effort and no automatic application retries or model tools. Availability and quotas are external constraints. The combined reasoning/answer allowance is 4,096 tokens with a 40-second absolute deadline.
- An incomplete-answer rejection was reproduced before the output allowance was raised. Token exhaustion is a plausible cause, not a proven root cause. Static rejection log categories distinguish output_limit, empty_answer and incomplete_answer without logging prompts, answers, reasoning or credentials.
- Source restrictions blocked direct HTTP collection. The initial nine-record/eight-page snapshot uses explicit web-extraction provenance; no unattended refresh is claimed. The collector checks robots policy, rejects unapproved hosts/redirects, bounds downloads and writes a private review report without replacing the dataset.
- Preserve conflicting size claims and label completion schedules as developer statements. Confirm current commercial details with the official source.
- Keys remain in process environment; the local runner can load only OPENROUTER_API_KEY from ignored local configuration. External content cannot change permissions or network destinations.
- Bound request bytes, question/history lengths, provider time, response bytes and per-instance model concurrency. Per-instance protection is not distributed quota enforcement.
- Render plain text and validated HTTPS official-source links. Reject incomplete/invalid/uncited model output; citation existence alone does not prove factual correctness.

## Public-answer caching

At most six approved public question types are cached for one hour per process after a successful cited answer. Only case, whitespace and terminal punctuation are normalized. Every request with history and all other wording bypass the cache. Entries contain validated answer/model/source data, not arbitrary questions or conversation context.

Deep-copy results, expire using a monotonic clock, and reset on process restart/deployment. The snapshot is immutable within an instance. Separate serverless instances do not share entries; concurrent cold misses can each consume quota. HTTP caching remains disabled. Hits return cached=true, retain original citations/model and show a saved-answer label that survives browser history. Cold caching cannot restore exhausted provider quota.

## Interface, history and privacy

- Refined cream/charcoal interface with Wasalt-purple accents, self-hosted Newsreader headings and Public Sans body text. CSS owns design tokens and responsive type/layout rules; original OFL notices are bundled.
- The sidebar prioritises recent chats; secondary exploration and coverage sit inside About this demo. Short welcome prompts and a compact composer reduce repeated text. Privacy and source notes expand on demand while the saved-source notice remains visible.
- One hamburger opens/closes the sidebar. Sidebar and conversation scroll independently; the composer stays outside the conversation scroll area. On mobile, the sidebar fills the viewport while the hamburger remains accessible; conversation/composer content is inert until it closes.
- Save completed exchanges and citations in localStorage for this origin/browser profile. Retain up to 20 conversations and the latest 40 messages each, within a 1 MB UTF-8 payload and browser quota. Restore the active conversation on reload.
- New conversation preserves older chats; individual deletion and confirmed Clear all affect only the app's storage key. Validate stored roles, lengths and source links. Storage failure leaves the current chat usable with a visible warning.
- No encryption, accounts, cross-device sync or server conversation database. Shared-browser access, private-mode data loss and non-atomic last-save-wins writes across tabs are limits. Other tabs do not automatically refresh their lists.
- Uncached requests send the question, four bounded context turns and selected evidence to OpenRouter/providers. Provider retention is separate from deletion of browser copies. Warn against personal information.

## API contract

- GET /api/health: service status, document count, snapshot date and mode; no credentials or prompts.
- POST /api/chat accepts question:string and history:[{role:user|assistant,content:string}]. Returns answer:string, sources:[{id,title,url,collected_at}], model:string|null and cached:boolean.
- Maximum question length 1,200 characters; four history turns, each 1-1,800 characters; body limit 16 KB. The model adapter bounds upstream responses and each instance permits two simultaneous model calls.
- Invalid input 422; oversized input 413; slow input 408; temporary instance saturation/provider limits 429; missing configuration 503; upstream failure/invalid output 502; timeout 504. Generic errors, no raw provider messages, no automatic retry.

## Verification and operation

Run the commands in README.md, including Python and JavaScript tests, lint/type checks and the root Docker build. Use real runtime checks for changed execution paths; distinguish synthetic model/DOM harness results from live-provider and browser verification. Keep one current verification summary in README.md.

Deployment uses a deny-by-default runtime bundle and server-only secrets. No migration is required for the disposable search index. Browser storage is versioned and validates old records before restoration. Rollback can redeploy a previously reviewed runtime/snapshot; code rollback does not erase provider records or revoke credentials. Production publication and deployment require task-specific authorization.
