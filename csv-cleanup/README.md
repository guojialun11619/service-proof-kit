# Quick Data Rescue

A deterministic first-pass CSV cleanup tool for a tightly bounded paid pilot. It trims cell whitespace, normalizes explicit blank tokens, removes exact normalized duplicates on an agreed non-blank key, preserves blank-key rows, flags spreadsheet-formula-like cells, and writes a complete JSON change report with SHA-256 hashes.

## Run

```bash
python3 csv_cleanup.py input.csv clean.csv --report change-report.json --dedupe-on email
```

No values are fuzzy-matched or inferred. Dates, phone numbers, names, and types are left untouched unless the client agrees to a separate rule.

## Test

```bash
python3 -m unittest -v
```

No third-party packages are required.

Use `CLIENT_INTAKE.md` to lock the duplicate key, blank tokens, locale, sensitive-data boundary, and acceptance examples before receiving a real file. Use `DELIVERY_TEMPLATE.md` to reconcile counts, flags, hashes, and retention status without overstating the result.
