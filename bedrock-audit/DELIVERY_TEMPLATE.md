# Delivery — [project name]

## Result

- Status: [audited / repaired / requires in-game verification]
- Original file hash: `[SHA-256]`
- Delivered file hash: `[SHA-256 or N/A]`
- Target Bedrock version/device: [version/device]

## Work completed

1. [finding or change]
2. [finding or change]
3. [finding or change]

## Verification

- Structural audit: [PASS / PASS_WITH_WARNINGS / FAIL]
- Automated tests: [command and result]
- In-game test: [version/device/result, or NOT PERFORMED]

## Files

- `audit-report.md` — readable findings and limitations
- `audit-report.json` — machine-readable findings
- `[patched-file].mcaddon` — patched copy, if repair was included
- `CHANGELOG.md` — exact changes, if repair was included

## Install / rollback

1. Back up the world.
2. Remove or disable the previously imported repaired copy if it has the same UUID/version.
3. Import the delivered archive.
4. Activate packs in the documented order.
5. If a regression occurs, deactivate the delivered pack and restore the original/world backup.

## Limitations

[List what was not tested. Never imply broad compatibility from one structural or device test.]
