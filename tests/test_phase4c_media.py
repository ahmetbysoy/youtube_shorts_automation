"""Phase4C: cookie-only gates and SAFE IO diagnosis. Network is MOCKED here."""
from __future__ import annotations

import io
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
import yaml
from PIL import Image

from scripts import phase4b_media_probe as live
from scripts.media_probe_security import audit_artifacts, cookie_only_preflight
from scripts.phase4b_consumer_chain import run_consumer_chain
from scripts.phase4c_commons_diagnostics import diagnose_commons, link_actual_consumer
from src.media_processing.media_history import MediaHistory
from src.media_processing.media_io import MAX_BYTES, MediaIOError, download_candidate, io_evidence, probe_media
from src.media_processing.media_providers import BrowserStockProvider
from src.media_processing.scene_media import SceneMediaError, select_storyboard_media
from tests.test_phase4_media import Provider, candidate, script

MARKER = "private-fixture-value-never-export"


def rows():
    return [{"name": "fixture", "value": MARKER, "domain": ".pexels.com", "path": "/", "secure": True},
            {"name": "fixture", "value": MARKER, "domain": ".pixabay.com", "path": "/", "httpOnly": True}]


@pytest.mark.parametrize("wrapped", [False, True])
def test_cookie_only_preflight_needs_no_api_and_outputs_only_safe_metadata(tmp_path, wrapped):
    data = rows(); data.append({"name": "unrelated", "value": "private-google-marker", "domain": ".google.com"})
    data[0]["unknown_field"] = "must-not-persist"
    path = tmp_path/"cookies.json"
    result = cookie_only_preflight(path, json.dumps({"cookies": data} if wrapped else data))
    assert result["status"] == "passed" and not result["api_credentials_evaluated"]
    assert result["pexels_cookie_domain_count"] == result["pixabay_cookie_domain_count"] == 1
    assert path.stat().st_mode & 0o777 == 0o600
    assert "google" not in path.read_text() and "unknown_field" not in path.read_text()
    assert MARKER not in json.dumps(result) and "sha256" not in json.dumps(result)
    stage = tmp_path/"evidence"; stage.mkdir(); (stage/"preflight.json").write_text(json.dumps(result))
    assert audit_artifacts(stage, {"MEDIA_COOKIES_JSON": json.dumps(data)})["status"] == "passed"


@pytest.mark.parametrize("raw", ["", "{broken", "{}", "true", "null", "[]", '{"cookies":{}}', '[false]'])
def test_invalid_or_missing_cookie_configuration_cannot_start_live_probe(tmp_path, raw):
    result = cookie_only_preflight(tmp_path/"cookies.json", raw)
    assert result["status"] == "failed" and not (tmp_path/"cookies.json").exists()
    assert not result["stock_cookie_file_created"]


@pytest.mark.parametrize("domain", [".google.com", ".youtube.com", ".github.com", "pexels.com.evil.test", "sub.pexels.com", "..pexels.com", ".www.pixabay.com"])
def test_exact_domain_gate_discards_unrelated_and_lookalike_cookies(tmp_path, domain):
    data = rows()+[{"name": "bad", "value": "other-private-marker", "domain": domain}]
    result = cookie_only_preflight(tmp_path/"cookies.json", json.dumps(data))
    assert result["status"] == "passed"
    assert len(json.loads((tmp_path/"cookies.json").read_text())) == 2


@pytest.mark.parametrize("field,value", [("name", 12), ("value", {}), ("path", "not/a/path"), ("secure", "yes"),
    ("httpOnly", 1), ("sameSite", "invalid"), ("expires", -2), ("expires", float("nan")), ("name", "bad\nname")])
def test_invalid_cookie_field_types_fail_without_echoing_values(tmp_path, field, value):
    data = rows(); data[0][field] = value
    result = cookie_only_preflight(tmp_path/"cookies.json", json.dumps(data))
    assert result["status"] == "failed" and result["error_class"] == "invalid_cookie_configuration"
    assert MARKER not in json.dumps(result) and not (tmp_path/"cookies.json").exists()


