# Source Inventory (multi-factor-strategy)

## Provider

- Tushare Pro (`https://api.tushare.pro`)

## APIs used

- `daily` for close history (momentum/volatility)
- `daily_basic` for valuation & turnover
- `fina_indicator` for profitability and growth

## Source extension notes

If Tushare is unavailable, keep the ranking pipeline deterministic by:

1. writing source status as `error` in output metadata,
2. returning partial ranking only when required factor data exists,
3. preserving a machine-readable `source_info` block for audit.
