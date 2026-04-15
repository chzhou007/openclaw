#!/usr/bin/env python3
"""Run a lightweight multi-factor stock ranking strategy with source lineage."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import urllib.request
from typing import Any

TUSHARE_ENDPOINT = "https://api.tushare.pro"


def _post(payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        TUSHARE_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tushare_query(token: str, api_name: str, params: dict[str, Any], fields: str) -> list[dict[str, Any]]:
    payload = {"api_name": api_name, "token": token, "params": params, "fields": fields}
    raw = _post(payload)
    data = raw.get("data") or {}
    items = data.get("items") or []
    cols = data.get("fields") or []
    if not isinstance(items, list) or not isinstance(cols, list):
        return []
    return [dict(zip(cols, row, strict=False)) for row in items]


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _zscore(values: list[float], value: float) -> float:
    if len(values) < 2:
        return 0.0
    m = statistics.mean(values)
    sd = statistics.pstdev(values)
    if sd == 0:
        return 0.0
    return (value - m) / sd


def momentum_score(closes: list[float], lookback: int = 20) -> float | None:
    if len(closes) < lookback + 1:
        return None
    return (closes[-1] / closes[-lookback - 1]) - 1


def volatility_score(closes: list[float], lookback: int = 20) -> float | None:
    if len(closes) < lookback + 1:
        return None
    rets = []
    window = closes[-(lookback + 1) :]
    for i in range(1, len(window)):
        if window[i - 1] == 0:
            continue
        rets.append((window[i] / window[i - 1]) - 1)
    if len(rets) < 2:
        return None
    return statistics.pstdev(rets)


def load_factor_snapshot(token: str, ts_code: str, start_date: str, end_date: str) -> dict[str, Any]:
    daily = tushare_query(
        token,
        "daily",
        {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
        "ts_code,trade_date,close,vol",
    )
    daily.sort(key=lambda r: r.get("trade_date") or "")
    closes = [_to_float(r.get("close")) for r in daily]
    closes = [x for x in closes if x is not None]

    daily_basic = tushare_query(
        token,
        "daily_basic",
        {"ts_code": ts_code, "limit": 1},
        "ts_code,trade_date,pe_ttm,pb,turnover_rate,total_mv",
    )
    latest_basic = daily_basic[0] if daily_basic else {}

    fina = tushare_query(
        token,
        "fina_indicator",
        {"ts_code": ts_code, "limit": 1},
        "ts_code,ann_date,end_date,roe,netprofit_yoy,or_yoy,grossprofit_margin",
    )
    latest_fina = fina[0] if fina else {}

    return {
        "ts_code": ts_code,
        "close_count": len(closes),
        "momentum_20d": momentum_score(closes, 20),
        "volatility_20d": volatility_score(closes, 20),
        "pe_ttm": _to_float(latest_basic.get("pe_ttm")),
        "pb": _to_float(latest_basic.get("pb")),
        "turnover_rate": _to_float(latest_basic.get("turnover_rate")),
        "roe": _to_float(latest_fina.get("roe")),
        "netprofit_yoy": _to_float(latest_fina.get("netprofit_yoy")),
        "or_yoy": _to_float(latest_fina.get("or_yoy")),
        "grossprofit_margin": _to_float(latest_fina.get("grossprofit_margin")),
    }


def rank_universe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Higher is better for momentum, roe, yoy; lower is better for volatility/valuation.
    momentum_vals = [r["momentum_20d"] for r in rows if isinstance(r.get("momentum_20d"), float)]
    vol_vals = [r["volatility_20d"] for r in rows if isinstance(r.get("volatility_20d"), float)]
    pe_vals = [r["pe_ttm"] for r in rows if isinstance(r.get("pe_ttm"), float)]
    pb_vals = [r["pb"] for r in rows if isinstance(r.get("pb"), float)]
    roe_vals = [r["roe"] for r in rows if isinstance(r.get("roe"), float)]
    npy_vals = [r["netprofit_yoy"] for r in rows if isinstance(r.get("netprofit_yoy"), float)]

    ranked = []
    for row in rows:
        mom = row.get("momentum_20d")
        vol = row.get("volatility_20d")
        pe = row.get("pe_ttm")
        pb = row.get("pb")
        roe = row.get("roe")
        npy = row.get("netprofit_yoy")
        score = 0.0
        if isinstance(mom, float):
            score += _zscore(momentum_vals, mom)
        if isinstance(vol, float):
            score -= _zscore(vol_vals, vol)
        if isinstance(pe, float):
            score -= 0.6 * _zscore(pe_vals, pe)
        if isinstance(pb, float):
            score -= 0.4 * _zscore(pb_vals, pb)
        if isinstance(roe, float):
            score += _zscore(roe_vals, roe)
        if isinstance(npy, float):
            score += 0.8 * _zscore(npy_vals, npy)
        ranked.append({**row, "composite_score": round(score, 4)})

    ranked.sort(key=lambda r: r.get("composite_score", -999), reverse=True)
    return ranked


def main() -> int:
    parser = argparse.ArgumentParser(description="Run multi-factor strategy")
    parser.add_argument("--universe", required=True, help="comma separated ts_code list")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--token", default=os.getenv("TUSHARE_TOKEN"))
    parser.add_argument("--format", choices=["json", "md"], default="md")
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("TUSHARE_TOKEN is required for multi-factor-strategy")

    ts_codes = [t.strip().upper() for t in args.universe.split(",") if t.strip()]
    snapshots = [load_factor_snapshot(args.token, ts_code, args.start_date, args.end_date) for ts_code in ts_codes]
    ranked = rank_universe(snapshots)

    source_info = {
        "provider": "tushare",
        "endpoint": TUSHARE_ENDPOINT,
        "queried_at": dt.datetime.utcnow().isoformat() + "Z",
        "apis": ["daily", "daily_basic", "fina_indicator"],
        "universe_size": len(ts_codes),
    }

    if args.format == "json":
        print(json.dumps({"ranked": ranked, "source_info": source_info}, ensure_ascii=False, indent=2))
        return 0

    lines = ["# Multi-factor Strategy Ranking", "", f"- universe size: {len(ts_codes)}", "", "| rank | ts_code | score | pe_ttm | pb | roe | netprofit_yoy |", "| ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for i, row in enumerate(ranked, 1):
        lines.append(
            f"| {i} | {row.get('ts_code')} | {row.get('composite_score')} | {row.get('pe_ttm')} | {row.get('pb')} | {row.get('roe')} | {row.get('netprofit_yoy')} |"
        )
    lines.extend([
        "",
        "## Source info",
        f"- provider: {source_info['provider']}",
        f"- endpoint: {source_info['endpoint']}",
        f"- apis: {', '.join(source_info['apis'])}",
        f"- queried_at: {source_info['queried_at']}",
    ])
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