def test_missing_one_provider_cookie_group_requires_only_media_cookie_secret(tmp_path):
    result = cookie_only_preflight(tmp_path/"cookies.json", json.dumps(rows()[:1]))
    assert result["missing_configuration"] == ["MEDIA_COOKIES_JSON"]
    assert result["pexels_cookie_domain_count"] == 1 and result["pixabay_cookie_domain_count"] == 0
    assert not (tmp_path/"cookies.json").exists()


def test_cookie_same_site_normalization_dedup_and_no_expiry_guess(tmp_path):
    data = rows(); data[0].update(sameSite="no_restriction", expires=1); data.append(dict(data[0]))
    result = cookie_only_preflight(tmp_path/"cookies.json", json.dumps(data))
    assert result["status"] == "passed" and "expired" not in json.dumps(result)
    saved = json.loads((tmp_path/"cookies.json").read_text())
    assert len(saved) == 2 and saved[0]["sameSite"] == "None" and saved[0]["expires"] == 1


def test_conflicting_cookie_rows_and_existing_cookie_path_fail_closed(tmp_path):
    data = rows()+[{**rows()[0], "value": "conflicting-fixture-value"}]
    assert cookie_only_preflight(tmp_path/"cookies.json", json.dumps(data))["status"] == "failed"
    path = tmp_path/"cookies.json"; path.write_text("existing-private-fixture")
    assert cookie_only_preflight(path, json.dumps(rows()))["status"] == "failed"
    assert path.read_text() == "existing-private-fixture"


def test_cookie_only_stock_factory_never_constructs_api_provider_or_reads_config():
    """API-key saglayici siniflari 2026-11-22'te kaldirildi; fabrika yalniz
    BrowserStockProvider uretir ve hicbir anahtar kaynagina dokunmaz."""
    import scripts.phase4b_media_probe as p4b
    assert not hasattr(p4b, "PexelsProvider") and not hasattr(p4b, "PixabayProvider"), \
        "API provider siniflari probe modulunden de kaldirilmis olmali"
    for name in ("pexels", "pixabay"):
        providers = live.stock_providers(name)
        assert len(providers) == 1 and isinstance(providers[0], BrowserStockProvider)


def test_runner_refuses_live_provider_calls_before_preflight(tmp_path):
    with patch("sys.argv", ["probe", "--stock-access-mode", "cookie_only", "--evidence", str(tmp_path/"e")]), \
         patch.object(live, "stock_providers") as providers, pytest.raises(SystemExit, match="preflight required"):
        live.main()
    providers.assert_not_called()


def test_cookie_only_runner_does_not_parse_env_file_or_infer_api_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    e = tmp_path/"e"; e.mkdir()
    gate = cookie_only_preflight(tmp_path/"cookies.json", json.dumps(rows())); (e/"preflight.json").write_text(json.dumps(gate))
    def chain(folder, *, providers, **kwargs):
        folder.mkdir(parents=True)
        for p in providers:
            if isinstance(p, BrowserStockProvider): p.last_diagnostics = {"search_http_status": 403}
        report = {"status": "blocked_unverified", "stages": {}, "failure": "scene_1_has_no_acceptable_media"}
        (folder/"chain.json").write_text(json.dumps(report))
        (folder/"scene_media_manifest.json").write_text(json.dumps({"scenes": [{"provider_errors": []}]}))
        return report
    with patch("sys.argv", ["probe", "--stock-access-mode", "cookie_only", "--work", str(tmp_path/"w"), "--evidence", str(e)]), \
         patch.object(live, "run_consumer_chain", side_effect=chain), \
         patch.object(live, "diagnose_commons", return_value={"candidates": []}):
        assert live.main() == 1
    result = json.loads((e/"evidence.json").read_text())
    for name in ("pexels", "pixabay"):
        assert result["providers"][name]["api_access"] == {"status": "not_requested_cookie_only", "key_used": False}
        assert result["providers"][name]["cookie_access"]["http_status"] == 403
    assert not result["configuration_presence_only"]["env_file_read"]


