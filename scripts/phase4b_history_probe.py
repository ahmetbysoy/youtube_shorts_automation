"""Real, production-isolated Contents API history proof across TWO Actions runs.

The controlled stale-SHA conflict is real HTTP, not a mocked status. It uses two
independent clients with an intentional interleaving in run 1, NOT a claim of a
distributed lock/reservation or spontaneous concurrent Actions execution. Run 2
must have a distinct Actions run ID, read the saved entries, then delete the ref.
All entries are labeled synthetic sentinels, not media-selection/publication data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from src.media_processing.media_history import MediaHistory, atomic_json

ROLES = {"seed", "competing_writer", "primary_writer"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def probe_target(probe_id: str) -> tuple[str, str]:
    if not re.fullmatch(r"p4b-[a-z0-9](?:[a-z0-9-]{6,48}[a-z0-9])", probe_id):
        raise ValueError("invalid_isolated_probe_id")
    return "phase4b-media-history/"+probe_id, ".phase4b-probes/"+probe_id+"/media_history.json"


def sentinel(probe_id: str, role: str, writer_id: str, repository: str) -> dict:
    return {"key": f"phase4b:{probe_id}:{role}", "sha256": hashlib.sha256(f"{probe_id}:{role}".encode()).hexdigest(),
            "source_url": f"https://github.com/{repository}/actions/runs/{writer_id}",
            "selected_at": now(), "generation_id": f"phase4b:{probe_id}:actions:{writer_id}",
            "probe_id": probe_id, "role": role, "writer_run_id": writer_id, "synthetic_probe_sentinel": True}


class GitHubProbe:
    def __init__(self, repository: str, token: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not token:
            raise ValueError("github_probe_config_missing_or_invalid")
        self.repository = repository
        self.base = f"https://api.github.com/repos/{repository}"
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self.token = token

    def request(self, method, route, **kwargs):
        if not route.startswith(("/git/", "/contents/")) or "?" in route:
            raise ValueError("probe_api_route_not_allowed")
        return requests.request(method, self.base+route, headers=self.headers, allow_redirects=False, timeout=(5, 30), **kwargs)

    def main_snapshot(self) -> dict:
        result = {}
        for name in (".used_topics.json", ".media_history.json"):
            r = self.request("GET", "/contents/"+name, params={"ref": "main"})
            if r.status_code not in {200, 404}: raise RuntimeError("production_snapshot_read_failed_closed")
            result[name] = {"http_status": r.status_code, "blob_sha": r.json().get("sha") if r.status_code == 200 else None}
        return result

    def ref(self, branch):
        return self.request("GET", "/git/ref/heads/"+quote(branch, safe="/"))

    def cleanup(self, branch: str, remote_path: str) -> dict:
        prefix = "phase4b-media-history/"
        if not branch.startswith(prefix) or probe_target(branch[len(prefix):]) != (branch, remote_path):
            raise ValueError("cleanup_target_not_isolated")
        route = "/contents/"+quote(remote_path, safe="/")
        before = self.request("GET", route, params={"ref": branch})
        file_delete_status = None
        if before.status_code == 200:
            sha = before.json().get("sha")
            if not isinstance(sha, str) or not sha: raise ValueError("cleanup_blob_sha_missing")
            deleted = self.request("DELETE", route, json={"message": "chore: remove isolated Phase4B probe data", "branch": branch, "sha": sha})
            file_delete_status = deleted.status_code
        file_check = self.request("GET", route, params={"ref": branch})
        # Remove the actual probe file first, verify 404 while the ref still
        # exists, then remove the branch. Old Git objects are not secure-erased.
        response = self.request("DELETE", "/git/refs/heads/"+quote(branch, safe="/"))
        status = response.status_code
        ref_check = self.ref(branch)
        path_check = self.request("GET", route, params={"ref": branch})
        file_removed = (before.status_code == 404 or file_delete_status == 200) and file_check.status_code == 404
        passed = file_removed and status in {204, 404, 422} and ref_check.status_code == 404 and path_check.status_code == 404
        return {"status": "passed" if passed else "FAILED_REQUIRES_MANUAL_CLEANUP", "delete_http_status": status,
                "probe_file_delete_http_status": file_delete_status, "probe_file_absence_before_ref_delete_http_status": file_check.status_code,
                "ref_absence_http_status": ref_check.status_code, "probe_path_absence_http_status": path_check.status_code,
                "branch_and_accessible_probe_data_removed": passed, "git_object_secure_erasure_claimed": False}


class RealHistoryTransport:
    """Trace only safe status/blob-SHA data; every request is actual GitHub HTTP."""
    def __init__(self, client: GitHubProbe, branch: str, remote_path: str, trace: list):
        self.url = client.base+"/contents/"+quote(remote_path, safe="/")
        self.branch, self.trace = branch, trace

    def get(self, url, **kwargs):
        if url != self.url or kwargs.get("params") != {"ref": self.branch}:
            raise ValueError("history_probe_read_target_violation")
        r = requests.get(url, **kwargs)
        self.trace.append({"method": "GET", "http_status": r.status_code, "blob_sha": r.json().get("sha") if r.status_code == 200 else None})
        return r

    def put(self, url, **kwargs):
        if url != self.url or kwargs.get("json", {}).get("branch") != self.branch:
            raise ValueError("history_probe_write_target_violation")
        r = requests.put(url, **kwargs)
        record = {"method": "PUT", "http_status": r.status_code, "submitted_blob_sha": kwargs["json"].get("sha")}
        if r.status_code in {200, 201}:
            record["result_blob_sha"] = (r.json().get("content") or {}).get("sha")
        self.trace.append(record)
        return r


class ControlledConflictTransport:
    def __init__(self, transport: RealHistoryTransport, competitor: MediaHistory, entry: dict):
        self.transport, self.competitor, self.entry = transport, competitor, entry
        self.injected, self.conflict_status, self.stale_trace_index = False, None, None

    def get(self, url, **kwargs):
        return self.transport.get(url, **kwargs)

    def put(self, url, **kwargs):
        if not self.injected:
            if not kwargs.get("json", {}).get("sha"):
                raise ValueError("real_conflict_requires_existing_blob_sha")
            self.injected = True
            # After primary's GET, BEFORE forwarding its unchanged PUT, a
            # second independent client commits to the SAME isolated file.
            self.competitor.remember([self.entry])
            self.stale_trace_index = len(self.transport.trace)
            r = self.transport.put(url, **kwargs)  # actual stale request to GitHub
            self.conflict_status = r.status_code
            return r
        return self.transport.put(url, **kwargs)


def verify_entries(entries: list, probe_id: str, writer_id: str, repository: str):
    if len(entries) != 3 or {e.get("role") for e in entries} != ROLES:
        raise ValueError("persisted_probe_roles_missing_or_duplicated")
    for entry in entries:
        expected = sentinel(probe_id, entry["role"], writer_id, repository)
        for name in ("key", "sha256", "source_url", "generation_id", "probe_id", "writer_run_id", "synthetic_probe_sentinel"):
            if entry.get(name) != expected[name]: raise ValueError("persisted_probe_identity_mismatch")


def run_probe(mode: str, probe_id: str, writer_id: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    branch, remote_path = probe_target(probe_id)
    current_id = os.environ.get("GITHUB_RUN_ID", "")
    source = os.environ.get("GITHUB_SHA", "")
    client = GitHubProbe(os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", ""))
    if not current_id.isdigit() or not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("requires_actual_actions_run_identity")
    result = {"version": 1, "phase": "4B", "mode": mode, "probe_id": probe_id, "branch": branch, "remote_path": remote_path,
              "github_run_id": current_id, "github_sha": source, "started_at": now(), "status": "started", "publishing": False,
              "production_history_targeted": False, "local_flock_is_distributed_lock": False,
              "synthetic_history_sentinels_not_media_selections": True, "http_trace": []}
    created = False
    snapshot = None
    try:
        snapshot = client.main_snapshot(); result["production_main_before"] = snapshot
        if mode == "cleanup":
            result["cleanup"] = client.cleanup(branch, remote_path)
            result["status"] = "passed" if result["cleanup"]["status"] == "passed" else "failed"
        elif mode == "write":
            if client.ref(branch).status_code != 404: raise ValueError("probe_ref_exists_refuse_reuse")
            response = client.request("POST", "/git/refs", json={"ref": "refs/heads/"+branch, "sha": source})
            if response.status_code != 201: raise RuntimeError("isolated_ref_create_failed")
            created = True
            result["writer_run_id"] = current_id
            transport = RealHistoryTransport(client, branch, remote_path, result["http_trace"])
            kwargs = {"repository": client.repository, "token": client.token, "ref": branch, "remote_path": remote_path}
            initial = MediaHistory(output/"seed_cache.json", session=transport, **kwargs)
            initial.remember([sentinel(probe_id, "seed", current_id, client.repository)])
            competitor = MediaHistory(output/"competing_cache.json", session=transport, **kwargs)
            conflict = ControlledConflictTransport(transport, competitor, sentinel(probe_id, "competing_writer", current_id, client.repository))
            primary = MediaHistory(output/"primary_cache.json", session=conflict, **kwargs)
            primary.remember([sentinel(probe_id, "primary_writer", current_id, client.repository)])
            entries = primary.recent()
            verify_entries(entries, probe_id, current_id, client.repository)
            retry = result["http_trace"][conflict.stale_trace_index or 0:]
            if conflict.conflict_status not in {409, 422} or [(e["method"], e["http_status"]) for e in retry[:3]] != [("PUT", conflict.conflict_status), ("GET", 200), ("PUT", 200)]:
                raise ValueError("real_conflict_reread_merge_not_observed")
            result["cas"] = {"real_http": True, "actual_conflict_http_status": conflict.conflict_status, "reread_and_merged_retry_passed": True,
                "controlled_two_client_interleaving_in_run1": True, "spontaneous_cross_actions_race_claimed": False,
                "merged_roles": sorted(ROLES), "distributed_reservation_claimed": False}
            result["persisted_entries"] = entries
            result["isolated_branch_commit_sha"] = client.ref(branch).json().get("object", {}).get("sha")
            result["status"] = "passed_waiting_for_distinct_run2"
            result["cleanup"] = {"status": "retained_only_for_run2_verification", "required_next_action": "verify_in_distinct_actions_run_then_delete_ref"}
        else:
            if not writer_id.isdigit() or writer_id == current_id:
                raise ValueError("verification_requires_distinct_writer_actions_run")
            result["writer_run_id"] = writer_id
            if client.ref(branch).status_code != 200: raise ValueError("isolated_writer_ref_missing")
            transport = RealHistoryTransport(client, branch, remote_path, result["http_trace"])
            history = MediaHistory(output/"verification_cache.json", repository=client.repository, token=client.token,
                                   ref=branch, remote_path=remote_path, session=transport)
            entries = history.recent()  # actual remote read, no artifact/local-cache substitution
            verify_entries(entries, probe_id, writer_id, client.repository)
            result["observed_entries"] = entries
            result["cross_actions_persistence"] = {"status": "passed", "writer_run_id": writer_id, "reader_run_id": current_id,
                "distinct_actions_runs": True, "read_from_github_contents_api": True, "all_three_writer_entries_observed": True}
            result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["error_type"] = type(exc).__name__
        # Only our fixed snake-case failure codes, never request/response text.
        if re.fullmatch(r"[a-z_]{4,100}", str(exc)): result["failure_code"] = str(exc)
    finally:
        if mode == "verify" or (mode == "write" and created and result["status"] != "passed_waiting_for_distinct_run2"):
            try: result["cleanup"] = client.cleanup(branch, remote_path)
            except Exception as exc: result["cleanup"] = {"status": "FAILED_REQUIRES_MANUAL_CLEANUP", "error_type": type(exc).__name__}
        if result.get("cleanup", {}).get("status") == "FAILED_REQUIRES_MANUAL_CLEANUP": result["status"] = "failed"
        try:
            after = client.main_snapshot()
            result["production_main_after"] = after
            result["production_main_unchanged_during_probe"] = snapshot is not None and snapshot == after
            if not result["production_main_unchanged_during_probe"]: result["status"] = "failed_main_snapshot_changed_or_unavailable"
        except Exception as exc:
            result["status"] = "failed_main_snapshot_unverified"; result["snapshot_error_type"] = type(exc).__name__
        result["completed_at"] = now()
        atomic_json(output/"result.json", result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["write", "verify", "cleanup"])
    ap.add_argument("--probe-id", required=True)
    ap.add_argument("--writer-run-id", default="")
    ap.add_argument("--output", type=Path, default=Path("output/phase4b_history"))
    args = ap.parse_args()
    try:
        result = run_probe(args.mode, args.probe_id, args.writer_run_id, args.output)
        print("PHASE4B_HISTORY_RESULT="+result["status"], flush=True)
        return 0 if result["status"] in {"passed", "passed_waiting_for_distinct_run2"} else 1
    except Exception as exc:
        print("PHASE4B_HISTORY_FAILURE="+type(exc).__name__, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
