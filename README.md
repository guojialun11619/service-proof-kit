# Offline service proof kit

Two deterministic, zero-dependency Python tools demonstrate bounded digital-service delivery with inspectable evidence.

## Included tools

- `bedrock-audit/`: read-only structural audits for Minecraft Bedrock `.mcpack` and `.mcaddon` files, including nested packs, manifest validation, dependency wiring, script entry checks, unsafe paths and packaging junk.
- `csv-cleanup/`: rule-based CSV cleanup with exact deduplication, preserved blank keys, formula-like-cell flags, SHA-256 receipts and a JSON change report.

Each folder contains a small input and the corresponding report/output so the delivery format can be inspected without uploading any data.

The test suite contains 17 automated tests. The tools never claim facts they cannot verify: a structural Bedrock pass is not presented as universal in-game compatibility, and ambiguous CSV values are flagged rather than guessed.

## Verify

Python 3.9 or newer is enough:

```bash
python3 -m unittest discover -s bedrock-audit -p 'test_*.py' -v
python3 -m unittest discover -s csv-cleanup -p 'test_*.py' -v
```

GitHub Actions runs the same checks on Python 3.9, 3.11 and 3.13.

## Service inquiry

Use the repository's service-inquiry form for a public, non-sensitive scope question. Do not attach client data, secrets, credentials, payment details, or personal information to a public issue. An inquiry is not an order until scope, timing, acceptance criteria and payment terms are agreed in writing.

## Service boundaries

The code is a public proof sample, not a promise of results on untested devices or datasets. Client work should begin only after scope, acceptance criteria, data sensitivity and payment terms are agreed in writing.

## License

MIT.
