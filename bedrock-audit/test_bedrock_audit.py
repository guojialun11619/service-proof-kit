from __future__ import annotations

import json
import io
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path

from bedrock_audit import audit


def make_pack(path: Path, manifest: dict, extra: dict[str, bytes] | None = None) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("pack_icon.png", b"png")
        for name, data in (extra or {}).items():
            zf.writestr(name, data)


class AuditTests(unittest.TestCase):
    def base_manifest(self):
        return {
            "format_version": 2,
            "header": {"name": "Test Pack", "description": "Fixture", "uuid": str(uuid.uuid4()), "version": [1, 0, 0], "min_engine_version": [1, 20, 0]},
            "modules": [{"type": "data", "uuid": str(uuid.uuid4()), "version": [1, 0, 0]}],
        }

    def test_valid_pack_passes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "valid.mcpack"
            make_pack(path, self.base_manifest())
            report = audit(path)
            self.assertEqual(report["grade"], "PASS")
            self.assertEqual(report["summary"]["ERROR"], 0)

    def test_duplicate_uuid_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "duplicate.mcpack"
            manifest = self.base_manifest()
            manifest["modules"][0]["uuid"] = manifest["header"]["uuid"]
            make_pack(path, manifest)
            report = audit(path)
            self.assertEqual(report["grade"], "FAIL")
            self.assertIn("DUPLICATE_UUID", {item["code"] for item in report["findings"]})

    def test_missing_script_entry_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "script.mcpack"
            manifest = self.base_manifest()
            manifest["modules"] = [{"type": "script", "language": "javascript", "uuid": str(uuid.uuid4()), "version": [1, 0, 0], "entry": "scripts/main.js"}]
            make_pack(path, manifest)
            report = audit(path)
            self.assertIn("SCRIPT_ENTRY_MISSING", {item["code"] for item in report["findings"]})

    def test_mcaddon_cross_pack_dependency_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "paired.mcaddon"
            behavior = self.base_manifest()
            resource = self.base_manifest()
            resource["header"]["name"] = "Resource Pack"
            resource["modules"][0]["type"] = "resources"
            behavior["dependencies"] = [{"uuid": resource["header"]["uuid"], "version": [1, 0, 0]}]
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("BP/manifest.json", json.dumps(behavior))
                zf.writestr("BP/pack_icon.png", b"png")
                zf.writestr("RP/manifest.json", json.dumps(resource))
                zf.writestr("RP/pack_icon.png", b"png")
            report = audit(path)
            self.assertEqual(report["grade"], "PASS")

    def test_bad_json_fails_without_crash(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.mcpack"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("manifest.json", "{broken")
            report = audit(path)
            self.assertEqual(report["grade"], "FAIL")
            self.assertIn("MANIFEST_JSON", {item["code"] for item in report["findings"]})

    def test_non_object_manifest_fails_without_crash(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "list-root.mcpack"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("manifest.json", "[]")
            report = audit(path)
            self.assertEqual(report["grade"], "FAIL")
            self.assertIn("MANIFEST_SHAPE", {item["code"] for item in report["findings"]})

    def test_unsafe_archive_path_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "unsafe.mcpack"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(self.base_manifest()))
                zf.writestr("../outside.txt", "unsafe")
            report = audit(path)
            self.assertEqual(report["grade"], "FAIL")
            self.assertIn("UNSAFE_PATH", {item["code"] for item in report["findings"]})

    def test_windows_style_traversal_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "unsafe-windows.mcpack"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(self.base_manifest()))
                zf.writestr("..\\outside.txt", "unsafe")
            report = audit(path)
            self.assertEqual(report["grade"], "FAIL")
            self.assertIn("UNSAFE_PATH", {item["code"] for item in report["findings"]})

    def test_unbundled_dependency_warns(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "dependency.mcpack"
            manifest = self.base_manifest()
            manifest["dependencies"] = [{"uuid": str(uuid.uuid4()), "version": [1, 0, 0]}]
            make_pack(path, manifest)
            report = audit(path)
            self.assertEqual(report["grade"], "PASS_WITH_WARNINGS")
            self.assertIn("UNRESOLVED_DEPENDENCY", {item["code"] for item in report["findings"]})

    def test_nested_mcpack_archives_are_inspected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            addon = root / "nested.mcaddon"
            behavior = self.base_manifest()
            resource = self.base_manifest()
            resource["header"]["name"] = "Nested Resource Pack"
            resource["modules"][0]["type"] = "resources"
            behavior["dependencies"] = [{"uuid": resource["header"]["uuid"], "version": [1, 0, 0]}]
            resource["dependencies"] = [{"uuid": behavior["header"]["uuid"], "version": [1, 0, 0]}]

            def nested_bytes(manifest):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w") as nested:
                    nested.writestr("manifest.json", json.dumps(manifest))
                    nested.writestr("pack_icon.png", b"png")
                return buffer.getvalue()

            with zipfile.ZipFile(addon, "w") as outer:
                outer.writestr("behavior.mcpack", nested_bytes(behavior))
                outer.writestr("resource.zip", nested_bytes(resource))
            report = audit(addon)
            self.assertEqual(report["grade"], "PASS")
            self.assertEqual(len(report["packs"]), 2)
            self.assertTrue(all((".mcpack!/" in pack["root"] or ".zip!/" in pack["root"]) for pack in report["packs"]))


if __name__ == "__main__":
    unittest.main()
