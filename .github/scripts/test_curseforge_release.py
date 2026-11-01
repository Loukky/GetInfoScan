#!/usr/bin/env python3
"""Offline check for curseforge_release.py — fake CurseForge server, no token.

    python .github/scripts/test_curseforge_release.py

Exercises the parts that silently break a release: Interface -> game version
mapping, version/releaseType selection, the multipart body, and the failure path.
"""

import importlib.util
import json
import os
import sys
import shutil
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cfr", HERE / "curseforge_release.py")
cfr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfr)

# id order mirrors CurseForge: newer versions get higher ids
VERSIONS = [
    {"id": 1, "gameVersionTypeID": 81212, "name": "3.80.1"},
    {"id": 2, "gameVersionTypeID": 81212, "name": "3.80.2"},
    {"id": 10, "gameVersionTypeID": 67408, "name": "1.15.9"},
    {"id": 20, "gameVersionTypeID": 73246, "name": "2.5.6"},
    {"id": 40, "gameVersionTypeID": 77522, "name": "4.4.2"},
    {"id": 50, "gameVersionTypeID": 79434, "name": "5.5.4"},
    {"id": 60, "gameVersionTypeID": 88568, "name": "1.16.1"},
    {"id": 70, "gameVersionTypeID": 517, "name": "12.1.0"},
]

seen = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        assert self.headers["X-Api-Token"] == "tok", "token header missing on GET"
        body = json.dumps(VERSIONS).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        seen["path"] = self.path
        seen["token"] = self.headers["X-Api-Token"]
        seen["ctype"] = self.headers["Content-Type"]
        seen["body"] = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"id": 987654}')


class Rejecting(Handler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(403)
        self.end_headers()
        self.wfile.write(b'{"error":"bad token"}')


def serve(handler):
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_port}"


def make_repo(root: Path) -> None:
    """Minimal stand-in for the addon repo, with the same TOC set."""
    tocs = {
        "GetInfoScan.toc": "120100",
        "GetInfoScan_Wrath.toc": "38002",
        "GetInfoScan_Vanilla.toc": "11509",
        "GetInfoScan_TBC.toc": "20506",
        "GetInfoScan_Cata.toc": "40402",
        "GetInfoScan_Mists.toc": "50504",
        "GetInfoScan_Forever.toc": "16001",
    }
    for name, interface in tocs.items():
        (root / name).write_text(
            f"## Interface: {interface}\n## Version: 1.4.0\n## Author: Loukky\n\nCore.lua\n",
            encoding="utf-8",
        )
    (root / "Core.lua").write_text("-- addon\n", encoding="utf-8")
    (root / "Libs").mkdir()
    (root / "Libs" / "LibStub.lua").write_text("-- lib\n", encoding="utf-8")
    (root / ".github").mkdir()
    (root / ".gitignore").write_text("dist/\n", encoding="utf-8")
    (root / ".vscode").mkdir()


def main() -> int:
    cfr.API_BASE = serve(Handler)
    # Plain makedirs, not mkdtemp: mkdtemp's 0700 mode can trip restricted
    # filesystems, and this repo lives on one.
    root = Path.cwd() / "_cfselftest"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    make_repo(root)
    tocs = cfr.read_tocs(root)
    assert len(tocs) == 7, len(tocs)

    # Interface -> game version id, one per TOC.
    ids = cfr.resolve_game_versions(tocs, "tok")
    assert sorted(ids) == [2, 10, 20, 40, 50, 60, 70], ids
    print("game versions ->", ids)

    # An interface CurseForge has never seen falls back to the newest of its type.
    unknown = [{"name": "x.toc", "interfaces": [38099], "version": "9"}]
    assert cfr.resolve_game_versions(unknown, "tok") == [2], "fallback must pick the newest titan version"
    print("unknown interface -> newest titan version ok")

    # Version + release type.
    assert cfr.pick_version("v1.4.0", tocs) == "1.4.0"
    assert cfr.pick_version(None, tocs) == "1.4.0", "TOC fallback"
    assert cfr.release_type("v1.4.0") == "release"
    assert cfr.release_type("v1.4.0-beta.2") == "beta"
    assert cfr.release_type("v2.0.0-alpha") == "alpha"
    assert cfr.release_type(None) == "release"
    print("version/releaseType ok")

    # Zip layout: everything under GetInfoScan/, no repo plumbing.
    archive = cfr.build_zip(root, "1.4.0", root / "dist")
    names = zipfile.ZipFile(archive).namelist()
    assert "GetInfoScan/Core.lua" in names, names
    assert "GetInfoScan/Libs/LibStub.lua" in names, names
    assert not [n for n in names if ".git" in n or ".vscode" in n or n.startswith("GetInfoScan/dist")], names
    print("zip layout ok ->", names)

    # Upload.
    meta = {
        "displayName": "GetInfoScan 1.4.0",
        "releaseType": "release",
        "changelog": "中文 | 管道符\n- second line",
        "changelogType": "markdown",
        "gameVersions": ids,
    }
    assert cfr.upload(archive, meta, "tok") == 987654
    assert seen["path"] == "/api/projects/1734764/upload-file", seen["path"]
    assert seen["token"] == "tok"
    assert seen["ctype"].startswith("multipart/form-data; boundary=")
    boundary = seen["ctype"].split("boundary=", 1)[1].encode()
    body = seen["body"]
    assert body.count(b"--" + boundary) == 3, "two fields + closing marker"
    assert b'name="metadata"' in body and b'name="file"' in body
    assert archive.read_bytes() in body, "zip payload corrupted"
    head = body.split(b'name="metadata"', 1)[1]
    meta_json = head.split(b"\r\n\r\n", 1)[1].split(b"\r\n--" + boundary, 1)[0].decode()
    assert json.loads(meta_json) == meta, meta_json
    assert "中文" in meta_json, "non-ASCII changelog must not be escaped"
    print("upload ok -> file id 987654")

    # HTTP error must fail the step.
    cfr.API_BASE = serve(Rejecting)
    try:
        cfr.upload(archive, meta, "tok")
    except SystemExit as exc:
        assert exc.code == 1, exc.code
        print("HTTP 403 -> SystemExit(1) ok")
    else:
        raise AssertionError("upload must fail the step on HTTP errors")

    # Missing token must fail before any network call.
    cfr.API_BASE = "http://127.0.0.1:1"
    os.environ.pop("CURSEFORGE_TOKEN", None)
    sys.argv = ["x", "--root", str(root), "--tag", "v1.4.0", "--out-dir", str(root / "dist")]
    try:
        cfr.main()
    except SystemExit as exc:
        assert exc.code == 1, exc.code
        print("missing token -> SystemExit(1) ok")
    else:
        raise AssertionError("missing token must fail")

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
