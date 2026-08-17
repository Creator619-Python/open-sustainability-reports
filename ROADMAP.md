# Roadmap

Ideas for evolving this from a pilot dataset into a community-maintained resource. Nothing here is committed to a timeline — this is a working list.

## ✅ Done as of v0.5: multi-source-per-company schema + submission workflow

Two items that used to live in this roadmap as open ideas are now shipped:

- **Legacy / historical reports** — `sustainability_sources` is an array per company, and each entry has `is_legacy: true/false`, so a company can carry both its current source(s) and older ones kept for progress tracking (report_year over report_year, is coverage widening, is the company migrating from GRI to ESRS/CSRD) instead of being overwritten each time. See `MIGRATION_NOTES.md`.
- **Community contribution workflow (Wikipedia-style verification)** — `CONTRIBUTING.md` + `submissions/` + `validate_submission.py` + `merge_submissions.py` implement a propose -> automated-check -> human-review -> merge flow, with an audit trail (`submissions/archive/`) of who submitted and who approved each entry.

## Next up

- **Update `gemini_gri_extractor.py` for the v0.5 schema.** It currently reads `all_487_report_sources.csv` (the old flat manifest) and writes verification fields that no longer have a home in `sustainability_sources` entries in the same shape. Needs to be re-pointed at `eu_sustainability_sources_v5.json`, verifying each entry's `report_url` / `parent_document_url` (as appropriate to `source_type`) and writing results into that entry's `frameworks_referenced` / `notes` instead of a separate CSV row.
- **`tools/archive_snapshot.py`** — walk all `webpage`-type entries and request/record a Wayback Machine snapshot into `archive_url`. Deliberately not built as part of the migration itself (108 live outbound requests should be rate-limited and reviewed, not fired blind from a batch script).
- **Backfill `retrieved_date`** for the 108 migrated `webpage` entries where it's currently `null` (the original research didn't record per-row retrieval timestamps). Likely needs a re-verification pass rather than a guess.

## Source quality: downloadable documents over landing pages

`sustainability_sources` entries come in three kinds via `source_type`:

- `downloadable_report` — a direct link to the actual standalone report file. This is the strong case: verifiers and tools like Gemini's `url_context` can read the primary document directly.
- `agr_section` — the sustainability content is embedded as a section/chapter within a broader Annual General Report rather than published standalone; `parent_document_url` + `section_reference` say where to look.
- `webpage` — no single downloadable file could be confirmed; the entry points to the company's reporting hub instead (e.g. some companies' disclosures live only on a webpage, not a PDF). `archive_url` should carry a Wayback Machine snapshot so the citation survives page changes.

Going forward, new contributions should aim for `downloadable_report` wherever one genuinely exists, and only fall back to `webpage` when a company doesn't publish a standalone document.

## Benchmarking / gap analysis — reference: Muuvment IQ

[Muuvment IQ](https://www.muuvment.com/iq) is an existing commercial tool worth knowing about as a reference point: it lets a company upload its own sustainability documentation and get an AI-driven gap analysis against up to 10 competitors across 70+ ESG factors, benchmarked against GRI/CSRD/ISSB/SASB frameworks, with each analysis validated by a human sustainability expert.

This dataset is a different thing — a public, CC0 record of *whether and how* companies report against GRI Standards, not a paid benchmarking service — but the comparison is useful context for where this could go if the community angle takes off: once there's a critical mass of verified companies, cross-company comparison (which sectors/countries have the strongest GRI coverage, common gaps in topic-standard reporting, etc.) becomes possible using this data as the input, without needing to replicate Muuvment's product itself.
