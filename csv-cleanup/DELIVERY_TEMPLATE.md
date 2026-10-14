# CSV cleanup delivery — [project name]

## Result

- Status: [completed / completed with exceptions / blocked]
- Input SHA-256: `[hash]`
- Output SHA-256: `[hash]`
- Rows in: [count]
- Rows out: [count]
- Duplicate key: [column(s) or full row]

## Agreed rules

1. [rule with a before/after example]
2. [rule with a before/after example]
3. [rule with a before/after example]

## Reconciliation

- Cells trimmed: [count]
- Explicit blank tokens normalized: [count]
- Exact duplicates removed: [count]
- Formula-like cells flagged: [count]
- Rows requiring client review: [count]

The totals above should reconcile to the attached JSON report. No fuzzy matching or inference was performed unless separately listed and approved.

## Files

- `clean.csv` — deterministic output
- `change-report.json` — hashes, row counts, changes, and flags
- `exceptions.csv` or `exceptions.md` — ambiguous or excluded cases, if any

## Retention / deletion

[State the agreed retention deadline and deletion confirmation process. Do not claim deletion before it occurs.]
