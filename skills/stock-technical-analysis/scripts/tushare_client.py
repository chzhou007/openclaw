#!/usr/bin/env python3
"""Minimal Tushare + public fallback client helpers for stock analysis skills."""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

TUSHARE_ENDPOINT = "https://api.tushare.pro"
YAHOO_CHART_ENDPOINT = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


@dataclass
class SourceEvent:
    provider: str
    endpoint: str
    status: str
    rows: int
    requested_at: str
    notes: str = ""


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _http_post_json(url: str, payload: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tushare_query(
    api_name: str,
    *,
    params: dict[str, Any],
    fields: str,
    token: str,
) -> list[dict[str, Any]]:
    payload = {
        "api_name": api_name,
        "token": token,
        "params": params,
        "fields": fields,
    }
    raw = _http_post_json(TUSHARE_ENDPOINT, payload)
    data = raw.get("data") or {}
    items = data.get("items") or []
    columns = data.get("fields") or []
    if not isinstance(items, list) or not isinstance(columns, list):
        return []
    return [dict(zip(columns, row, strict=False)) for row in items]


def ts_code_to_yahoo_symbol(ts_code: str) -> str:
    # Tushare uses 000001.SZ / 600000.SH. Yahoo accepts the same suffixes.
    return ts_code.upper()


def fetch_yahoo_daily(ts_code: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    symbol = ts_code_to_yahoo_symbol(ts_code)
    start = dt.datetime.strptime(start_date, "%Y%m%d")
    end = dt.datetime.strptime(end_date, "%Y%m%d") + dt.timedelta(days=1)
    params = urllib.parse.urlencode(
        {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": "1d",
            "events": "history",
        }
    )
    url = YAHOO_CHART_ENDPOINT.format(symbol=urllib.parse.quote(symbol, safe="")) + f"?{params}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result") or []
    if not result:
        return []
    entry = result[0]
    timestamps = entry.get("timestamp") or []
    quote = ((entry.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    vols = quote.get("volume") or []

    rows: list[dict[str, Any]] = []
    for idx, ts in enumerate(timestamps):
        if idx >= len(closes) or closes[idx] is None:
            continue
        trade_date = dt.datetime.utcfromtimestamp(ts).strftime("%Y%m%d")
        rows.append(
            {
                "ts_code": ts_code,
                "trade_date": trade_date,
                "open": opens[idx] if idx < len(opens) else None,
                "high": highs[idx] if idx < len(highs) else None,
                "low": lows[idx] if idx < len(lows) else None,
                "close": closes[idx],
                "vol": vols[idx] if idx < len(vols) else None,
            }
        )
    return rows


def load_data_with_memmap(
    *,
    ts_code: str,
    start_date: str,
    end_date: str,
    token: str | None = None,
) -> tuple[list[dict[str, Any]], list[SourceEvent]]:
    """Load daily OHLCV data (Tushare preferred, public fallback).

    Name kept aligned with user workflow while returning python-native rows.
    """

    source_events: list[SourceEvent] = []
    token = token or os.getenv("TUSHARE_TOKEN")

    if token:
        try:
            rows = tushare_query(
                "daily",
                params={"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
                fields="ts_code,trade_date,open,high,low,close,vol,amount",
                token=token,
            )
            source_events.append(
                SourceEvent(
                    provider="tushare",
                    endpoint="daily",
                    status="ok",
                    rows=len(rows),
                    requested_at=_now_iso(),
                    notes="tushare api_name=daily",
                )
            )
            if rows:
                return rows, source_events
        except Exception as exc:  # noqa: BLE001
            source_events.append(
                SourceEvent(
                    provider="tushare",
                    endpoint="daily",
                    status="error",
                    rows=0,
                    requested_at=_now_iso(),
                    notes=str(exc),
                )
            )

    try:
        rows = fetch_yahoo_daily(ts_code, start_date, end_date)
        source_events.append(
            SourceEvent(
                provider="yahoo-finance",
                endpoint="chart/v8",
                status="ok" if rows else "empty",
                rows=len(rows),
                requested_at=_now_iso(),
                notes="public fallback",
            )
        )
        return rows, source_events
    except Exception as exc:  # noqa: BLE001
        source_events.append(
            SourceEvent(
                provider="yahoo-finance",
                endpoint="chart/v8",
                status="error",
                rows=0,
                requested_at=_now_iso(),
                notes=str(exc),
            )
        )
        return [], source_events
