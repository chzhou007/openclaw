---
name: multi-factor-strategy
description: 运行多因子选股策略（动量/波动率/估值/盈利质量），输出排序结果与源信息。
metadata:
  {
    "openclaw":
      {
        "emoji": "🧮",
        "requires": { "bins": ["python3"], "env": ["TUSHARE_TOKEN"] },
        "primaryEnv": "TUSHARE_TOKEN",
      },
  }
---

# Multi-factor Strategy

该 skill 关注“可执行的因子排序”：

- 动量（20日）
- 波动率（20日，负向）
- 估值（PE/PB，负向）
- 质量与成长（ROE、净利润同比）

## Run

```bash
python {baseDir}/scripts/run_strategy.py \
  --universe 002906.SZ,300750.SZ,603259.SH \
  --start-date 20240101 \
  --end-date 20260331 \
  --format md
```

## Notes

- 强依赖 Tushare（需要 `TUSHARE_TOKEN`）。
- 输出必须包含 `Source info`，标注 provider/endpoint/apis/查询时间。
- 策略用于研究，不构成投资建议。
