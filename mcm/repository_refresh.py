from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RefreshJobRef:
    shop_id: int
    source_slug: str
    started_at: str
    chunk_index: int | None = None


def latest_successful_chunk_jobs(
    db: sqlite3.Connection,
    source_slug: str,
    expected_count: int,
    since: str = "",
) -> list[sqlite3.Row]:
    rows = db.execute(
        """
        SELECT rj.chunk_index, rj.started_at, rj.listings_found
        FROM refresh_jobs rj
        JOIN (
            SELECT chunk_index, MAX(started_at) AS started_at
            FROM refresh_jobs
            WHERE source_slug = ?
              AND chunk_index IS NOT NULL
              AND status = 'success'
              AND started_at >= ?
            GROUP BY chunk_index
        ) latest
          ON latest.chunk_index = rj.chunk_index
         AND latest.started_at = rj.started_at
        WHERE rj.source_slug = ?
          AND rj.chunk_index >= 0
          AND rj.chunk_index < ?
        """,
        (source_slug, since, source_slug, expected_count),
    ).fetchall()
    return rows


def record_availability_event(
    db: sqlite3.Connection,
    listing_id: int,
    shop_id: int,
    source_listing_key: str,
    from_status: str,
    to_status: str,
    observed_at: str,
    event_type: str,
) -> None:
    db.execute(
        """
        INSERT INTO listing_availability_events (
            listing_id, shop_id, source_listing_key, observed_at,
            from_status, to_status, event_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            listing_id,
            shop_id,
            source_listing_key,
            observed_at,
            from_status,
            to_status,
            event_type,
        ),
    )


def record_price_event(
    db: sqlite3.Connection,
    listing_id: int,
    shop_id: int,
    source_listing_key: str,
    from_price_raw: str,
    from_price_value: object,
    to_price_raw: str,
    to_price_value: object,
    currency: str,
    observed_at: str,
    event_type: str,
) -> None:
    db.execute(
        """
        INSERT INTO listing_price_events (
            listing_id, shop_id, source_listing_key, observed_at,
            from_price_raw, from_price_value, to_price_raw, to_price_value,
            currency, event_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            listing_id,
            shop_id,
            source_listing_key,
            observed_at,
            from_price_raw,
            from_price_value,
            to_price_raw,
            to_price_value,
            currency,
            event_type,
        ),
    )


def reassign_listing_events(
    db: sqlite3.Connection,
    from_listing_id: int,
    to_listing_id: int,
    source_listing_key: str,
) -> None:
    db.execute(
        """
        UPDATE listing_availability_events
        SET listing_id = ?,
            source_listing_key = ?
        WHERE listing_id = ?
        """,
        (to_listing_id, source_listing_key, from_listing_id),
    )
    db.execute(
        """
        UPDATE listing_price_events
        SET listing_id = ?,
            source_listing_key = ?
        WHERE listing_id = ?
        """,
        (to_listing_id, source_listing_key, from_listing_id),
    )


def start_refresh_job(
    db: sqlite3.Connection,
    shop_id: int,
    source_slug: str,
    started_at: str,
    *,
    chunk_index: int | None = None,
    entry_url: str = "",
) -> RefreshJobRef:
    db.execute(
        """
        INSERT INTO refresh_jobs (
            shop_id, source_slug, chunk_index, entry_url, started_at, status
        )
        VALUES (?, ?, ?, ?, ?, 'running')
        """,
        (shop_id, source_slug, chunk_index, entry_url, started_at),
    )
    return RefreshJobRef(
        shop_id=shop_id,
        source_slug=source_slug,
        started_at=started_at,
        chunk_index=chunk_index,
    )


def finish_refresh_job(
    db: sqlite3.Connection,
    job: RefreshJobRef,
    finished_at: str,
    *,
    status: str,
    listings_found: int,
    new_count: int,
    reconciled_count: int,
    hidden_count: int,
    error_message: str,
) -> None:
    db.execute(
        """
        UPDATE refresh_jobs
        SET finished_at = ?,
            status = ?,
            listings_found = ?,
            new_count = ?,
            reconciled_count = ?,
            hidden_count = ?,
            error_message = ?
        WHERE shop_id = ?
          AND source_slug = ?
          AND started_at = ?
        """,
        (
            finished_at,
            status,
            listings_found,
            new_count,
            reconciled_count,
            hidden_count,
            error_message,
            job.shop_id,
            job.source_slug,
            job.started_at,
        ),
    )


def finish_refresh_job_with_result(
    db: sqlite3.Connection,
    job: RefreshJobRef,
    finished_at: str,
    result: Any,
) -> None:
    finish_refresh_job(
        db,
        job,
        finished_at,
        status="warning" if result.error else "success",
        listings_found=result.listings_found,
        new_count=result.new_count,
        reconciled_count=result.reconciled_count,
        hidden_count=result.hidden_count,
        error_message=result.error,
    )
