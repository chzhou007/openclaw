# Source Inventory (stock-technical-analysis)

## Primary source (authenticated)

- Provider: Tushare Pro
- Endpoint: `https://api.tushare.pro`
- Request shape: JSON POST with keys: `api_name`, `token`, `params`, `fields`
- Endpoints used by this skill:
  - `daily`
  - `income`
  - `fina_indicator`
  - `balancesheet`
  - `cashflow`
  - `daily_basic`

## Public fallback source

- Provider: Yahoo Finance chart API
- Endpoint template: `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}`
- Used only as fallback when Tushare daily行情 unavailable

## Output source logging

The generated markdown report includes a source table with:

- provider
- endpoint
- status
- rows
- notes

This is used to make data lineage explicit and auditable.
