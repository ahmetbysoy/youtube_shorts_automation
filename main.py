"""Local environment check. This entry point does not call external services."""
from __future__ import annotations

import argparse
import importlib
import json
import platform
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MODULES = {
    "google-api-python-client": "googleapiclient.discovery",
    "google-auth-oauthlib": "google_auth_oauthlib.flow",
    "google-auth-httplib2": "google_auth_httplib2",
    "edge-tts": "edge_tts",
    "moviepy": "moviepy",
    "ffmpeg-python": "ffmpeg",
    "opencv-python": "cv2",
    "Pillow": "PIL.Image",
    "playwright": "playwright.sync_api",
    "selenium": "selenium.webdriver",
    "pydrive2": "pydrive2.auth",
    "python-dotenv": "dotenv",
    "aiohttp": "aiohttp",
    "requests": "requests",
    "beautifulsoup4": "bs4",
    "yt-dlp": "yt_dlp",
}


def inspect_environment() -> dict:
    packages = {}
    for distribution, module in MODULES.items():
        try:
            importlib.import_module(module)
        except Exception as exc:
            packages[distribution] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        else:
            try:
                installed_version = version(distribution)
            except PackageNotFoundError:
                installed_version = "unknown"
            packages[distribution] = {"ok": True, "version": installed_version}

    tools = {}
    for tool, flag in (("ffmpeg", "-version"), ("ffprobe", "-version"), ("tree", "--version")):
        executable = shutil.which(tool)
        if executable:
            result = subprocess.run([executable, flag], capture_output=True, text=True, check=False)
            tools[tool] = {
                "ok": result.returncode == 0,
                "path": executable,
                "version": (result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else "",
            }
        else:
            tools[tool] = {"ok": False, "error": "Not found on PATH"}

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "tools": tools,
        "ok": all(item["ok"] for item in packages.values()) and all(item["ok"] for item in tools.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the local environment without network requests")
    parser.add_argument("--json", type=Path, help="Also write the check result to a JSON file")
    args = parser.parse_args()
    if not args.check:
        parser.print_help()
        return 0
    report = inspect_environment()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
