# Changelog

Completed release-track planning and implementation history for Montreal MCM.

## [0.1.2] Stabilize The Live MVP

The `0.1.x` line made the live product dependable. It is closed at release `0.1.2`; remaining
reliability improvements now belong to `0.2.x` unless they are urgent production incidents.

### Deployment And Operations

Questions monitored during `0.1.x`:

- Is `montrealmcm.ca` resolving consistently under external monitoring?
- Is the current Worker-to-container-to-D1 bridge fast enough for public browse traffic?
- Do we need a cheaper/faster read path for high-traffic pages, such as cached rendered pages or
  batched D1 bridge calls?
- What is the minimum monitoring needed before sharing the site more broadly?

Completed in `0.1.1`:

- make `/healthz` verify app process health without requiring D1
- add a separate deeper health endpoint or admin check that verifies D1 connectivity
- protect admin routes when `MCM_ADMIN_TOKEN` is configured
- redirect `www.montrealmcm.ca` to `montrealmcm.ca`
- add a repeatable operations runbook with deploy, health-check, backup, and bad-deploy recovery
  steps
- add `npm run d1:backup` and ignore local backup exports
- add `npm run prod:health` for repeatable public health, custom-domain, admin-auth, cron-blocking,
  D1 count, and refresh-job checks
- document production admin-token rotation so the owner can store the token outside the repository
- rotate `MCM_ADMIN_TOKEN` to an owner-stored value and verify authenticated `npm run prod:health`
- add a second daily cron that logs missing or non-success per-source refresh jobs

Moved to `0.2.x`:

- add external uptime checks or alert delivery if log-only monitoring is not enough

### Refresh Reliability

The current cron enqueues refresh work through Cloudflare Queues. The queue consumer calls private
container refresh endpoints and writes to D1 through the Worker bridge. This became necessary
because Showroom Montreal and Le Centerpiece are too slow for a request-shaped per-source refresh.

Current decision:

- For `0.1.x`, refresh runs through Cloudflare Queues.
- Partial refresh success is acceptable: one source can fail without blocking the others.
- Production refresh messages run sequentially from the Worker queue consumer to avoid overloading
  the single Cloudflare container instance with multiple concurrent long crawls.
- Manual forced refreshes enqueue one source or all active sources and return quickly.
- D1 `refresh_jobs`, admin source status, and the second monitor cron provide current visibility.
- Cloudflare Workflows should be reconsidered only if refresh becomes multi-step orchestration with
  durable backoff, branching, or richer run history.

Completed in `0.1.1`:

- split refresh into per-source jobs
- make the cron trigger one private container refresh request per source instead of one long
  all-source request
- record refresh job status in D1
- expose last refresh job status per source in admin
- preserve existing conservative behavior: source failures should not deactivate existing inventory
  when a shop already has records
- fix Showroom's Wix `siteassets` URL decoding so BeautifulSoup's `&reg` entity handling does not
  corrupt `&registryLibrariesTopology` and trigger a non-ASCII URL failure in the container
- add a lightweight `/readyz` endpoint for Cloudflare container readiness checks separate from deep
  D1 health

Completed in `0.1.2`:

- add a Cloudflare Queue binding and producer in `src/worker.js`
- add a queue consumer that runs refresh messages with controlled concurrency and retries
- keep a guarded manual refresh endpoint that enqueues one source or all active sources
- configure single-message queue batches, max concurrency 1, retries, and a dead-letter queue
- document queue creation, retry, dead-letter, and manual force-refresh behavior in
  `docs/operations.md`
- split Showroom Montreal into 12 queue chunks and filter its sold archive rows before ingestion
- split Le Centerpiece into 7 Shopify collection chunks and skip sold-out products in chunked
  refreshes
- keep chunk refreshes non-authoritative for now: chunks upsert current listings but do not
  deactivate missing inventory until a later source-wide reconciliation exists
- mark stale `running` refresh jobs from the monitor cron so admin status is not permanently noisy

Closure check:

