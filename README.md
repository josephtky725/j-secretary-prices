# J Secretary prices

A free daily job that turns KPDN PriceCatcher open data into small files for J Secretary (Josephine) to read.
Source: KPDN PriceCatcher via data.gov.my, CC BY 4.0. Prices are collected at physical shops by KPDN staff.

- `build_prices.py`: downloads the month's prices and the item and shop lookups, keeps each shop's latest
  price from the last 14 days, and writes `out/`.
- `.github/workflows/prices.yml`: runs it every day at 1:30 PM Malaysia time and publishes `out/` to the
  `data` branch (replaced each day, so the repository stays small).

The repository must be **public** so the Worker can read the files from raw.githubusercontent.com.
The data is public government data; nothing personal is stored here.