class Response:
    def __init__(self, status=200, body=b"x"*2048, headers=None):
        self.status_code=status; self.body=body; self.headers=headers or {}; self.closed=False
    def close(self): self.closed=True
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def iter_content(self, chunk_size): yield self.body


@pytest.mark.parametrize("status", [403, 404, 429, 500])
def test_download_http_status_is_distinct_and_query_credentials_never_escape(tmp_path, status):
    session = Mock(get=Mock(return_value=Response(status)))
    c = replace(candidate(), download_url="https://upload.wikimedia.org/file.jpg?signature="+MARKER)
    with pytest.raises(MediaIOError) as error: download_candidate(c, tmp_path/"x", session=session)
    e = error.value
    assert e.safe_error_class == "http_error" and e.evidence["download_http"]["http_status"] == status
    assert e.evidence["container_probe"]["status"] == e.evidence["full_decode"]["status"] == "not_reached"
    assert MARKER not in json.dumps(e.evidence) and MARKER not in str(e)
    assert not (tmp_path/"x").exists()


def test_redirect_rejection_is_not_misreported_as_decode_failure(tmp_path):
    session = Mock(get=Mock(return_value=Response(302, headers={"Location": "https://evil.test/?token="+MARKER})))
    with pytest.raises(MediaIOError) as error: download_candidate(candidate(), tmp_path/"x", session=session)
    assert error.value.safe_error_class == "redirect_rejected" and session.get.call_count == 1
    assert not error.value.evidence["redirect_final_host"]["final_host_allowed"]
    assert MARKER not in json.dumps(error.value.evidence)


def test_download_timeout_has_no_exception_message_or_url(tmp_path):
    with pytest.raises(MediaIOError) as error:
        download_candidate(candidate(), tmp_path/"x", session=Mock(get=Mock(side_effect=requests.ReadTimeout(MARKER))))
    assert error.value.safe_error_class == "download_timeout" and MARKER not in json.dumps(error.value.evidence)


@pytest.mark.parametrize("body,length,code", [(b"", 0, "empty_download"), (b"x"*512, 512, "empty_download"),
    (b"x"*1024, 2048, "truncated_download"), (b"", MAX_BYTES+1, "download_size_limit")])
def test_download_byte_failures_are_separate_and_remove_partial_files(tmp_path, body, length, code):
    session = Mock(get=Mock(return_value=Response(body=body, headers={"Content-Length": str(length)})))
    path = tmp_path/"x.mp4"
    with pytest.raises(MediaIOError) as error: download_candidate(candidate(), path, session=session)
    assert error.value.safe_error_class == code
    assert not path.exists() and not path.with_suffix('.mp4.part').exists()


def test_html_200_is_invalid_container_before_accepting_body(tmp_path):
    response = Response(headers={"Content-Type": "text/html; private="+MARKER})
    with pytest.raises(MediaIOError) as error: download_candidate(candidate(), tmp_path/"x", session=Mock(get=Mock(return_value=response)))
    assert error.value.safe_error_class == "invalid_container"
    assert error.value.evidence["content_type"]["mime"] == "text/html"
    assert MARKER not in json.dumps(error.value.evidence)


def test_actual_image_download_probe_and_full_load_have_separate_evidence(tmp_path):
    out = io.BytesIO(); Image.new("RGB", (1280,720), "blue").save(out, format="JPEG"); data=out.getvalue()
    response=Response(body=data,headers={"Content-Length":str(len(data)),"Content-Type":"image/jpeg"})
    evidence = io_evidence(); path=tmp_path/"fixture.jpg"
    download_candidate(candidate(),path,session=Mock(get=Mock(return_value=response)),evidence=evidence)
    measured=probe_media(path,"image",evidence=evidence)
    assert measured["width"]==1280 and evidence["full_decode"]["status"]=="passed"
    assert evidence["download_body"]["received_bytes"]==len(data) and evidence["file_sha256"]["sha256"]==measured["sha256"]


@pytest.mark.parametrize("fault,code", [("probe_exit","probe_failed"),("bad_json","probe_failed"),("wrong_container","invalid_container"),
    ("decode_exit","full_decode_failed"),("decode_stderr","full_decode_failed")])
