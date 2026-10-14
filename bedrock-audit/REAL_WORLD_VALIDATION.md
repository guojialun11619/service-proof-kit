# Real-world validation note

The auditor was exercised against the public repository [`Davis8483/MCBE-Shovel-Land-Claim`](https://github.com/Davis8483/MCBE-Shovel-Land-Claim) at commit `4e286d24c5fb0f7ada13363ae7c83c577322f01e`.

Method:

1. Clone the public source checkout.
2. Package its `BP/` and `RP/` trees while excluding development-only `node_modules`, TypeScript sources, package manifests, and `.gitkeep` files.
3. Run `bedrock_audit.py` against the resulting `.mcaddon`.

Result: the tool detected both bundled packs, resolved their mutual UUID dependencies, and reported one concrete source-checkout packaging error: the behavior-pack manifest declares `scripts/main.js`, while the checkout contains `BP/dist/scripts/main.ts` and no bundled `scripts/main.js`.

The official `v1.0.6` release archive was then downloaded from GitHub and audited separately. That `.mcaddon` contains nested `BP.zip` and `RP.zip` packs; this exposed a false negative in the first implementation, which was fixed with safe nested-pack inspection and a regression test. The final audit detects two packs, resolves their mutual dependencies, and grades the official release **PASS** with zero findings.

This validates the checker against a non-trivial public release layout. It does not prove gameplay behavior or compatibility beyond the structural checks. No upstream issue or pull request was opened, and no project files were modified.
