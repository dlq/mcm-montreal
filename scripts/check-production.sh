#!/bin/sh
set -eu

BASE_URL="${MCM_BASE_URL:-https://montreal-mcm.dalaque.workers.dev}"
APEX_URL="${MCM_APEX_URL:-https://montrealmcm.ca}"
WWW_URL="${MCM_WWW_URL:-https://www.montrealmcm.ca}"
D1_DATABASE="${MCM_D1_DATABASE:-montreal-mcm}"

check_url() {
    label="$1"
    url="$2"
    output_file="$3"
    curl -fsS -o "$output_file" -w "$label http=%{http_code} total=%{time_total} size=%{size_download}\n" "$url"
}

expect_redirect() {
    label="$1"
    url="$2"
    expected_location="$3"
    headers_file="/tmp/mcm-${label}-headers.txt"
    status="$(curl -sS -o /dev/null -D "$headers_file" -w "%{http_code}" "$url")"
    location="$(awk 'BEGIN {IGNORECASE = 1} /^location:/ {print $2}' "$headers_file" | tr -d '\r' | tail -n 1)"
    if [ "$status" != "301" ] || [ "$location" != "$expected_location" ]; then
        echo "$label expected HTTP 301 to $expected_location, got HTTP $status to $location" >&2
        return 1
    fi
    echo "$label http=$status location=$location"
}

expect_status() {
    label="$1"
    expected="$2"
    url="$3"
    method="${4:-GET}"
    status="$(curl -sS -o "/tmp/mcm-${label}.txt" -w "%{http_code}" -X "$method" "$url")"
    if [ "$status" != "$expected" ]; then
        echo "$label expected HTTP $expected, got HTTP $status" >&2
        return 1
    fi
    echo "$label http=$status"
}

run_d1() {
    sql="$1"
    if npx wrangler d1 execute "$D1_DATABASE" --remote --command "$sql"; then
        return 0
    fi
    echo "D1 check failed; retrying once ..." >&2
    sleep 2
    npx wrangler d1 execute "$D1_DATABASE" --remote --command "$sql"
}

check_url "healthz" "$BASE_URL/healthz" /tmp/mcm-healthz.txt
check_url "home" "$BASE_URL/" /tmp/mcm-home.html
check_url "apex" "$APEX_URL/" /tmp/mcm-apex.html
expect_redirect "www_redirect" "$WWW_URL/" "$APEX_URL/"

expect_status "admin_noauth" "401" "$BASE_URL/admin/healthz"
expect_status "cron_external" "404" "$BASE_URL/cron/refresh/morceau" "POST"

if [ -n "${MCM_ADMIN_TOKEN:-}" ]; then
    curl -fsS \
        -H "Authorization: Bearer $MCM_ADMIN_TOKEN" \
        -o /tmp/mcm-admin-healthz.json \
        -w "admin_auth http=%{http_code} total=%{time_total} size=%{size_download}\n" \
        "$BASE_URL/admin/healthz"
else
    echo "admin_auth skipped: MCM_ADMIN_TOKEN is not set"
fi

run_d1 "SELECT COUNT(*) AS listings FROM listings;"
run_d1 "SELECT source_slug, status, started_at, finished_at FROM refresh_jobs ORDER BY started_at DESC LIMIT 8;"