def test_probe_container_and_full_decode_errors_remain_distinct(tmp_path, fault, code):
    path=tmp_path/"fixture.mp4";path.write_bytes(b"x"*2048)
    data={"streams":[{"codec_type":"video","width":1920,"height":1080}],"format":{"duration":"8","format_name":"matroska,webm"}}
    if fault=="wrong_container":data["format"]["format_name"]="hls"
    probe=Mock(stdout="{bad" if fault=="bad_json" else json.dumps(data))
    failure=subprocess.CalledProcessError(1,["binary"],stderr=MARKER)
    responses=[failure] if fault=="probe_exit" else [probe,failure if fault=="decode_exit" else Mock(stderr=MARKER if fault=="decode_stderr" else "")]
    with patch("src.media_processing.media_io.subprocess.run",side_effect=responses) as run, pytest.raises(MediaIOError) as error: probe_media(path,"video")
    assert error.value.safe_error_class==code and MARKER not in json.dumps(error.value.evidence)
    assert all("file,pipe" in call.args[0] for call in run.call_args_list)
    if code=="full_decode_failed":assert error.value.evidence["container_probe"]["status"]=="passed"


def test_scene_rejection_preserves_safe_io_stage_without_raw_error(tmp_path):
    evidence=io_evidence();evidence["download_http"]={"status":"failed","http_status":403,"error_class":"http_error"}
    def fail(c,p):raise MediaIOError("media_download_failed","http_error",evidence)
    with pytest.raises(SceneMediaError) as error:
        select_storyboard_media(script(),tmp_path/"w",providers=[Provider([candidate()])],history=MediaHistory(tmp_path/"h"),downloader=fail)
    rejection=error.value.report["scenes"][0]["rejections"][-1]
    assert rejection["safe_error_class"]=="http_error" and rejection["io_stages"]["download_http"]["http_status"]==403
    assert not (tmp_path/"h").exists()


def test_commons_diagnostics_do_not_confuse_licensed_metadata_with_download_success(tmp_path):
    c=replace(candidate("fixture"),media_type="video",title="ocean waves beach",description="ocean waves beach",tags=(),duration=12)
    provider=Provider([c]);provider.last_diagnostics={"metadata_http_responses":[{"kind":"video","http_status":200}]}
    def reject(c,p,*,evidence):
        evidence["download_http"]={"status":"failed","http_status":403,"error_class":"http_error"}
        raise MediaIOError("media_download_failed","http_error",evidence)
    def licensed(scene,*,evidence):evidence["source_page_http"]={"status":"passed","http_status":200};return {"status":"passed"}
    result=diagnose_commons(tmp_path,provider=provider,downloader=reject,license_checker=licensed,live_provider_calls=False)
    item=result["candidates"][0]
    assert item["stages"]["license_evidence_http"]["status"]=="passed" and item["safe_error_class"]=="http_error"
    assert item["stages"]["full_decode"]["status"]==item["stages"]["consumer_render"]["status"]=="not_reached"
    assert len(item["stages"])==12 and not list(tmp_path.glob('commons-io-*'))


@pytest.mark.parametrize("chain_passed,same_sha",[(True,True),(True,False),(False,True)])
def test_diagnostic_consumer_link_requires_actual_render_stage_and_same_bytes_not_global_success(chain_passed,same_sha):
    stages=io_evidence();stages.update(consumer_render={"status":"not_reached"},final_mp4_qc={"status":"not_reached"})
    d={"candidates":[{"media_id":"1","measured_file":{"sha256":"actual"},"stages":stages}]}
    chain={"status":"passed" if chain_passed else "blocked_unverified","selected_media":[{"media_id":"1","sha256":"actual" if same_sha else "different"}],
        "stages":{"strict_media_wrapper":{"status":"passed"},"final_qc":{"status":"passed"},"full_av_decode":{"status":"passed"}}}
    link_actual_consumer(d,chain)
    assert (stages["consumer_render"]["status"]=="passed")==same_sha
    assert d["actual_chain_status"]==chain["status"]


