# Data Source Strategy

## Active source model

The system now uses one source model only: authenticated users upload historical trading files.

## Supported formats

- CSV
- XLSX

## Fixed template

```text
stock_code,stock_name,trade_date,open,high,low,close,volume,amount
```

## Asset classes

- `stock`
- `commodity`

These labels are metadata only. Both asset classes share the same storage, query, and algorithm path through `trading_records`.

## Isolation model

- every import run belongs to `owner_user_id`
- normal users are always limited to their own runs
- admins can query across all users

## Retired sources

- stock crawler imports
- e-commerce demo imports
- synthetic dataset imports
- benchmark demo routes

