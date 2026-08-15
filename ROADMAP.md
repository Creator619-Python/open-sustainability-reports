# Roadmap

Ideas for evolving this from a v0.1 pilot dataset into a community-maintained resource. Nothing here is committed to a timeline — this is a working list.

## Source quality: downloadable documents over landing pages

As of the 311-company expansion, `all_311_report_sources.csv` distinguishes three kinds of entries via a `source_type` column:

- `downloadable_pdf` — a direct link to the actual report file (sustainability report, GRI content index, or the sustainability-statement chapter of an Annual Report). This is the strong case: verifiers and tools like Gemini's `url_context` can read the primary document directly.
- `webpage_landing_page` — no single downloadable file could be confirmed; the entry points to the company's reporting hub instead (e.g. Mercedes-Benz-style disclosures that live only on a webpage, not a PDF). These need a human or a browsing-capable tool to locate the actual document.
- Where a company's GRI/sustainability content is embedded as a chapter within a broader Annual (General) Report rather than published standalone, the `notes` field says so explicitly and `additional_source_urls` links the standalone extract where one exists.

Going forward, new contributions should aim for `downloadable_pdf` wherever one exists, and only fall back to a landing page when a company genuinely doesn't publish one.

## Legacy / historical reports

Right now the dataset captures one snapshot (most recent report year) per company. A natural next step is a `report_year` history — linking prior years' reports (2021, 2022, 2023...) per company so the dataset can show trajectory: is a company's GRI coverage widening or shrinking, is assurance being added or dropped, is the company migrating from GRI to ESRS/CSRD (a pattern that shows up constantly in this dataset already). This would probably mean a separate `historical_reports.csv` keyed by `company_name` + `report_year`, rather than widening the main table.

## Community contribution workflow (Wikipedia-style verification)

Currently every row is either "unverified — pending manual review" or has been checked via the Gemini extraction pipeline. A community version of this project would need a lightweight way for outside contributors to submit or correct a report link, with some equivalent of Wikipedia's "citation needed" / edit-history model: who added a source, when, and what changed. At minimum this could be a `CONTRIBUTING.md` process (PR with a source URL + one-line justification); at most, a small review queue. Not building the infrastructure now, just flagging the need.

## Benchmarking / gap analysis — reference: Muuvment IQ

[Muuvment IQ](https://www.muuvment.com/iq) is an existing commercial tool worth knowing about as a reference point: it lets a company upload its own sustainability documentation and get an AI-driven gap analysis against up to 10 competitors across 70+ ESG factors, benchmarked against GRI/CSRD/ISSB/SASB frameworks, with each analysis validated by a human sustainability expert.

This dataset is a different thing — a public, CC0 record of *whether and how* companies report against GRI Standards, not a paid benchmarking service — but the comparison is useful context for where this could go if the community angle takes off: once there's a critical mass of verified companies, cross-company comparison (which sectors/countries have the strongest GRI coverage, common gaps in topic-standard reporting, etc.) becomes possible using this data as the input, without needing to replicate Muuvment's product itself.