def test_actual_consumer_render_failure_has_safe_stage_and_preserves_production(tmp_path):
    failure=subprocess.CalledProcessError(1,["ffmpeg"],stderr=MARKER)
    with patch("scripts.phase4b_consumer_chain.mp.run_media_pipeline",side_effect=failure):
        result=run_consumer_chain(tmp_path/"chain",providers=[],duration=1.2,live_provider_calls=False)
    assert result["safe_error_class"]=="consumer_render_failed" and result["failure_stage"]=="strict_media_wrapper"
    assert result["protected_files_unchanged"] and MARKER not in json.dumps(result)


def test_workflow_defaults_cookie_only_and_gates_before_browser_or_provider():
    text=Path('.github/workflows/phase4_media_probe.yml').read_text();data=yaml.safe_load(text);events=data.get('on',data.get(True))
    assert not ((events.get('workflow_dispatch') or {}).get('inputs')), "stock_access_mode input'u kaldirilmis olmali"
    assert "options: [cookie_only, auto]" not in text and "secrets.PEXELS_API_KEY" not in text \
        and "secrets.PIXABAY_API_KEY" not in text, "API-key 'auto' yolu kaldirilmis olmali"
    assert 'PEXELS_API_KEY' not in text and 'PIXABAY_API_KEY' not in text, "API key secret referanslari kaldirilmis olmali"
    assert data['permissions']=={'contents':'read'}
    steps=data['jobs']['media-consumer-proof']['steps'];pref=next(i for i,s in enumerate(steps) if s.get('id')=='preflight')
    assert all(pref<i for i,s in enumerate(steps) if any(marker in s.get('name','') for marker in ['Chromium probe','Media system','Live providers']))
    assert 'main.py' not in text and 'youtube_studio_uploader.js' not in text


def test_real_download_trace_survives_a_subsequent_probe_failure(tmp_path):
    response=Response(body=b'not-a-valid-image'*256,headers={'Content-Type':'image/jpeg'})
    with patch('src.media_processing.media_providers.requests.get',return_value=response),pytest.raises(SceneMediaError) as error:
        select_storyboard_media(script(),tmp_path/'w',providers=[Provider([candidate()])],history=MediaHistory(tmp_path/'history.json'))
    failures=[r for r in error.value.report['scenes'][0]['rejections'] if 'io_stages' in r]
    assert failures and failures[0]['safe_error_class']=='invalid_container'
    assert failures[0]['io_stages']['download_http']['http_status']==200
    assert failures[0]['io_stages']['download_body']['status']=='passed'
    assert failures[0]['io_stages']['container_probe']['status']=='failed'
    assert failures[0]['io_stages']['full_decode']['status']=='not_reached'


def test_commons_file_denial_and_official_deed_http_are_independently_observed():
    from scripts.phase4b_live_evidence import verify_commons_file_pages
    source=Response(status=403);deed=Response();deed.text='<p>share adapt attribution</p>'
    trace={}
    scene={'source_url':'https://commons.wikimedia.org/wiki/File:Fixture.webm',
        'license':{'url':'https://creativecommons.org/licenses/by/4.0','creator':'Fixture Author'}}
    with patch('src.media_processing.media_providers.requests.get',side_effect=[source,deed]) as get,pytest.raises(ValueError,match='source_or_license_http_failed'):
        verify_commons_file_pages(scene,evidence=trace)
    assert get.call_count==2 and trace['source_page_http']['http_status']==403
    assert trace['license_deed_http']['http_status']==200 and trace['license_deed_http']['status']=='passed'


def test_actual_render_error_is_linked_only_to_the_same_measured_candidate():
    d={'candidates':[{'media_id':'1','measured_file':{'sha256':'same'},'stages':{'consumer_render':{'status':'not_reached'}}}]}
    chain={'status':'failed','selected_media':[{'media_id':'1','sha256':'same'}],
        'stages':{'strict_media_wrapper':{'status':'failed','error_class':'consumer_render_failed'}}}
    link_actual_consumer(d,chain)
    assert d['candidates'][0]['stages']['consumer_render']['error_class']=='consumer_render_failed'
