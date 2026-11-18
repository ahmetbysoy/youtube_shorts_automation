"""Separate, bounded media selection history. Never touches Phase 3 topic history.

Recent use is a ranking penalty, not a perpetual ban. Same-video duplication is
hard-blocked in the selector. Remote writes merge via Contents API blob-SHA CAS;
this is NOT a distributed media reservation and cannot prevent all concurrent reuse.
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / ".media_history.json"


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def validate_history(data) -> dict:
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("entries"), list):
        raise ValueError("media_history_invalid_fail_closed")
    for item in data["entries"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k] for k in ("key", "sha256", "source_url", "selected_at", "generation_id")):
            raise ValueError("media_history_invalid_entry_fail_closed")
    return {"version": 1, "entries": data["entries"][-200:]}


class MediaHistory:
    def __init__(self, path: Path = DEFAULT_PATH, *, repository: str = "", token: str = "", ref: str = "main", remote_path: str = ".media_history.json", session=requests):
        if bool(repository) != bool(token):
            raise ValueError("media_history_incomplete_remote_config_fail_closed")
        self.path, self.repository, self.ref, self.session = path, repository, ref, session
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self.url = f"https://api.github.com/repos/{repository}/contents/{quote(remote_path, safe='/')}" if repository else None

    @classmethod
    def from_environment(cls):
        return cls(repository=os.environ.get("GITHUB_REPOSITORY", ""), token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "",
                   ref=os.environ.get("TOPIC_HISTORY_REF", "main"))

    def _get(self) -> tuple[dict, str | None]:
        if self.url:
            r = self.session.get(self.url, headers=self._headers, params={"ref": self.ref}, timeout=(5, 20), allow_redirects=False)
            if r.status_code == 404:
                return {"version": 1, "entries": []}, None
            if r.status_code != 200:
                raise RuntimeError("media_history_read_failed_closed")
            try:
                body = r.json()
                if not isinstance(body.get("sha"), str) or not body["sha"]:
                    raise ValueError("missing_blob_sha")
                encoded = "".join(body["content"].split())
                data = json.loads(base64.b64decode(encoded, validate=True))
                return validate_history(data), body["sha"]
            except Exception:
                raise ValueError("media_history_remote_payload_invalid_fail_closed") from None
        try:
            return validate_history(json.loads(self.path.read_text(encoding="utf-8"))), None
        except FileNotFoundError:
            return {"version": 1, "entries": []}, None

    def recent(self) -> list[dict]:
        return self._get()[0]["entries"][-100:]

    def remember(self, entries: list[dict]) -> None:
        validate_history({"version": 1, "entries": entries})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".json.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                for attempt in range(6):
                    current, sha = self._get()
                    existing = {(e["key"], e["generation_id"]) for e in current["entries"]}
                    additions = []
                    for entry in entries:
                        identity = (entry["key"], entry["generation_id"])
                        if identity not in existing:
                            additions.append(entry)
                            existing.add(identity)
                    merged = {"version": 1, "entries": (current["entries"]+additions)[-200:]}
                    if self.url:
                        payload = {"message": "chore: atomic media selection history", "branch": self.ref,
                                   "content": base64.b64encode((json.dumps(merged, ensure_ascii=False, indent=2)+"\n").encode()).decode()}
                        if sha: payload["sha"] = sha
                        r = self.session.put(self.url, headers=self._headers, json=payload, timeout=(5, 20), allow_redirects=False)
                        if r.status_code in {409, 422}:
                            time.sleep(0.05*(attempt+1)); continue
                        if r.status_code not in {200, 201}:
                            raise RuntimeError("media_history_write_failed_closed")
                    atomic_json(self.path, merged)
                    return
                raise RuntimeError("media_history_cas_retry_exhausted")
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
