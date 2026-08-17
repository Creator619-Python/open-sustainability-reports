# submissions/

This is where new/updated sustainability sources are proposed, reviewed, and
merged. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for the full process.

- `TEMPLATE.json` - copy this to start a new submission.
- `pending/` - open submissions awaiting review. One file per submission.
  Validated automatically by CI on every PR (`validate_submission.py`).
- `archive/` - submissions that have already been merged into
  `eu_sustainability_sources_v5.json` (by `merge_submissions.py`), kept for
  audit history. Do not edit files here.

Do not edit `eu_sustainability_sources_v5.json` directly in a submission PR
- CI will reject it. Propose changes as a file here instead.
