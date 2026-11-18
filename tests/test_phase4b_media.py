"""FAZ4B boundaries: mocked HTTP unless a test explicitly says offline real IO.

No test in this module is live-provider or cross-Actions evidence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from requests.adapters import BaseAdapter

from scripts.media_probe_security import audit_artifacts, consume_provider_configuration, prepare_media_cookies
from scripts.phase4b_history_probe import GitHubProbe, probe_target
from src.media_processing.media_history import MediaHistory
from src.media_processing.media_io import MAX_BYTES, download_candidate, probe_media
from src.media_processing.media_providers import BrowserStockProvider, PexelsProvider, PixabayProvider, commons_license, get_public
from src.media_processing.scene_media import SceneMediaError, provider_issue, select_storyboard_media
from tests.test_phase4_media import Provider, candidate, download_stub, probe_stub, script


def entry(key="old", sha="old", generation="prior"):
    return {"key": key, "sha256": sha, "source_url": f"https://commons.wikimedia.org/wiki/File:{key}",
            "selected_at": "2026-11-18T12:00:00Z", "generation_id": generation}


def response(entries, sha="old"):
    return Mock(status_code=200, json=lambda: {"sha": sha, "content": base64.b64encode(json.dumps({"version": 1, "entries": entries}).encode()).decode()})


def test_hash_only_recent_hit_reranks_against_fresh_measured_candidate(tmp_path):
    first, fresh = candidate("a"), candidate("b")
    old_hash = hashlib.sha256(b"a"*2048).hexdigest()
    history = MediaHistory(tmp_path/"history.json")
    history.remember([entry("different-provider-and-id", old_hash)])
    runtime, report = select_storyboard_media(script(), tmp_path/"work", providers=[Provider([first, fresh])],
        history=history, downloader=download_stub, prober=probe_stub)
    assert report["scenes"][0]["selected_media_id"] == "b"
    measured = report["scenes"][0]["measured_candidates"]
    assert measured[0]["recent_hash_match"] and measured[0]["assessment"]["components"]["recent_use_penalty"] == -25
    assert measured[0]["decision"] == "not_selected_lower_measured_rank"
    assert measured[1]["decision"] == "selected_highest_measured_rank"
    assert len(list((tmp_path/"work").iterdir())) == 1 and runtime[0]["path"].exists()
    assert history.recent()[-1]["key"] == "wikimedia:b"


def test_measured_resolution_changes_ranking_not_just_the_reported_score(tmp_path):
    def prober(path, kind):
        return {**probe_stub(path, kind), **({"width": 1080, "height": 720} if path.read_bytes().startswith(b"a") else {})}
    _, report = select_storyboard_media(script(), tmp_path/"work", providers=[Provider([candidate("a"), candidate("b")])],
        history=MediaHistory(tmp_path/"h.json"), downloader=download_stub, prober=prober)
    assert report["scenes"][0]["selected_media_id"] == "b"


def test_identical_bytes_under_different_providers_urls_ids_and_two_scenes_fail_closed(tmp_path):
    a = replace(candidate("1"), provider="pexels", source_url="https://www.pexels.com/video/moon-1/", download_url="https://images.pexels.com/1.jpg")
    b = candidate("2")
    data = script(); data["storyboard"].append({**data["storyboard"][0], "scene_id": 2})
    def same_bytes(c, path): path.write_bytes(b"identical-media"*1024)
    with pytest.raises(SceneMediaError) as err:
        select_storyboard_media(data, tmp_path/"work", providers=[Provider([a], "pexels"), Provider([b], "wikimedia")],
            history=MediaHistory(tmp_path/"h.json"), downloader=same_bytes, prober=probe_stub)
    assert "duplicate_content_in_video" in json.dumps(err.value.report)
    assert not (tmp_path/"h.json").exists() and "scene_media" not in data


def test_measured_rerank_stays_within_four_download_budget(tmp_path):
    download = Mock(side_effect=download_stub)
    select_storyboard_media(script(), tmp_path/"work", providers=[Provider([candidate(str(i)) for i in range(8)])],
        history=MediaHistory(tmp_path/"h.json"), downloader=download, prober=probe_stub)
    assert download.call_count == 4


class CapturingAdapter(BaseAdapter):
    """Real requests prepared-request path, offline fake HTTP response only."""
    def __init__(self): self.sent = []
    def send(self, request, **kwargs):
        self.sent.append(request)
        r = requests.Response(); r.request = request; r.url = request.url
        r.status_code = 302 if len(self.sent) == 1 else 200
        r.headers = {"Location": "https://thumb.wikimedia.org/final.jpg"} if len(self.sent) == 1 else {}
        r._content = b"fixture"*1024; r._content_consumed = True
        return r
    def close(self): pass


def test_redirects_strip_session_auth_cookies_and_custom_key_headers_on_every_hop():
    session = requests.Session()
    session.auth = ("private-user", "private-password")
    session.headers.update({"Authorization": "Bearer private", "Cookie": "secret=value", "X-API-Key": "private"})
    session.cookies.set("private_cookie", "private_value", domain=".wikimedia.org")
    adapter = CapturingAdapter(); session.mount("https://", adapter)
    with get_public(session, "https://upload.wikimedia.org/start.jpg", {"upload.wikimedia.org", "thumb.wikimedia.org"}) as r:
        assert r.status_code == 200
    assert len(adapter.sent) == 2
    assert all(set(r.headers) == {"User-Agent", "Accept"} for r in adapter.sent)
    assert all("private" not in str(dict(r.headers)) for r in adapter.sent)


@pytest.mark.parametrize("destination", ["http://upload.wikimedia.org/a", "https://upload.wikimedia.org.evil.test/a", "https://user:pass@upload.wikimedia.org/a", "https://169.254.169.254/a"])
def test_redirect_host_and_credential_lookalikes_rejected_before_second_request(destination):
    session = Mock(get=Mock(return_value=Mock(status_code=302, headers={"Location": destination})))
    with pytest.raises(ValueError): get_public(session, "https://upload.wikimedia.org/a", {"upload.wikimedia.org"})
    assert session.get.call_count == 1


@pytest.mark.parametrize("provider", [PexelsProvider, PixabayProvider])
def test_api_key_is_only_sent_to_its_own_api_and_authenticated_redirects_stop(provider):
    session = Mock(get=Mock(return_value=Mock(status_code=302)))
    with pytest.raises(RuntimeError): provider("private-fixture-key", session=session).search("ocean")
    call = session.get.call_args
    assert call.kwargs["allow_redirects"] is False and session.get.call_count == 1
    assert call.args[0] == ("https://api.pexels.com/videos/search" if provider is PexelsProvider else "https://pixabay.com/api/videos/")
    if provider is PexelsProvider: assert call.kwargs["headers"]["Authorization"] == "private-fixture-key"
    else: assert call.kwargs["params"]["key"] == "private-fixture-key" and "Authorization" not in call.kwargs["headers"]


@pytest.mark.parametrize("declared,chunks", [(2048, [b"x"*1024]), (0, [b"x"]), (MAX_BYTES+1, []), (0, [b"x"*(MAX_BYTES+1)])])
def test_partial_empty_and_oversize_downloads_remove_both_final_and_part(tmp_path, declared, chunks):
    r = Mock(headers={"Content-Length": str(declared)}, iter_content=Mock(return_value=iter(chunks)))
    r.__enter__ = Mock(return_value=r); r.__exit__ = Mock(return_value=None)
    path = tmp_path/"media.jpg"
    with patch("src.media_processing.media_io.get_public", return_value=r), pytest.raises(RuntimeError):
        download_candidate(candidate(), path)
    assert not path.exists() and not path.with_suffix(".jpg.part").exists()


@pytest.mark.parametrize("case", ["missing", "only_partial", "too_small"])
def test_missing_and_partial_files_cannot_pass_full_decode(tmp_path, case):
    p = tmp_path/"media.mp4"
    if case == "only_partial": p.with_suffix(".mp4.part").write_bytes(b"x"*2048)
    if case == "too_small": p.write_bytes(b"x"*1023)
    with pytest.raises(RuntimeError, match="probe_or_decode_failed"): probe_media(p, "video")


@pytest.mark.parametrize("status", [403, 409, 422, 500, 503])
def test_contents_read_errors_do_not_turn_into_empty_history(tmp_path, status):
    session = Mock(get=Mock(return_value=Mock(status_code=status)))
    h = MediaHistory(tmp_path/"h.json", repository="owner/repo", token="fixture", session=session)
    with pytest.raises(RuntimeError, match="read_failed_closed"): h.remember([entry()])
    session.put.assert_not_called()
    assert not (tmp_path/"h.json").exists()


def test_contents_404_and_missing_local_history_are_explicitly_empty(tmp_path):
    session = Mock(get=Mock(return_value=Mock(status_code=404)))
    assert MediaHistory(tmp_path/"h.json", repository="owner/repo", token="fixture", session=session).recent() == []
    assert MediaHistory(tmp_path/"local.json").recent() == []


@pytest.mark.parametrize("status", [403, 404, 500, 503])
def test_contents_non_conflict_write_errors_fail_without_local_success_cache(tmp_path, status):
    session = Mock(get=Mock(return_value=Mock(status_code=404)), put=Mock(return_value=Mock(status_code=status)))
    with pytest.raises(RuntimeError, match="write_failed_closed"):
        MediaHistory(tmp_path/"h.json", repository="owner/repo", token="fixture", session=session).remember([entry()])
    assert session.put.call_count == 1 and not (tmp_path/"h.json").exists()


@pytest.mark.parametrize("status", [409, 422])
def test_contents_conflict_rereads_and_merges_competitor_without_lost_update(tmp_path, status):
    session = Mock(); session.get.side_effect = [response([], "old"), response([entry("competitor")], "fresh")]
    session.put.side_effect = [Mock(status_code=status), Mock(status_code=200)]
    h = MediaHistory(tmp_path/"h.json", repository="owner/repo", token="fixture", session=session)
    h.remember([entry("primary"), entry("primary")])
    payload = json.loads(base64.b64decode(session.put.call_args.kwargs["json"]["content"]))
    assert [e["key"] for e in payload["entries"]] == ["competitor", "primary"]
    assert session.put.call_args.kwargs["json"]["sha"] == "fresh"


@pytest.mark.parametrize("status", [409, 422])
def test_repeated_contents_conflicts_have_bounded_retries(tmp_path, status):
    session = Mock(get=Mock(return_value=response([])), put=Mock(return_value=Mock(status_code=status)))
    with patch("src.media_processing.media_history.time.sleep"), pytest.raises(RuntimeError, match="retry_exhausted"):
        MediaHistory(tmp_path/"h.json", repository="owner/repo", token="fixture", session=session).remember([entry()])
    assert session.get.call_count == session.put.call_count == 6
    assert not (tmp_path/"h.json").exists()


@pytest.mark.parametrize("body", [{"sha": "ok", "content": "%%%"}, {"sha": "", "content": "e30="}, {"content": "e30="},
                                 {"sha": "ok", "content": "W10="}, {"sha": "ok", "content": "e2Jyb2tlbg=="}])
def test_corrupt_remote_history_payload_is_not_overwritten(tmp_path, body):
    session = Mock(get=Mock(return_value=Mock(status_code=200, json=lambda: body)))
    with pytest.raises(ValueError, match="payload_invalid"):
        MediaHistory(tmp_path/"h.json", repository="owner/repo", token="fixture", session=session).remember([entry()])
    session.put.assert_not_called()


def _local_writer(args):
    path, number = args
    MediaHistory(Path(path)).remember([entry(f"writer-{number}", generation=f"generation-{number}")])


def test_real_offline_multiprocess_local_flock_prevents_lost_updates_not_distributed_reservation(tmp_path):
    path = tmp_path/"h.json"
    with ProcessPoolExecutor(max_workers=4) as executor:
        list(executor.map(_local_writer, [(str(path), i) for i in range(12)]))
    assert {e["key"] for e in MediaHistory(path).recent()} == {f"writer-{i}" for i in range(12)}


@pytest.mark.parametrize("url,attr,creator", [("https://creativecommons.org/licenses/by/4.0/", "false", "Author"),
    ("https://creativecommons.org:invalid/licenses/by/4.0/", "true", "Author"),
    ("https://creativecommons.org/licenses/by/4.0/", "true", "")])
def test_contradictory_attribution_malformed_license_and_missing_creator_are_rejected(url, attr, creator):
    ext = {"LicenseShortName": {"value": "CC BY 4.0"}, "LicenseUrl": {"value": url}, "AttributionRequired": {"value": attr}, "Artist": {"value": creator}}
    lic = commons_license({"title": "File:Test.jpg"}, {"descriptionurl": "https://commons.wikimedia.org/wiki/File:Test.jpg", "extmetadata": ext})
    assert not lic.verified


def test_dotenv_is_data_only_allowlisted_no_interpolation_or_export_to_children(tmp_path):
    marker = tmp_path/"must-not-exist"
    env = {"PHASE4_PROVIDER_ENV": f'PEXELS_API_KEY="${{OTHER_KEY}}"\nPIXABAY_API_KEY="$(touch {marker})"\nGEMINI_API_KEY=unrelated-private-value\nOTHER_KEY=do-not-copy\n',
           "PEXELS_API_KEY": "direct-private-pexels-key", "PATH": "/usr/bin"}
    config = consume_provider_configuration(env)
    assert config.key_for("pexels") == "direct-private-pexels-key"
    assert config.key_for("pixabay") == f"$(touch {marker})" and not marker.exists()
    assert env == {"PATH": "/usr/bin"} and "unrelated-private-value" not in repr(config)
    assert all(type(value) is bool for value in config.presence["providers"]["pexels"].values())
    literal = consume_provider_configuration({"PHASE4_PROVIDER_ENV": 'PEXELS_API_KEY="${OTHER_KEY}"\nOTHER_KEY=private'})
    assert literal.key_for("pexels") == "${OTHER_KEY}"


def test_browser_403_has_four_safe_fields_and_never_inherits_api_github_or_gemini_values(tmp_path, monkeypatch):
    (tmp_path/"cookies.json").write_text("[]")
    monkeypatch.setattr("src.media_processing.media_providers.ROOT", tmp_path)
    # Faz 4E: PEXELS_COOK olmadan BrowserStockProvider subprocess'a hic gitmez
    # (cookie_missing erken donus). Env sanitizasyon testi icin ornek cookie ekle.
    env = {"PEXELS_API_KEY": "private-pexels", "PIXABAY_API_KEY": "private-pixabay", "GH_TOKEN": "private-github",
           "GEMINI_COOK": "private-gemini", "PHASE4_PROVIDER_ENV": "private-env",
           "PEXELS_COOK": "[]",  # cookie var ama bos (domain_ok degilse de search cagrilir ama biz 0 donuyoruz)
           "PATH": "/usr/bin", "HOME": str(tmp_path)}
    result = Mock(returncode=0, stdout=json.dumps({"candidates": [], "diagnostics": {"search_http_status": 403, "Cookie": "private-cookie", "cookie_present": False}}))
    terms = Mock()
    with patch.dict(os.environ, env, clear=True), patch("src.media_processing.media_providers.subprocess.run", return_value=result) as run:
        p = BrowserStockProvider("pexels", terms=terms)
        assert p.search("ocean waves beach") == []
    # run cagrilmis olmali (metadata modu)
    assert run.call_args is not None, "subprocess.run cagrilmadi (cookie erken donus?)"
    called_env = run.call_args.kwargs.get("env") or run.call_args[1].get("env")
    assert set(called_env) <= {"PATH", "HOME", "PEXELS_COOK", "LANG", "LC_ALL", "LC_CTYPE", "DISPLAY",
                               "TMPDIR", "TMP", "TEMP", "XDG_RUNTIME_DIR", "PLAYWRIGHT_BROWSERS_PATH",
                               "USER", "LOGNAME"}
    assert "GH_TOKEN" not in called_env and "GEMINI_COOK" not in called_env and "PEXELS_API_KEY" not in called_env
    issue = provider_issue(p, "ocean waves beach")
    # issue safe alanlar: provider, error_type, query_id, ve opsiyonel http_status
    assert set(issue) <= {"provider", "error_type", "query_id", "http_status"}
    assert "private" not in json.dumps(issue) and "ocean waves" not in json.dumps(issue)
    terms.check.assert_not_called()


def test_cookie_writer_only_persists_existing_stock_domains_with_private_permissions(tmp_path):
    p = tmp_path/"cookies.json"
    raw = json.dumps([{"name": "a", "value": "private-stock", "domain": ".pexels.com", "path": "/"},
                      {"name": "b", "value": "private-google", "domain": ".google.com", "path": "/"}])
    result = prepare_media_cookies(p, raw)
    assert result == {"secret_supplied": True, "stock_cookie_file_created": True}
    assert p.stat().st_mode & 0o777 == 0o600 and "private-google" not in p.read_text()
    with pytest.raises(ValueError): prepare_media_cookies(p, raw)


@pytest.mark.parametrize("payload,env", [({"value": "private-provider-key"}, {"PEXELS_API_KEY": "private-provider-key"}),
    ({"value": "ghp_"+"x"*30}, {}), ({"url": "https://upload.wikimedia.org/a?signature=private"}, {}),
    ({"url": "https://user:pass@upload.wikimedia.org/a"}, {}),
    ({"description": "Credit source: https://upload.wikimedia.org/a?signature=private ; modified"}, {})])
def test_artifact_audit_blocks_known_credentials_patterns_and_signed_urls(tmp_path, payload, env):
    (tmp_path/"result.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError): audit_artifacts(tmp_path, env)


@pytest.mark.parametrize("bad", ["main", "p4b-../main", "p4b-test?ref=main", "p4b-x", "p4b-test/branch"])
def test_isolated_probe_target_cannot_be_production_or_path_injection(bad):
    with pytest.raises(ValueError): probe_target(bad)


def test_cleanup_failure_is_explicit_not_silently_accepted():
    client = object.__new__(GitHubProbe)
    client.request = Mock(return_value=Mock(status_code=403))
    client.ref = Mock(return_value=Mock(status_code=200))
    result = client.cleanup(*probe_target("p4b-cleanup-test-20261118"))
    assert result["status"] == "FAILED_REQUIRES_MANUAL_CLEANUP" and not result["branch_and_accessible_probe_data_removed"]


@pytest.mark.parametrize("suffix", ["?signature=private", "#different-conditions"])
def test_license_declarations_with_query_or_fragment_are_not_canonical_permission(suffix):
    ext = {"LicenseShortName": {"value": "CC BY 4.0"}, "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"+suffix},
           "AttributionRequired": {"value": "true"}, "Artist": {"value": "Author"}}
    assert not commons_license({"title": "File:Test"}, {"descriptionurl": "https://commons.wikimedia.org/wiki/File:Test", "extmetadata": ext}).verified


def test_commons_actual_getid3_duration_field_is_advertised_not_invented():
    from src.media_processing.media_providers import WikimediaProvider
    data = {"query": {"pages": {"1": {"pageid": 1, "title": "File:Ocean.webm", "imageinfo": [{"url": "https://upload.wikimedia.org/ocean.webm",
        "mime": "video/webm", "width": 1920, "height": 1080, "metadata": [{"name": "playtime_seconds", "value": 8.661}]}]}}}}
    session = Mock(); session.get.side_effect = [Mock(status_code=200, json=lambda: data), Mock(status_code=200, json=lambda: {})]
    result = WikimediaProvider(session=session).search("ocean")
    assert result[0].duration == 8.661  # still independently re-probed before acceptance


def test_controlled_conflict_transport_preserves_actual_stale_request_and_only_interleaves_once():
    from scripts.phase4b_history_probe import ControlledConflictTransport
    events = []
    transport = Mock(trace=[])
    transport.put.side_effect = lambda url, **kwargs: (events.append(("forward-original-put", kwargs["json"]["sha"])) or Mock(status_code=409))
    competitor = Mock(); competitor.remember.side_effect = lambda entries: events.append(("competing-commit", entries[0]["key"]))
    wrapper = ControlledConflictTransport(transport, competitor, entry("competitor"))
    wrapper.put("https://api.github.com/isolated", json={"sha": "stale-original"})
    wrapper.put("https://api.github.com/isolated", json={"sha": "reread"})
    assert events == [("competing-commit", "competitor"), ("forward-original-put", "stale-original"), ("forward-original-put", "reread")]
    assert wrapper.conflict_status == 409 and competitor.remember.call_count == 1


def test_only_manual_isolated_history_workflow_has_new_write_permission():
    media = Path(".github/workflows/phase4_media_probe.yml").read_text()
    history = Path(".github/workflows/phase4b_history_probe.yml").read_text()
    assert "permissions:\n  contents: read" in media and "contents: write" not in media
    assert "permissions: {}" in history and "      contents: write" in history and "actions: write" not in history.replace("# It has no provider, Gemini, Google or YouTube secrets and no actions:write.", "")
    assert "secrets." not in history and "persist-credentials: false" in media and "persist-credentials: false" in history
    assert "schedule:" not in history
