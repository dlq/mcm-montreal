from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterable, Sequence
from typing import Any


class D1Error(RuntimeError):
    pass


class D1Connection:
    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.token = token

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> D1Cursor:
        payload = json.dumps(
            {
                "sql": sql,
                "params": list(parameters or []),
            }
        ).encode()
        request = urllib.request.Request(
            self.url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "MontrealMCM-D1Bridge/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise D1Error(f"D1 bridge returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise D1Error(f"D1 bridge request failed: {exc}") from exc

        if not body.get("success", False):
            raise D1Error(body.get("error") or "D1 bridge query failed")
        return D1Cursor(body.get("results", []), int(body.get("changes") or 0))

    def executemany(self, sql: str, seq_of_parameters: Iterable[Sequence[Any]]) -> None:
        for parameters in seq_of_parameters:
            self.execute(sql, parameters)

    def executescript(self, _script: str) -> None:
        raise D1Error("D1 schema changes must be applied through Wrangler migrations")

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


class D1Cursor:
    def __init__(self, rows: list[dict[str, Any]], rowcount: int) -> None:
        self._rows = [D1Row(row) for row in rows]
        self.rowcount = rowcount

    def fetchone(self) -> D1Row | None:
        if not self._rows:
            return None
        return self._rows.pop(0)

    def fetchall(self) -> list[D1Row]:
        rows = self._rows
        self._rows = []
        return rows


class D1Row(dict[str, Any]):
    pass
