# Open Sustainability Reports Database

An open, CC0-licensed catalog of corporate sustainability reports, starting with a European Union pilot batch. Modeled on [open-epd-india](https://github.com/Creator619-Python/open-epd-india).

## Why this exists

GRI's own Sustainability Disclosure Database was discontinued as an actively maintained public resource (last populated December 2020). This project sources data directly from companies instead, so it doesn't depend on a single centralized registry.

## Pilot scope (v0.1)

- **Region:** European Union
- **Companies:** 98
- **Countries:** 8 (Germany, France, Denmark, Italy, Spain, Netherlands, Belgium, Austria)
- **Sectors:** 25 sector/sub-sector labels across technology, automotive, pharma, finance, energy, retail, and more

## Files

- `eu_sustainability_reports.csv` — main dataset
- `eu_sustainability_reports.json` — same data, JSON format

## Schema

| Column | Description |
|---|---|
| company_name | Company name |
| country | HQ country |
| sector | Industry sector |
| hq_city | Headquarters city |
| sustainability_page_url | Company's sustainability/ESG page |
| gri_referenced | Whether the company is known to reference GRI Standards (Y/N) |
| report_year | Latest report year (pending verification) |
| universal_standards | GRI 1/2/3 compliance notes (pending verification) |
| topic_standards_200 | Economic disclosures tagged (pending verification) |
| topic_standards_300 | Environmental disclosures tagged (pending verification) |
| topic_standards_400 | Social disclosures tagged (pending verification) |
| externally_assured | Whether the report has external assurance (pending verification) |
| verification_status | Data quality status per row |
| source_method | How the entry was sourced |

## Status

This is a v0.1 pilot. Company names, countries, sectors, and sustainability page URLs have been compiled from public sources. Report-level fields (report year, GRI standards tagging, assurance status) are marked `unverified — pending manual review` and need contributor verification against each company's actual published report.

## Contributing

See `CONTRIBUTING.md`.

## License

CC0 1.0 — public domain. See `LICENSE`.
