# Contributing

This project needs community help to go from a v0.1 pilot to a verified, useful dataset.

## How to contribute

1. **Verify a row.** Pick a company in `eu_sustainability_reports.csv`, find their latest published sustainability report, and fill in `report_year`, `gri_referenced`, `universal_standards`, `topic_standards_200/300/400`, and `externally_assured`. Change `verification_status` to `verified`.
2. **Add a company.** Open a PR adding a new row for an EU-headquartered company with a public sustainability report, following the existing schema.
3. **Expand scope.** Once the EU pilot is solid, help extend to other regions (North America, Asia-Pacific) using the same schema.
4. **Fix errors.** If a URL is broken or a company detail is wrong, open an issue or PR.

## Guidelines

- Only include publicly available, company-published sustainability/ESG reports.
- Cite the exact report URL where possible (not just the general sustainability page).
- Keep entries factual — no personal opinions or ratings in the dataset itself.

## Data license

All contributions are released under CC0 1.0 (public domain).
