---
name: stock-technical-analysis
description: A股个股综合分析（基本面/估值面/技术面/消息面）并输出结构化报告，优先使用 Tushare，自动补充公开数据源回退。
metadata:
  {
    "openclaw":
      {
        "emoji": "📈",
        "requires": { "bins": ["python3"], "env": ["TUSHARE_TOKEN"] },
        "primaryEnv": "TUSHARE_TOKEN",
      },
  }
---

# Stock Technical Analysis

用于生成 A 股个股综合分析报告，默认输出以下结构：

1. 基本面分析（四维分析法）
2. 估值面分析
3. 技术面分析
4. 消息面分析（占位，可后续接入）
5. 综合判断矩阵
6. 源信息（扩充）

## Run

```bash
python {baseDir}/scripts/generate_stock_report.py \
  --ts-code 002906.SZ \
  --start-date 20200101 \
  --end-date 20260331 \
  --as-of 2026-03-27 \
  --out -
```

## Data policy

- 首选 Tushare Pro 接口（daily/income/fina_indicator/balancesheet/cashflow/daily_basic）。
- 若行情接口不可用，回退 Yahoo Finance chart/v8 公共接口抓取 K 线。
- 财报口径遵循“按最新披露优先（ann_date/end_date）”原则，避免仅看年报。
- 报告尾部必须输出源信息表（provider/endpoint/status/rows/notes）。

## Notes

- 不要在代码中硬编码 token。
- 使用 `TUSHARE_TOKEN` 环境变量或 `--token` 参数注入。
- 若某字段缺失，报告中标记为“待补充”，不要静默填 0。
