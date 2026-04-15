#!/usr/bin/env python3
"""Generate a stock technical + multi-dimensional markdown report."""

from __future__ import annotations

import argparse
import json
import math
import os
from statistics import mean
from typing import Any

from tushare_client import SourceEvent, load_data_with_memmap, tushare_query


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(-period, 0):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains.append(delta)
        else:
            losses.append(abs(delta))
    avg_gain = mean(gains) if gains else 0.0
    avg_loss = mean(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_v = mean(values[:period])
    for p in values[period:]:
        ema_v = p * k + ema_v * (1 - k)
    return ema_v


def macd_hist(values: list[float]) -> float | None:
    if len(values) < 35:
        return None
    ema12 = ema(values, 12)
    ema26 = ema(values, 26)
    if ema12 is None or ema26 is None:
        return None
    dif = ema12 - ema26
    # Lightweight approximation of DEA from trailing DIF history.
    dif_series: list[float] = []
    for i in range(26, len(values)):
        e12 = ema(values[: i + 1], 12)
        e26 = ema(values[: i + 1], 26)
        if e12 is not None and e26 is not None:
            dif_series.append(e12 - e26)
    dea = ema(dif_series, 9) if len(dif_series) >= 9 else None
    if dea is None:
        return None
    return dif - dea


def bollinger(values: list[float], period: int = 20, k: float = 2.0) -> tuple[float | None, float | None, float | None]:
    if len(values) < period:
        return None, None, None
    sample = values[-period:]
    mid = mean(sample)
    var = mean([(x - mid) ** 2 for x in sample])
    std = math.sqrt(var)
    return mid + k * std, mid, mid - k * std


def select_latest_financial_rows(token: str, ts_code: str) -> tuple[dict[str, Any], list[SourceEvent]]:
    events: list[SourceEvent] = []
    endpoints = [
        (
            "income",
            "ts_code,ann_date,end_date,total_revenue,revenue,n_income,n_income_attr_p",
        ),
        (
            "fina_indicator",
            "ts_code,ann_date,end_date,grossprofit_margin,roe,or_yoy,netprofit_yoy,rd_exp,rd_exp_ratio",
        ),
        (
            "balancesheet",
            "ts_code,ann_date,end_date,total_assets,total_liab,accounts_receiv",
        ),
        (
            "cashflow",
            "ts_code,ann_date,end_date,n_cashflow_act",
        ),
        (
            "daily_basic",
            "ts_code,trade_date,pe_ttm,pb,turnover_rate,volume_ratio,total_mv",
        ),
    ]
    combined: dict[str, Any] = {}
    for endpoint, fields in endpoints:
        try:
            rows = tushare_query(endpoint, params={"ts_code": ts_code, "limit": 8}, fields=fields, token=token)
            if rows:
                rows.sort(key=lambda r: ((r.get("ann_date") or ""), (r.get("end_date") or "")), reverse=True)
                combined[endpoint] = rows[0]
            events.append(
                SourceEvent(provider="tushare", endpoint=endpoint, status="ok", rows=len(rows), requested_at="", notes="")
            )
        except Exception as exc:  # noqa: BLE001
            events.append(
                SourceEvent(provider="tushare", endpoint=endpoint, status="error", rows=0, requested_at="", notes=str(exc))
            )
    return combined, events


def render_report(
    *,
    ts_code: str,
    as_of: str,
    prices: list[dict[str, Any]],
    technical: dict[str, Any],
    financials: dict[str, Any],
    sources: list[SourceEvent],
) -> str:
    close_series = [_safe_float(r.get("close")) for r in prices]
    close_series = [v for v in close_series if v is not None]
    last_close = close_series[-1] if close_series else None

    income = financials.get("income") or {}
    fina = financials.get("fina_indicator") or {}
    bal = financials.get("balancesheet") or {}
    cash = financials.get("cashflow") or {}
    daily_basic = financials.get("daily_basic") or {}

    lines = [
        f"# {ts_code} 综合分析报告",
        "",
        f"- 估值/技术截止日: {as_of}",
        f"- 最新收盘价: {last_close:.2f}" if last_close is not None else "- 最新收盘价: 无可用数据",
        "",
        "## 一、基本面分析（四维分析法）",
        "### 经营维度",
        f"- 收入（最新披露）: {income.get('revenue') or income.get('total_revenue') or '待补充'}",
        f"- 净利润（归母）: {income.get('n_income_attr_p') or income.get('n_income') or '待补充'}",
        f"- 研发强度: {fina.get('rd_exp_ratio') or '待补充'}",
        "",
        "### 管理维度",
        "- 业务结构与客户结构: 建议结合公司公告与年报正文补全。",
        "",
        "### 财务维度",
        f"- 资产负债率（需可用字段换算）: 待补充",
        f"- 应收账款: {bal.get('accounts_receiv') or '待补充'}",
        f"- 经营现金流净额: {cash.get('n_cashflow_act') or '待补充'}",
        "",
        "### 业绩维度",
        f"- 毛利率: {fina.get('grossprofit_margin') or '待补充'}",
        f"- ROE: {fina.get('roe') or '待补充'}",
        f"- 净利润同比: {fina.get('netprofit_yoy') or '待补充'}",
        "",
        "## 二、估值面分析",
        f"- PE(TTM): {daily_basic.get('pe_ttm') or '待补充'}",
        f"- PB: {daily_basic.get('pb') or '待补充'}",
        f"- 总市值: {daily_basic.get('total_mv') or '待补充'}",
        "",
        "## 三、技术面分析",
        f"- MA5/10/20/60: {technical.get('ma5')} / {technical.get('ma10')} / {technical.get('ma20')} / {technical.get('ma60')}",
        f"- RSI14: {technical.get('rsi14')}",
        f"- MACD(hist): {technical.get('macd_hist')}",
        f"- 布林带(上/中/下): {technical.get('boll_upper')} / {technical.get('boll_mid')} / {technical.get('boll_lower')}",
        "",
        "## 四、消息面分析",
        "- 该脚本默认不抓新闻正文；建议并行接入公告/研报/新闻源后做事件打分。",
        "",
        "## 五、综合判断矩阵",
        "- 建议在后处理阶段按业务规则打分并输出总分。",
        "",
        "## 六、源信息（扩充）",
        "| provider | endpoint | status | rows | notes |",
        "| --- | --- | --- | ---: | --- |",
    ]

    for event in sources:
        lines.append(
            f"| {event.provider} | {event.endpoint} | {event.status} | {event.rows} | {event.notes or '-'} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate stock technical analysis report")
    parser.add_argument("--ts-code", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--token", default=os.getenv("TUSHARE_TOKEN"))
    parser.add_argument("--out", default="-")
    args = parser.parse_args()

    prices, source_events = load_data_with_memmap(
        ts_code=args.ts_code,
        start_date=args.start_date,
        end_date=args.end_date,
        token=args.token,
    )
    prices.sort(key=lambda r: r.get("trade_date") or "")

    closes = [_safe_float(r.get("close")) for r in prices]
    closes = [c for c in closes if c is not None]
    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    boll_up, boll_mid, boll_low = bollinger(closes)

    technical = {
        "ma5": round(ma5, 4) if ma5 else None,
        "ma10": round(ma10, 4) if ma10 else None,
        "ma20": round(ma20, 4) if ma20 else None,
        "ma60": round(ma60, 4) if ma60 else None,
        "rsi14": round(rsi(closes, 14), 4) if rsi(closes, 14) is not None else None,
        "macd_hist": round(macd_hist(closes), 6) if macd_hist(closes) is not None else None,
        "boll_upper": round(boll_up, 4) if boll_up else None,
        "boll_mid": round(boll_mid, 4) if boll_mid else None,
        "boll_lower": round(boll_low, 4) if boll_low else None,
    }

    financials: dict[str, Any] = {}
    if args.token:
        fs, fs_events = select_latest_financial_rows(args.token, args.ts_code)
        financials.update(fs)
        source_events.extend(fs_events)

    report = render_report(
        ts_code=args.ts_code,
        as_of=args.as_of,
        prices=prices,
        technical=technical,
        financials=financials,
        sources=source_events,
    )

    if args.out == "-":
        print(report)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
