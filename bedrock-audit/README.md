# Bedrock Add-on Audit

Offline, read-only structural validation for Minecraft Bedrock `.mcpack`, `.mcaddon`, and ZIP archives.

## Run

```bash
python3 bedrock_audit.py MyAddon.mcaddon \
  --markdown audit-report.md \
  --json audit-report.json
```

Exit code `0` means no structural errors were found. Exit code `1` means the report contains at least one error.

## Checks

- ZIP integrity and unsafe archive paths
- manifest JSON and UTF-8 encoding
- manifest format, header, UUID, and semantic version shapes
- module UUIDs, types, and versions
- missing script entry files
- dependencies bundled in a multi-pack add-on
- nested `.mcpack` or `.zip` packs inside a `.mcaddon`
- duplicate UUIDs across bundled packs
- missing icons and OS metadata/junk

The tool does not alter the input file. In-game testing on the target Bedrock version/device is still required for a complete compatibility claim.

## Test

```bash
python3 -m unittest -v
```

No third-party Python packages are required.
