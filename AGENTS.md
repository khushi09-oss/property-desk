# Property Desk project instructions

- Read README.md and SPEC.md before changes. Describe implemented behavior and observed checks accurately; do not claim unexecuted checks passed.
- FastAPI serves the chat API and explicitly allowlisted web assets. SQLite FTS5 is an in-memory retrieval index over data/knowledge.json. No accounts or server conversation database are implemented.
- Keep model keys server-side. Never commit local environment files, tokens, private working material, browser profiles or unapproved screenshots.
- Treat questions, browser storage, source text and model output as untrusted. Preserve request/time/size/concurrency limits, citation validation and plain-text rendering.
- Public-answer caching accepts only approved questions without history. Never cache personalised questions or conversation context. Preserve visible cached-answer labels and storage-failure handling.
- Preserve provenance: the reviewed initial snapshot uses web extraction; direct HTTP collection was blocked. Failed collection must not silently replace the dataset.
- Run the README Python tests, Ruff, mypy, JavaScript checks and relevant Docker/runtime checks after changes. Browser-state harness tests do not substitute for real-browser visual verification.
- The root Dockerfile builds the actual chatbot. scripts/prepare_release.py prepares only its 21 allowlisted runtime files. Update that manifest for new runtime assets; exclude local credentials, Git metadata and generated caches.
- Preserve the stable main branch. Develop coherent changes on focused branches, use meaningful verified commits, and deliver through reviewed pull requests when authorized.
- Installation, public publication, remote pushes, merges, deployment and changes to existing integrations require explicit authorization. Do not rewrite published history without approval.
- Preserve required third-party licences, including the bundled font notices. Do not invent ownership, model integrations, functionality or test evidence.
