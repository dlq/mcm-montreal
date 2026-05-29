#!/bin/sh
set -eu

D1_DATABASE="${MCM_D1_DATABASE:-montreal-mcm}"
SINCE="${MCM_REFRESH_AUDIT_SINCE:-$(python3 -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00"))')}"
TODAY="${MCM_REFRESH_AUDIT_TODAY:-$(python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime("%Y-%m-%d"))')}"

run_d1() {
    sql="$1"
    npx wrangler d1 execute "$D1_DATABASE" --remote --command "$sql"
}

echo "Refresh job status counts since $SINCE"
run_d1 "
SELECT substr(started_at, 1, 10) AS refresh_date,
       status,
       COUNT(*) AS count
  FROM refresh_jobs
 WHERE started_at >= '$SINCE'
 GROUP BY refresh_date, status
 ORDER BY refresh_date DESC, status;
"

echo "Currently running refresh jobs"
run_d1 "
SELECT id,
       source_slug,
       chunk_index,
       started_at,
       finished_at,
       listings_found,
       hidden_count,
       substr(error_message, 1, 160) AS error_message
  FROM refresh_jobs
 WHERE status = 'running'
 ORDER BY started_at DESC
 LIMIT 50;
"

echo "Recent non-success refresh jobs since $SINCE"
run_d1 "
SELECT id,
       source_slug,
       chunk_index,
       status,
       started_at,
       finished_at,
       listings_found,
       hidden_count,
       substr(error_message, 1, 160) AS error_message
  FROM refresh_jobs
 WHERE started_at >= '$SINCE'
   AND status <> 'success'
 ORDER BY started_at DESC
 LIMIT 100;
"

echo "Today's per-source refresh coverage for $TODAY"
run_d1 "
SELECT source_slug,
       status,
       COUNT(*) AS count,
       MIN(started_at) AS first_started,
       MAX(finished_at) AS last_finished
  FROM refresh_jobs
 WHERE started_at >= '${TODAY}T00:00:00'
 GROUP BY source_slug, status
 ORDER BY source_slug, status;
"
