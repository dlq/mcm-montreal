# Codex Collaboration

- Before making edits, run `git status --short` and preserve unrelated user or agent changes.
- For larger implementation tasks, prefer a dedicated branch or worktree so parallel chats do not mix unrelated edits.
- Keep changes scoped to the current task. Read-only investigation, reviews, and short answers can happen in the existing checkout.
- When technical direction is ambiguous, separate observed facts, inferences, assumptions, and the next verification step before changing code.

## Durable Notes

- Use `research.md` for findings that should survive chat context loss: source behavior, parser evidence, URLs, commands run, unresolved questions, and conclusions.
- Use `plan.md` for execution state: current goal, checklist, decisions, risks, and next steps.
- Update these files only when the durable facts or plan materially change. Do not add conversational notes, temporary scratch work, secrets, or duplicate final responses.

## Project Shape

- This is a Python 3.12 Flask app for Montreal mid-century modern furniture discovery.
- The app uses SQLite, HTMX, Jinja templates, Tailwind via CDN, and native Web Components.
- Core application code lives in `mcm/`, templates in `templates/`, frontend assets in `static/`, and local data under `data/`.
- Source ingestion should remain conservative and review-friendly. Prefer preserving provenance, admin notes, overrides, and fallback seed behavior instead of hand-editing derived data.

## Local Runtime

- Install Python and frontend tooling with `uv sync --dev` and `npm install`.
- Refresh listing data with `uv run app.py refresh`.
- Run the local app with `uv run app.py`, then open `http://127.0.0.1:8000`.
- Network-backed ingestion may fail in restricted environments. If a fetch-dependent command fails because of sandbox or network access, report that clearly and request escalation when the task requires live data.

## Verification

- Run checks that match the files touched before handing off code changes.
- Python: `uv run ruff check .` and `uv run ruff format .`.
- Templates: `uv run djlint templates --lint` and `uv run djlint templates --reformat`.
- Static JS/CSS: `npm run lint` or `npx biome check static`; formatting is covered by `npm run format`.
- For broad changes, prefer `uv run pre-commit run --all-files` after dependencies are installed.
- If a verification command cannot be run, state the reason and the residual risk in the handoff.

## Design And UX

- Keep the MVP focused on browse, filtering, listing detail, shop detail, favourites, and admin review workflows.
- Preserve English/French UI behavior when changing user-facing text or routes.
- Keep templates readable and HTMX interactions progressive. Avoid adding client-side complexity unless it simplifies a real interaction.
- For user-facing UI changes, verify the interface on both desktop and mobile viewports before handoff.
- Tailwind is currently loaded from the CDN; do not introduce a build pipeline unless the task calls for it.

## Data And Deployment

- Treat `data/mcm.db` as local development data, not a place for permanent hand-authored facts.
- Prefer source definitions, seed data, migrations, or importer logic over direct database edits when behavior should be reproducible.
- Do not deploy or publish changes unless explicitly asked.

## What Belongs Here

- Standing project instructions, workflow preferences, repo-specific commands, architecture constraints, verification expectations, and collaboration boundaries belong in this file.
- One-off task details, long research logs, credentials, private tokens, temporary debugging notes, and speculative plans belong elsewhere.
