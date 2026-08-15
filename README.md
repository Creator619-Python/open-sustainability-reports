# Open Sustainability Reports Database

An open, CC0-licensed catalog of corporate sustainability reports, starting with a European Union pilot batch. Modeled on [open-epd-india](https://github.com/Creator619-Python/open-epd-india).

## Why this exists

GRI's own Sustainability Disclosure Database was discontinued as an actively maintained public resource (last populated December 2020). This project sources data directly from companies instead, so it doesn't depend on a single centralized registry.

## Pilot scope (v0.3)

- **Region:** European Union
- **Companies:** 311
- **Countries:** all 27 EU member states (Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden)
- **Sectors:** wide-ranging free-text industry descriptions spanning technology, automotive, pharma, finance, energy, retail, telecom, defense, and more

Grew in three rounds: 49 -> 98 companies (8 founding countries), 98 -> 202 (19 new countries added, full EU-27 coverage reached), 202 -> 311 (deeper coverage within all 27 countries, ~11-12 companies per country on average).

## Files

- `eu_sustainability_reports.csv` — main dataset (311 companies)
- `eu_sustainability_reports.json` — same data, JSON format
- `all_311_report_sources.csv` — per-company report source manifest (`source_pdf_url`, `source_type`: `downloadable_pdf` vs `webpage_landing_page`, notes on CSRD/ESRS migration, name collisions, etc.) — see `gemini_gri_extractor.py` for how this is used to auto-verify GRI disclosures
- `gemini_gri_extractor.py` — script that reads the manifest and uses the Gemini API to check each source document for a GRI Content Index
- `merge_expansion.py` — helper for folding a partial verification run into a newer, larger version of the dataset
- `ROADMAP.md` — planned directions (legacy/historical reports, community verification workflow, benchmarking)

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

Company names, countries, sectors, and sustainability page URLs have been compiled from public sources. Report-level fields (report year, GRI standards tagging, assurance status) are marked `unverified — pending manual review` and need contributor verification against each company's actual published report — `gemini_gri_extractor.py` automates this by reading each source document and checking for a GRI Content Index. 259 of 311 companies (83%) now have a direct `downloadable_pdf` source rather than a general landing page; see `all_311_report_sources.csv`'s `notes` column for cases involving CSRD/ESRS migration, redomiciled HQs, or similarly-named unrelated companies.

## Contributing

See `CONTRIBUTING.md`.

## License

CC0 1.0 — public domain. See `LICENSE`.
