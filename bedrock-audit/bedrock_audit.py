#!/usr/bin/env python3
"""Offline validator for Minecraft Bedrock .mcpack/.mcaddon archives.

The tool never modifies the input. It emits a human-readable Markdown report
and an optional JSON report suitable for a client handoff.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ALLOWED_SUFFIXES = {".mcpack", ".mcaddon", ".zip"}
JUNK_PARTS = {"__MACOSX", ".DS_Store", "Thumbs.db"}
PACK_TYPE_NAMES = {"resources": "resource", "data": "behavior", "script": "script"}


@dataclass
class Finding:
    severity: str
    code: str
    location: str
    message: str
    remediation: str = ""


@dataclass
class Pack:
    root: str
    name: str
    uuid: str | None
    version: list[int] | None
    module_types: list[str]
    min_engine_version: list[int] | None
    dependency_uuids: list[str]


def finding(severity: str, code: str, location: str, message: str, remediation: str = "") -> Finding:
    return Finding(severity, code, location or ".", message, remediation)


def valid_version(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(item, int) and item >= 0 for item in value)
    )


def valid_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def safe_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return (
        "\x00" not in name
        and not path.is_absolute()
        and ".." not in path.parts
        and re.match(r"^[A-Za-z]:/", normalized) is None
    )


def discover_manifests(names: Iterable[str]) -> list[str]:
    return sorted(name for name in names if PurePosixPath(name).name == "manifest.json")


def get_root(manifest_path: str) -> str:
    parent = str(PurePosixPath(manifest_path).parent)
    return "" if parent == "." else parent.rstrip("/") + "/"


def read_json(zf: zipfile.ZipFile, path: str, findings: list[Finding]) -> dict[str, Any] | None:
    try:
        raw = zf.read(path)
        parsed = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(parsed, dict):
            findings.append(finding("ERROR", "MANIFEST_SHAPE", path, "Manifest root must be a JSON object."))
            return None
        return parsed
    except UnicodeDecodeError as exc:
        findings.append(finding("ERROR", "MANIFEST_ENCODING", path, f"Manifest is not UTF-8: {exc}", "Save it as UTF-8 without binary data."))
    except json.JSONDecodeError as exc:
        findings.append(finding("ERROR", "MANIFEST_JSON", path, f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}", "Repair the JSON syntax and re-run the audit."))
    except KeyError:
        findings.append(finding("ERROR", "MANIFEST_MISSING", path, "Manifest disappeared while reading the archive."))
    return None


def validate_manifest(data: dict[str, Any], path: str, root: str, names: set[str], findings: list[Finding]) -> Pack:
    fmt = data.get("format_version")
    if fmt not in (1, 2):
        findings.append(finding("ERROR", "FORMAT_VERSION", path, f"Unsupported or missing format_version: {fmt!r}", "Use manifest format_version 2 for current packs."))

    header = data.get("header")
    if not isinstance(header, dict):
        findings.append(finding("ERROR", "HEADER_MISSING", path, "header must be an object."))
        header = {}

    name = header.get("name")
    if not isinstance(name, str) or not name.strip():
        findings.append(finding("ERROR", "HEADER_NAME", path, "header.name is missing or empty."))
        name = "Unnamed pack"

    pack_uuid = header.get("uuid")
    if not valid_uuid(pack_uuid):
        findings.append(finding("ERROR", "HEADER_UUID", path, f"header.uuid is invalid: {pack_uuid!r}", "Generate a UUID v4; do not reuse another pack's UUID."))
        pack_uuid = None

    version = header.get("version")
    if not valid_version(version):
        findings.append(finding("ERROR", "HEADER_VERSION", path, f"header.version must be [major, minor, patch], got {version!r}."))
        version = None

    mev = header.get("min_engine_version")
    if mev is not None and not valid_version(mev):
        findings.append(finding("ERROR", "MIN_ENGINE_VERSION", path, f"min_engine_version must be a 3-integer array, got {mev!r}."))
        mev = None
    elif mev is None:
        findings.append(finding("WARN", "MIN_ENGINE_VERSION_MISSING", path, "min_engine_version is missing.", "Declare the oldest Bedrock version actually tested."))

    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        findings.append(finding("ERROR", "MODULES_MISSING", path, "modules must be a non-empty array."))
        modules = []

    module_types: list[str] = []
    seen_module_uuids: set[str] = set()
    for idx, module in enumerate(modules):
        loc = f"{path}:modules[{idx}]"
        if not isinstance(module, dict):
            findings.append(finding("ERROR", "MODULE_SHAPE", loc, "Module must be an object."))
            continue
        module_type = module.get("type")
        if not isinstance(module_type, str):
            findings.append(finding("ERROR", "MODULE_TYPE", loc, "Module type is missing."))
        else:
            module_types.append(module_type)
        module_uuid = module.get("uuid")
        if not valid_uuid(module_uuid):
            findings.append(finding("ERROR", "MODULE_UUID", loc, f"Invalid module UUID: {module_uuid!r}."))
        elif module_uuid in seen_module_uuids or module_uuid == pack_uuid:
            findings.append(finding("ERROR", "DUPLICATE_UUID", loc, f"UUID {module_uuid} is reused within the manifest.", "Give every header and module a distinct UUID v4."))
        else:
            seen_module_uuids.add(module_uuid)
        if not valid_version(module.get("version")):
            findings.append(finding("ERROR", "MODULE_VERSION", loc, f"Module version must be [major, minor, patch], got {module.get('version')!r}."))
        if module_type == "script":
            entry = module.get("entry")
            if not isinstance(entry, str) or not entry.strip():
                findings.append(finding("ERROR", "SCRIPT_ENTRY", loc, "Script module has no entry path."))
            else:
                archive_entry = root + entry.lstrip("/")
                if archive_entry not in names:
                    findings.append(finding("ERROR", "SCRIPT_ENTRY_MISSING", loc, f"Script entry {entry!r} is not present in the archive.", "Fix the entry path or include the built script."))

    dependencies = data.get("dependencies", [])
    dependency_uuids: list[str] = []
    if not isinstance(dependencies, list):
        findings.append(finding("ERROR", "DEPENDENCIES_SHAPE", path, "dependencies must be an array."))
        dependencies = []
    for idx, dep in enumerate(dependencies):
        loc = f"{path}:dependencies[{idx}]"
        if not isinstance(dep, dict):
            findings.append(finding("ERROR", "DEPENDENCY_SHAPE", loc, "Dependency must be an object."))
            continue
        if "uuid" in dep:
            dep_uuid = dep.get("uuid")
            if not valid_uuid(dep_uuid):
                findings.append(finding("ERROR", "DEPENDENCY_UUID", loc, f"Invalid dependency UUID: {dep_uuid!r}."))
            else:
                dependency_uuids.append(dep_uuid)
            if not valid_version(dep.get("version")):
                findings.append(finding("ERROR", "DEPENDENCY_VERSION", loc, f"Dependency version must be [major, minor, patch], got {dep.get('version')!r}."))
        elif "module_name" not in dep:
            findings.append(finding("WARN", "DEPENDENCY_UNKNOWN", loc, "Dependency has neither uuid nor module_name."))

    icon = root + "pack_icon.png"
    if icon not in names:
        findings.append(finding("INFO", "PACK_ICON_MISSING", path, "pack_icon.png is missing; Minecraft will use a default icon."))

    return Pack(root=root or ".", name=name, uuid=pack_uuid, version=version, module_types=module_types, min_engine_version=mev, dependency_uuids=dependency_uuids)


def audit(path: Path) -> dict[str, Any]:
    findings: list[Finding] = []
    packs: list[Pack] = []
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        findings.append(finding("WARN", "EXTENSION", str(path), f"Unexpected extension {path.suffix!r}; treating the file as ZIP."))
    if not path.is_file():
        return {"input": str(path), "valid_zip": False, "packs": [], "findings": [asdict(finding("ERROR", "INPUT_MISSING", str(path), "Input file does not exist."))], "summary": {"ERROR": 1, "WARN": 0, "INFO": 0}, "grade": "FAIL"}
    if not zipfile.is_zipfile(path):
        return {"input": str(path), "valid_zip": False, "packs": [], "findings": [asdict(finding("ERROR", "NOT_ZIP", str(path), "Input is not a valid ZIP-based pack archive."))], "summary": {"ERROR": 1, "WARN": 0, "INFO": 0}, "grade": "FAIL"}

    def scan_zip(zf: zipfile.ZipFile, container: str = "", depth: int = 0) -> None:
        names_list = zf.namelist()
        names = set(names_list)
        for name in names_list:
            shown = f"{container}{name}"
            if not safe_member(name):
                findings.append(finding("ERROR", "UNSAFE_PATH", shown, "Archive contains an absolute or parent-traversal path.", "Remove the unsafe entry and rebuild the archive."))
            if any(part in JUNK_PARTS or part.startswith("._") for part in PurePosixPath(name).parts):
                findings.append(finding("WARN", "JUNK_FILE", shown, "Archive contains OS metadata/junk.", "Remove it before client delivery."))
        manifests = discover_manifests(names_list)
        for manifest in manifests:
            local_findings: list[Finding] = []
            data = read_json(zf, manifest, local_findings)
            for item in local_findings:
                item.location = f"{container}{item.location}"
                findings.append(item)
            if data is not None:
                local_findings = []
                pack = validate_manifest(data, manifest, get_root(manifest), names, local_findings)
                pack.root = container if container and pack.root == "." else f"{container}{pack.root}"
                packs.append(pack)
                for item in local_findings:
                    item.location = f"{container}{item.location}"
                    findings.append(item)

        nested = [name for name in names_list if name.lower().endswith((".mcpack", ".zip")) and not name.endswith("/")]
        if not manifests and nested and depth == 0:
            for member in nested:
                info = zf.getinfo(member)
                if info.file_size > 100 * 1024 * 1024:
                    findings.append(finding("ERROR", "NESTED_PACK_TOO_LARGE", f"{container}{member}", "Nested pack exceeds the 100 MB safety limit."))
                    continue
                try:
                    with zipfile.ZipFile(io.BytesIO(zf.read(member))) as nested_zip:
                        scan_zip(nested_zip, f"{container}{member}!/", depth + 1)
                except zipfile.BadZipFile:
                    findings.append(finding("ERROR", "NESTED_PACK_INVALID", f"{container}{member}", "Nested pack is not a valid ZIP archive."))
        elif not manifests and not nested:
            location = container[:-2] if container.endswith("!/") else str(path)
            findings.append(finding("ERROR", "NO_MANIFEST", location, "No manifest.json was found."))

    with zipfile.ZipFile(path) as zf:
        scan_zip(zf)

    pack_uuids = [pack.uuid for pack in packs if pack.uuid]
    for duplicate in sorted({item for item in pack_uuids if pack_uuids.count(item) > 1}):
        findings.append(finding("ERROR", "CROSS_PACK_UUID", duplicate, "Multiple bundled packs reuse the same header UUID."))
    available = set(pack_uuids)
    for pack in packs:
        for dep in pack.dependency_uuids:
            if dep not in available:
                findings.append(finding("WARN", "UNRESOLVED_DEPENDENCY", pack.root, f"Dependency UUID {dep} is not bundled in this archive.", "Confirm the dependency is installed separately or include the matching pack."))

    counts = {level: sum(item.severity == level for item in findings) for level in ("ERROR", "WARN", "INFO")}
    grade = "FAIL" if counts["ERROR"] else ("PASS_WITH_WARNINGS" if counts["WARN"] else "PASS")
    return {"input": str(path.resolve()), "valid_zip": True, "packs": [asdict(pack) for pack in packs], "findings": [asdict(item) for item in findings], "summary": counts, "grade": grade}


def markdown(report: dict[str, Any]) -> str:
    lines = ["# Minecraft Bedrock Add-on Audit", "", f"- Input: `{report['input']}`", f"- Grade: **{report['grade']}**", f"- Findings: {report['summary']['ERROR']} error(s), {report['summary']['WARN']} warning(s), {report['summary']['INFO']} informational", f"- Packs detected: {len(report['packs'])}", ""]
    if report["packs"]:
        lines.extend(["## Packs", "", "| Name | Root | Header UUID | Version | Modules |", "|---|---|---|---|---|"])
        for pack in report["packs"]:
            lines.append(f"| {pack['name']} | `{pack['root']}` | `{pack['uuid'] or 'invalid'}` | `{pack['version']}` | {', '.join(pack['module_types']) or 'none'} |")
        lines.append("")
    lines.extend(["## Findings", ""])
    if not report["findings"]:
        lines.append("No structural manifest or packaging problems were detected by this audit.")
    else:
        for item in report["findings"]:
            lines.append(f"### {item['severity']} — {item['code']}")
            lines.append(f"- Location: `{item['location']}`")
            lines.append(f"- Detail: {item['message']}")
            if item["remediation"]:
                lines.append(f"- Suggested fix: {item['remediation']}")
            lines.append("")
    lines.extend(["## Scope and limitations", "", "This is an offline structural audit. It does not launch Minecraft, prove gameplay behavior, validate marketplace licensing, or guarantee compatibility with every device or Bedrock release. A production repair should also be tested in-game on the client's target version and device.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a Minecraft Bedrock .mcpack/.mcaddon archive without modifying it.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, help="Write machine-readable report")
    parser.add_argument("--markdown", dest="md_path", type=Path, help="Write client-ready Markdown report")
    args = parser.parse_args()
    report = audit(args.archive)
    rendered = markdown(report)
    if args.json_path:
        args.json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.md_path:
        args.md_path.write_text(rendered, encoding="utf-8")
    if not args.json_path and not args.md_path:
        print(rendered)
    return 1 if report["grade"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
