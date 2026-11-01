#!/usr/bin/env python3
"""Package the addon and publish it to CurseForge.

Runs inside the Release workflow; standard library only so the runner needs no
setup. Nothing here is addon code — it only reads the TOC files.

The addon version comes from ## Version in GetInfoScan.toc; the tag only
decides whether the file is published as alpha, beta or release.

    python3 .github/scripts/curseforge_release.py --tag v1.4.0 --changelog dist/changelog.md

Exit code 0 means the file is on CurseForge. Anything else fails the workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

ADDON = "GetInfoScan"
PROJECT_ID = int(os.environ.get("CF_PROJECT_ID", "1734764"))
API_BASE = os.environ.get("CF_API_BASE", "https://wow.curseforge.com").rstrip("/")

# Interface -> CurseForge game version type id. Same table as BigWigsMods/packager.
# Titan Reforged lives on its own type even though it reuses the 3.x client.
GAME_VERSION_TYPES = (
    (re.compile(r"380\d\d"), 81212, "Titan Reforged"),
    (re.compile(r"16\d\d\d"), 88568, "Classic Era (Forever)"),
    (re.compile(r"11\d\d\d"), 67408, "Classic Era"),
    (re.compile(r"20\d\d\d"), 73246, "TBC Classic"),
    (re.compile(r"30\d\d\d"), 73713, "Wrath Classic"),
    (re.compile(r"40\d\d\d"), 77522, "Cata Classic"),
    (re.compile(r"50\d\d\d"), 79434, "Mists Classic"),
)
RETAIL_TYPE = 517

# Shipped in the zip: everything except repo plumbing.
SKIP_DIRS = {".git", ".github", ".vscode", "__pycache__"}
SKIP_FILES = {".gitignore", ".gitattributes", ".DS_Store", "Thumbs.db"}


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str):
    print(f"::error::{msg}", flush=True)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Repo inspection
# --------------------------------------------------------------------------- #

def read_tocs(root: Path) -> list[dict]:
    """Return one entry per root-level *.toc with its Interface and Version."""
    tocs = []
    for path in sorted(root.glob("*.toc")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        interface = re.search(r"^##\s*Interface\s*:\s*([\d,\s]+)", text, re.M)
        version = re.search(r"^##\s*Version\s*:\s*(\S+)", text, re.M)
        if not interface:
            continue
        tocs.append(
            {
                "name": path.name,
                "interfaces": [int(v) for v in interface.group(1).replace(" ", "").split(",") if v],
                "version": version.group(1) if version else None,
            }
        )
    if not tocs:
        fail(f"no *.toc with an ## Interface line found in {root}")
    return tocs


VERSION_TOC = "GetInfoScan.toc"


def pick_version(tocs: list[dict]) -> str:
    """The addon version is whatever ## Version says in GetInfoScan.toc.

    You bump that line yourself before tagging; the tag only decides whether
    the file goes out as alpha, beta or release.
    """
    for toc in tocs:
        if toc["name"] == VERSION_TOC:
            if toc["version"]:
                return toc["version"]
            fail(f"{VERSION_TOC} has no ## Version line")
    fail(f"{VERSION_TOC} is missing; it holds the addon version")


def release_type(tag: str | None) -> str:
    lowered = (tag or "").lower()
    if "alpha" in lowered:
        return "alpha"
    if "beta" in lowered:
        return "beta"
    return "release"


# --------------------------------------------------------------------------- #
# Zip
# --------------------------------------------------------------------------- #

def build_zip(root: Path, version: str, out_dir: Path) -> Path:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{ADDON}-{version}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if rel.parts and rel.parts[0] in SKIP_FILES:
                continue
            if path.is_dir() or path == target or out_dir in path.parents:
                continue
            # The game expects <AddOns>/GetInfoScan/... inside the archive.
            zf.write(path, f"{ADDON}/{rel.as_posix()}")
    log(f"built {target} ({target.stat().st_size} bytes)")
    return target


# --------------------------------------------------------------------------- #
# CurseForge
# --------------------------------------------------------------------------- #

def api_json(path: str, token: str) -> dict | list:
    req = urllib.request.Request(f"{API_BASE}{path}", headers={"X-Api-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(f"GET {path} -> HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:800]}")
    except urllib.error.URLError as exc:
        fail(f"GET {path} failed: {exc.reason}")


def resolve_game_versions(tocs: list[dict], token: str) -> list[int]:
    """Map every ## Interface in the repo to a CurseForge game version id."""
    versions = api_json("/api/game/wow/versions", token)
    if not isinstance(versions, list):
        fail(f"unexpected /api/game/wow/versions payload: {str(versions)[:400]}")

    wanted = []
    for toc in tocs:
        for interface in toc["interfaces"]:
            type_id, label = RETAIL_TYPE, "Retail"
            for pattern, candidate, candidate_label in GAME_VERSION_TYPES:
                if pattern.fullmatch(str(interface)):
                    type_id, label = candidate, candidate_label
                    break
            wanted.append((interface, type_id, label))

    resolved: list[int] = []
    for interface, type_id, label in wanted:
        major, minor, patch = interface // 10000, (interface // 100) % 100, interface % 100
        name = f"{major}.{minor}.{patch}"
        pool = [v for v in versions if v.get("gameVersionTypeID") == type_id]
        exact = [v for v in pool if v.get("name") == name]
        if exact:
            chosen = exact[0]
        elif pool:
            chosen = max(pool, key=lambda v: v.get("id", 0))
            log(
                f"::warning::no CurseForge {label} version named {name} "
                f"(Interface {interface}); using {chosen.get('name')}"
            )
        else:
            fail(f"CurseForge has no game versions for {label} (type id {type_id})")
        log(f"Interface {interface} -> {label} {chosen.get('name')} (id {chosen.get('id')})")
        if chosen["id"] not in resolved:
            resolved.append(chosen["id"])

    if not resolved:
        fail("resolved no CurseForge game versions")
    return resolved