- observe the next scheduled production refresh after queue chunking and confirm successful
  `refresh_jobs` rows for each active source/chunk

Moved to `0.2.x`:

- add owner alerting if admin-dashboard and log visibility are not enough
- add monitor cron status checks for suspicious hidden-count spikes

Forced production refresh notes from 2026-05-12:

- Morceau completed through the Worker-to-container-to-D1 path in about 10 seconds: 34 listings, 0
  new, 39 hidden.
- Montreal Moderne completed through the same path in about 15 seconds: 49 listings, 0 new, 37
  hidden.
- Showroom completed as 12 queue chunks after sold-archive filtering: 779 listings found, 504 new,
  no sold archive rows imported.
- Le Centerpiece completed as 7 queue chunks after the manual refresh token was rotated: 230
  listings found, 18 new, all chunk jobs successful.

### Admin Safety

Admin routes are useful but should not remain casually reachable as production traffic grows.

Current decision:

- For `0.1.x`, admin routes use a simple owner-controlled `MCM_ADMIN_TOKEN`.
- Worker-level public traffic blocks `/cron/*` and `/internal/*`.
- Cloudflare Access and explicit admin audit tables remain future options if operational risk grows.

Completed in `0.1.1`:

- protect admin routes, including manual admin refresh, when `MCM_ADMIN_TOKEN` is configured
- keep public Worker traffic from reaching `/cron/*` or `/internal/*`

Remaining follow-up:

- keep manual notes, availability overrides, category overrides, and duplicate review durable in D1
- decide whether manual overrides need an explicit audit table

### Data And Schema Hygiene

Questions settled or deferred during `0.1.x`:

- Do we need a D1 backup/export routine before adding more write-heavy features?
- Should local SQLite migrations be formalized, or is D1 migration history enough for now?
- Which fields are genuinely source-derived versus admin-authored?

Completed in `0.1.1`:

- add a repeatable D1 export/backup command
- keep migrations small and reviewable
- make seed/import paths explicit and avoid hand-editing derived data
- keep local `data/mcm.db` as development data, not a source of permanent facts
- add D1 migration `0003_refresh_jobs.sql` for source-level refresh job tracking

Remaining follow-up:

- decide whether local SQLite migrations need a first-class migration runner beyond `ensure_schema`

### Source Parser Maintenance

Questions settled or deferred during `0.1.x`:

- Should `mcm/sources.py` be split before adding more sources?
- Which parser failures deserve fallback data versus a visible source warning?
- Are direct-shop pages enough for the next few releases, or do some sources require Shopify/Wix
  helpers?

Likely work moved forward:

- split source definitions, fetch helpers, normalization helpers, and parser-specific code
- add source-level parser tests for current sources
- keep provenance and source URLs review-friendly
- clean legacy Showroom fallback and override URLs so seeded data follows the same source-page URL
  convention as live parsing

Decision after `0.1.1` review:

- keep the current source module for `0.1.x` because the live-dependability work is now covered and
  splitting parser files is a larger readability refactor with higher churn; revisit before adding
  more sources

### UX Polish

Questions settled or deferred during `0.1.x`:

- Are listing cards dense enough for repeated browsing?
- Should cards show location only once non-Montreal sources are added?
- Should the public scope include lighting/decor now, or stay furniture-first?

Likely work moved forward:

- improve empty/filter states
- refine mobile filter ergonomics
- add a clear stale-data/freshness presentation where useful
- normalize listing-grid thumbnails enough that mixed source image canvases feel intentional

Decision after `0.1.1` review:

- keep UX polish out of the final `0.1.x` hardening pass unless a concrete browsing bug appears;
  move broader card-density, mobile-filter, and image-canvas refinements into `0.2.x` planning

### 0.1.x Success Criteria

The `0.1.x` line is successful as of `0.1.2`:

- local development, deploy dry-run, Cloudflare deploy, and live health checks are routine
- the production app clearly reads/writes D1, not container disk
- refresh is reliable enough to trust daily
- admin paths are protected
- current source inventory feels dependable enough for repeated browsing