def upload(archive: Path, metadata: dict, token: str) -> int:
    boundary = f"----dsh{uuid.uuid4().hex}"
    body = bytearray()

    def field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    field("metadata", json.dumps(metadata, ensure_ascii=False))
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{archive.name}"\r\n'.encode()
    )
    body.extend(b"Content-Type: application/zip\r\n\r\n")
    body.extend(archive.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    url = f"{API_BASE}/api/projects/{PROJECT_ID}/upload-file"
    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "X-Api-Token": token,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        fail(f"CurseForge upload failed: HTTP {exc.code}\n{detail[:2000]}")
    except urllib.error.URLError as exc:
        fail(f"CurseForge upload failed: {exc.reason}")

    try:
        file_id = int(json.loads(raw)["id"])
    except (ValueError, KeyError, TypeError):
        fail(f"CurseForge upload returned an unexpected body: {raw[:800]}")
    return file_id


# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="release tag, used only to pick alpha/beta/release")
    parser.add_argument("--changelog", help="file holding the changelog text")
    parser.add_argument("--changelog-type", default="markdown", choices=("text", "html", "markdown"))
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--out-dir", default="dist", help="where to write the zip")
    parser.add_argument(
        "--expect-version",
        help="fail unless GetInfoScan.toc says this version (the tag's version)",
    )
    parser.add_argument("--dry-run", action="store_true", help="build the zip and stop")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    token = os.environ.get("CURSEFORGE_TOKEN", "").strip()

    tocs = read_tocs(root)
    version = pick_version(tocs)
    kind = release_type(args.tag)

    if args.expect_version and args.expect_version != version:
        fail(
            f"tag says {args.expect_version} but {VERSION_TOC} says {version}; "
            f"bump ## Version first, then tag"
        )

    changelog = ""
    if args.changelog and Path(args.changelog).is_file():
        changelog = Path(args.changelog).read_text(encoding="utf-8", errors="replace").strip()
    if not changelog:
        changelog = f"{ADDON} {version}"

    display_name = f"{ADDON} {version}"
    log(f"version={version} releaseType={kind} displayName={display_name!r}")

    archive = build_zip(root, version, Path(args.out_dir))
    if args.dry_run:
        log("dry run: not uploading")
        return 0

    if not token:
        fail("CURSEFORGE_TOKEN is empty; add the repository secret before publishing")

    metadata = {
        "displayName": display_name,
        "releaseType": kind,
        "changelog": changelog,
        "changelogType": args.changelog_type,
        "gameVersions": resolve_game_versions(tocs, token),
    }
    file_id = upload(archive, metadata, token)

    log(f"::notice::CurseForge file {file_id} published")
    log(f"https://www.curseforge.com/wow/addons/getinfoscan/files/{file_id}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(
                f"### CurseForge\n\n"
                f"- project: `{PROJECT_ID}`\n"
                f"- file id: `{file_id}`\n"
                f"- release type: `{kind}`\n"
                f"- game versions: `{metadata['gameVersions']}`\n"
                f"- https://www.curseforge.com/wow/addons/getinfoscan/files/{file_id}\n"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
