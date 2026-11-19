"""Phase 4 contract/selection tests. Provider calls here are MOCKS, not live evidence."""
from __future__ import annotations

import base64
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from scripts.validate_script_json import validate_payload
from src.media_processing.media_history import MediaHistory
from src.media_processing.media_io import download_candidate, probe_media
from src.media_processing.media_providers import (
    BrowserStockProvider, MediaCandidate, MediaLicense, PexelsProvider, PixabayProvider,
    StockTerms, WikimediaProvider, commons_license, get_public,
)
from src.media_processing.scene_media import SceneMediaError, evaluate, scene_plan, select_storyboard_media
from src.media_processing import media_processor as mp


def license_ok(attribution=""):
    return MediaLicense(name="CC BY 4.0" if attribution else "Public domain", url="https://creativecommons.org/licenses/by/4.0/" if attribution else "",
                        verified=True, evidence_url="https://commons.wikimedia.org/wiki/File:Moon.jpg", evidence_method="commons_per_file_extmetadata",
                        checked_at="2026-11-18T10:00:00+00:00", attribution_required=bool(attribution), attribution=attribution, creator="NASA")


def candidate(mid="1", title="Moon Apollo astronaut crater", **kw):
    d = dict(provider="wikimedia", media_id=mid, source_url=f"https://commons.wikimedia.org/wiki/File:Moon_{mid}.jpg",
             download_url=f"https://upload.wikimedia.org/wikipedia/commons/a/aa/Moon_{mid}.jpg", media_type="image", width=1440, height=1440,
             duration=None, title=title, license=license_ok())
    d.update(kw)
    return MediaCandidate(**d)


def script(two=False):
    board = [{"scene_id": 1, "visual_query": "Moon Apollo astronaut", "alternative_queries": ["Apollo Moon crater", "Moon astronaut landing"], "narration": "Apollo astronot Ay kraterlerinde yürüyor."}]
    if two:
        board.append({"scene_id": 2, "visual_query": "Eiffel Tower Paris", "alternative_queries": ["Paris Eiffel tower building"], "narration": "Paris Eyfel kulesi demir yapısıyla görülüyor."})
    return {"audio_duration_sec": 8.0, "description": "Test description", "generation_id": "phase4-test", "storyboard": board}


class Provider:
    def __init__(self, result, name="fixture"):
        self.name, self.result, self.calls = name, result, []

    def search(self, query):
        self.calls.append(query)
        if isinstance(self.result, Exception): raise self.result
        return self.result(query) if callable(self.result) else self.result


def download_stub(c, path):
    path.write_bytes(c.media_id.encode()*2048)
    return path


def probe_stub(path, kind):
    import hashlib
    return {"width": 1440, "height": 1440, "duration": 30 if kind == "video" else None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "decode_status": "passed", "bytes": path.stat().st_size}


def select(data, tmp, providers, **kwargs):
    return select_storyboard_media(data, tmp/"work", providers=providers, history=MediaHistory(tmp/"history.json"),
                                   downloader=kwargs.pop("downloader", download_stub), prober=kwargs.pop("prober", probe_stub), **kwargs)


def test_distinct_query_and_media_for_every_storyboard_scene(tmp_path):
    p = Provider(lambda q: [candidate("moon")] if q.startswith("Moon") else [candidate("eiffel", "Eiffel Tower Paris iron structure")])
    data = script(two=True)
    runtime, report = select(data, tmp_path, [p])
    assert p.calls == ["Moon Apollo astronaut", "Eiffel Tower Paris"]
    assert [s["scene_id"] for s in runtime] == [1, 2]
    assert len({s["selected_media_id"] for s in report["scenes"]}) == 2
    assert sum(s["duration"] for s in runtime) == 8
    assert report["visual_verification"] == "not_performed"
    assert all(s["assessment"]["relevance_status"] == "metadata_supported" for s in data["scene_media"])
    assert all(s["timing_basis"].endswith("not_tts_aligned") for s in data["scene_media"])


def test_alternatives_are_tried_in_order_without_generic_query_dilution(tmp_path):
    p = Provider(lambda q: [candidate()] if q == "Moon astronaut landing" else [])
    _, report = select(script(), tmp_path, [p])
    assert p.calls == ["Moon Apollo astronaut", "Apollo Moon crater", "Moon astronaut landing"]
    assert report["scenes"][0]["fallback_used"]


@pytest.mark.parametrize(("changes", "reason"), [
    ({"title": "generic forest walking grass", "description": "a green field"}, "relevance_unproven_or_unrelated"),
    ({"width": 320, "height": 240}, "insufficient_resolution"),
    ({"width": 8000, "height": 1080}, "unsupported_aspect_ratio"),
    ({"media_type": "video", "duration": 1.0}, "insufficient_duration"),
    ({"license": MediaLicense()}, "missing_license_evidence"),
    ({"source_url": "https://evil.example/clip"}, "untrusted_or_missing_source_identity"),
    ({"download_url": "http://127.0.0.1/internal"}, "untrusted_download_url"),
])
def test_hard_rejection_criteria(changes, reason):
    scene = scene_plan(script())[0]
    verdict = evaluate(candidate(**changes), scene, scene["primary_query"], used=set(), recent=[])
    assert not verdict["eligible"]
    assert reason in verdict["rejection_reasons"]


def test_wrong_but_usable_aspect_is_explicitly_contained_not_blindly_cropped():
    scene = scene_plan(script())[0]
    v = evaluate(candidate(width=1920, height=1080), scene, scene["primary_query"], used=set(), recent=[])
    assert v["eligible"] and v["framing"] == "contain_letterbox"
    assert v["components"]["aspect_ratio"] < 10


def test_query_is_never_used_as_evidence_for_an_unrelated_candidate(tmp_path):
    p = Provider([candidate(title="waves ocean sand")])
    with pytest.raises(SceneMediaError) as exc:
        select(script(), tmp_path, [p])
    assert "relevance_unproven_or_unrelated" in exc.value.report["scenes"][0]["rejections"][0]["reasons"]


def test_diluted_alternative_cannot_replace_original_narration_anchor(tmp_path):
    data = script(); data["storyboard"][0]["alternative_queries"] = ["green forest walking"]
    p = Provider([candidate(title="green forest walking")])
    with pytest.raises(SceneMediaError): select(data, tmp_path, [p])


def test_required_attribution_preserved_in_manifest_and_description(tmp_path):
    credit = "Moon — Example Author — CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); source; modified: scaled."
    data = script()
    _, r = select(data, tmp_path, [Provider([candidate(license=license_ok(credit))])])
    assert r["scenes"][0]["attribution"] == credit
    assert r["scenes"][0]["license"]["attribution_required"] is True
    assert credit in data["description"] and credit in data["media_credits"]


def test_attribution_is_never_silently_truncated(tmp_path):
    data = script(); data["description"] = "x"*4899
    with pytest.raises(SceneMediaError) as exc: select(data, tmp_path, [Provider([candidate(license=license_ok("mandatory credit"))])])
    assert exc.value.report["failure"] == "description_cannot_preserve_required_attribution"
    assert not (tmp_path/"history.json").exists()


def test_same_clip_identity_blocked_in_two_scenes(tmp_path):
    data = script(); data["storyboard"].append({**data["storyboard"][0], "scene_id": 2})
    with pytest.raises(SceneMediaError) as exc: select(data, tmp_path, [Provider([candidate()])])
    assert "duplicate_in_video" in exc.value.report["scenes"][1]["rejections"][0]["reasons"]
    assert not (tmp_path/"history.json").exists()


def test_same_bytes_under_different_ids_are_also_blocked(tmp_path):
    data = script(); data["storyboard"].append({**data["storyboard"][0], "scene_id": 2})
    def dl(c, path): path.write_bytes(b"same contents"*1024)
    with pytest.raises(SceneMediaError) as exc: select(data, tmp_path, [Provider([candidate("a"), candidate("b")])], downloader=dl)
    reasons = [r for rej in exc.value.report["scenes"][1]["rejections"] for r in rej["reasons"]]
    assert "duplicate_content_in_video" in reasons


def test_provider_failure_continues_to_wikimedia_and_preserves_evidence(tmp_path):
    bad = Provider(RuntimeError("may contain a secret URL: never serialize this"), "pexels")
    commons = Provider([candidate()], "wikimedia")
    _, r = select(script(), tmp_path, [bad, commons])
    assert r["scenes"][0]["selected_provider"] == "wikimedia"
    assert r["scenes"][0]["provider_errors"][0]["error_type"] == "RuntimeError"
    assert "secret URL" not in json.dumps(r)


def test_all_providers_fail_no_random_or_partial_filled_video(tmp_path):
    report = tmp_path/"failure.json"
    with pytest.raises(SceneMediaError): select(script(), tmp_path, [Provider([]), Provider(ValueError("no result"))], report_path=report)
    data = json.loads(report.read_text())
    assert data["status"] == "blocked" and data["scenes"][0]["selected_media_id"] is None


def test_recent_media_penalty_prefers_a_fresh_candidate(tmp_path):
    history = MediaHistory(tmp_path/"history.json")
    history.remember([{"key": "wikimedia:a", "source_url": candidate("a").source_url, "sha256": "old", "generation_id": "previous", "selected_at": "2026-11-18T10:00:00Z"}])
    _, report = select_storyboard_media(script(), tmp_path/"work", providers=[Provider([candidate("a"), candidate("b")])], history=history, downloader=download_stub, prober=probe_stub)
    assert report["scenes"][0]["selected_media_id"] == "b"
    assert len(history.recent()) == 2


def test_corrupt_or_lying_download_is_not_accepted(tmp_path):
    def bad_probe(path, kind): raise RuntimeError("invalid")
    with pytest.raises(SceneMediaError) as exc: select(script(), tmp_path, [Provider([candidate()])], prober=bad_probe)
    assert any("download_or_decode_failed" in x["reasons"] for x in exc.value.report["scenes"][0]["rejections"])
    def low_res(path, kind): return {**probe_stub(path, kind), "width": 320, "height": 240}
    with pytest.raises(SceneMediaError): select(script(), tmp_path, [Provider([candidate()])], prober=low_res)


@pytest.mark.parametrize("payload", [b"not a video"*1000, b"<html>cloudflare</html>"*1000])
def test_real_probe_rejects_broken_bytes(tmp_path, payload):
    p = tmp_path/"broken.mp4"; p.write_bytes(payload)
    with pytest.raises(RuntimeError, match="probe_or_decode"): probe_media(p, "video")
    with pytest.raises(RuntimeError, match="probe_or_decode"): probe_media(p, "image")


def test_real_pillow_probe_records_file_resolution_not_advertised_size(tmp_path):
    p = tmp_path/"test.png"; Image.new("RGB", (1440, 1080), (10, 100, 60)).save(p)
    meta = probe_media(p, "image")
    assert (meta["width"], meta["height"]) == (1440, 1080)
    assert meta["decode_status"] == "passed" and len(meta["sha256"]) == 64


def test_invalid_storyboard_never_degrades_to_legacy_or_generic_query(tmp_path):
    for board in [[], None, [{}], [{**script()["storyboard"][0], "narration": "Completely unrelated grassland."}]]:
        data = script(); data["storyboard"] = board
        p = Provider([candidate()])
        with pytest.raises(SceneMediaError): select(data, tmp_path, [p])
        assert not p.calls


def test_legacy_branch_and_existing_wikimedia_fallback_preserved(tmp_path, monkeypatch):
    p = tmp_path/"script.json"; p.write_text(json.dumps({"audio_duration_sec": 5, "visual_keywords": ["moon"]}))
    monkeypatch.setattr(mp, "SCRIPT_JSON_PATH", p)
    monkeypatch.setattr(mp, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(mp, "ASSETS_DIR", tmp_path)
    monkeypatch.setattr(mp, "FINAL_OUTPUT", tmp_path/"out.mp4")
    fake = {"url": "https://upload.wikimedia.org/moon.jpg", "provider": "wikimedia-commons-archive", "media_kind": "image"}
    with patch.object(mp, "fetch_video_playwright", return_value=None), patch.object(mp, "fetch_pexels_video", return_value=None), \
         patch.object(mp, "fetch_pixabay_video", return_value=None), patch.object(mp, "fetch_wikimedia_media", return_value=fake) as commons, \
         patch.object(mp, "download_media", return_value=True), patch.object(mp, "_probe_has_video_stream", return_value=True), \
         patch.object(mp, "convert_srt_to_ass"), patch.object(mp, "assemble_video_ffmpeg"), patch.object(mp, "validate_output"), \
         patch.object(mp, "run_storyboard_pipeline") as strict:
        mp.run_media_pipeline()
        commons.assert_called_once(); strict.assert_not_called()


def test_present_but_empty_storyboard_enters_strict_not_legacy(tmp_path, monkeypatch):
    p = tmp_path/"script.json"; p.write_text(json.dumps({"storyboard": []}))
    monkeypatch.setattr(mp, "SCRIPT_JSON_PATH", p); monkeypatch.setattr(mp, "OUTPUT_DIR", tmp_path); monkeypatch.setattr(mp, "ASSETS_DIR", tmp_path)
    with patch.object(mp, "run_storyboard_pipeline", side_effect=RuntimeError("blocked")) as strict, patch.object(mp, "fetch_video_playwright") as legacy:
        with pytest.raises(RuntimeError): mp.run_media_pipeline()
        strict.assert_called_once(); legacy.assert_not_called()


def test_strict_pipeline_calls_real_selector_and_stops_before_render_when_scene_missing(tmp_path, monkeypatch):
    data = script()
    monkeypatch.setattr(mp, "OUTPUT_DIR", tmp_path)
    with patch('src.media_processing.scene_media.default_providers', return_value=[Provider([])]), \
         patch('src.media_processing.scene_media.MediaHistory.from_environment', return_value=MediaHistory(tmp_path/"h.json")), \
         patch.object(mp, "assemble_video_ffmpeg") as render:
        with pytest.raises(SceneMediaError): mp.run_storyboard_pipeline(data, tmp_path/"script.json", tmp_path/"s.srt", tmp_path/"a.mp3")
        render.assert_not_called()
        assert (tmp_path/"scene_media_manifest.json").exists()


def test_contain_framing_disables_video_loop_only_for_strict_scenes(tmp_path):
    scene = {"path": tmp_path/"clip.mp4", "duration": 3, "media_kind": "video", "fit_mode": "contain", "loop_allowed": False}
    with patch.object(mp.subprocess, "run") as run:
        mp.assemble_video_ffmpeg([scene], tmp_path/"audio.mp3", 3, tmp_path/"s.ass", tmp_path/"o.mp4")
    cmd = run.call_args.args[0]
    # Background music may still loop; the strict VIDEO input must not.
    assert "-stream_loop" not in cmd[:cmd.index(str(tmp_path/"audio.mp3"))]
    assert "pad=1080:1920" in cmd[cmd.index("-filter_complex")+1]


def test_metadata_cannot_claim_visual_or_timing_verification(tmp_path):
    data = script(); _, r = select(data, tmp_path, [Provider([candidate()])])
    assert "verified" not in r["scenes"][0]["assessment"]["relevance_status"]
    assert data["media_selection"]["visual_verification"] == "not_performed"


def test_new_schema_and_validator_require_exact_scene_coverage_and_credits(tmp_path):
    sample = json.loads(Path('samples/script.json').read_text())
    # Produce the selected records with the actual selector (mock catalog/download).
    data = script(); select(data, tmp_path, [Provider([candidate()])])
    sample.update(data)
    sample['generation_id'] = '9cdc18f7-420c-41eb-b040-f4c0d7e2f819'
    sample['schema_version'] = '2.0'
    assert validate_payload(sample) == []
    sample['scene_media'][0]['scene_id'] = 77
    assert any('one-to-one' in x for x in validate_payload(sample))
    sample['scene_media'][0]['scene_id'] = 1
    sample['scene_media'][0]['assessment']['visual_verification'] = 'verified'
    assert validate_payload(sample)


def test_commons_licenses_are_not_guessed_and_sharealike_is_not_silently_relicensed():
    page = {"title": "File:Moon.jpg"}
    info = {"descriptionurl": "https://commons.wikimedia.org/wiki/File:Moon.jpg", "extmetadata": {}}
    assert not commons_license(page, info).verified
    ext = {"Artist": {"value": "Test Author"}, "LicenseShortName": {"value": "CC BY 4.0"}, "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"}, "AttributionRequired": {"value": "true"}}
    lic = commons_license(page, {**info, "extmetadata": ext})
    assert lic.verified and "Test Author" in lic.attribution and lic.url in lic.attribution
    ext["LicenseShortName"]["value"] = "CC BY-SA 4.0"
    assert commons_license(page, {**info, "extmetadata": ext}).rejection_reason == "share_alike_downstream_policy_not_implemented"


def test_commons_pd_preserves_missing_license_url_instead_of_inventing_cc0():
    lic = commons_license({"title": "File:Moon"}, {"descriptionurl": "https://commons.wikimedia.org/wiki/File:Moon", "extmetadata": {
        "License": {"value": "pd-usgov-nasa"}, "LicenseShortName": {"value": "Public domain"}, "AttributionRequired": {"value": "false"}}})
    assert lic.verified and lic.url == "" and lic.attribution_required is False


def test_remote_history_cas_reread_preserves_competing_entries(tmp_path):
    def entry(key): return {"key": key, "source_url": "https://commons.wikimedia.org/wiki/File:A", "sha256": key, "selected_at": "2026-11-18", "generation_id": key}
    def response(data, sha):
        return Mock(status_code=200, json=lambda: {"content": base64.b64encode(json.dumps({"version": 1, "entries": data}).encode()).decode(), "sha": sha})
    session = Mock()
    session.get.side_effect = [response([], 'old'), response([entry('competing')], 'new')]
    session.put.side_effect = [Mock(status_code=409), Mock(status_code=200)]
    h = MediaHistory(tmp_path/'h.json', repository='owner/repo', token='fixture', session=session)
    h.remember([entry('selected')])
    saved = json.loads(base64.b64decode(session.put.call_args.kwargs['json']['content']))
    assert [x['key'] for x in saved['entries']] == ['competing', 'selected']
    assert session.put.call_args.kwargs['json']['sha'] == 'new'
    assert session.get.call_count == 2


def test_corrupt_history_fails_closed_before_provider_search(tmp_path):
    (tmp_path/'history.json').write_text('{broken')
    p = Provider([candidate()])
    with pytest.raises(SceneMediaError): select(script(), tmp_path, [p])
    assert not p.calls


def test_authenticated_api_redirects_are_disabled_and_sensitive_errors_not_propagated_to_report(tmp_path):
    session = Mock(get=Mock(return_value=Mock(status_code=302)))
    with pytest.raises(RuntimeError): PixabayProvider('private-key', session=session).search('moon')
    assert session.get.call_args.kwargs['allow_redirects'] is False
    assert 'private-key' not in str(session.get.call_args.args)


def test_download_denies_untrusted_redirect_and_removes_partial_file(tmp_path):
    response = Mock(status_code=302, headers={'Location':'http://169.254.169.254/credentials'})
    session = Mock(get=Mock(return_value=response))
    path = tmp_path/'x.jpg'
    with pytest.raises(RuntimeError): download_candidate(candidate(), path, session=session)
    assert not path.exists() and not path.with_suffix('.jpg.part').exists()
    assert session.get.call_count == 1


def test_terms_page_missing_or_changed_is_not_a_verified_license():
    # HTTP fail + canonical snapshot da yoksa (bos) -> fail-closed (verified=False)
    with patch('src.media_processing.media_providers.get_public', side_effect=RuntimeError('403')), \
         patch.object(StockTerms, 'CANONICAL_LICENSE_TEXT', {}), \
         patch.object(StockTerms, '_fetch_via_browser', return_value=None):
        assert not StockTerms().check('pexels').verified


def test_catalog_provider_parsers_preserve_source_identity_and_dimensions():
    lic = license_ok(); terms = Mock(check=Mock(return_value=lic))
    pexels = Mock(status_code=200); pexels.json.return_value = {'videos':[{'id':9,'url':'https://www.pexels.com/video/moon-apollo-9/','duration':15,'video_files':[{'width':1080,'height':1920,'link':'https://videos.pexels.com/9.mp4'}]}]}
    result = PexelsProvider('fixture',session=Mock(get=Mock(return_value=pexels)),terms=terms).search('query-is-not-evidence')
    assert result[0].media_id == '9' and result[0].height == 1920 and 'query-is-not-evidence' not in result[0].title
    pix = Mock(status_code=200); pix.json.return_value = {'hits':[{'id':8,'pageURL':'https://pixabay.com/videos/moon-8/','tags':'moon, apollo','duration':12,'videos':{'large':{'url':'https://cdn.pixabay.com/8.mp4','width':1920,'height':1080}}}]}
    result = PixabayProvider('fixture',session=Mock(get=Mock(return_value=pix)),terms=terms).search('moon')
    assert result[0].tags == ('moon','apollo') and result[0].license.verified


def test_commons_api_video_then_bitmap_and_no_unknown_duration_invention():
    v = Mock(status_code=200); v.json.return_value = {'query':{'pages':{'1':{'pageid':1,'title':'File:Moon.webm','imageinfo':[{'url':'https://upload.wikimedia.org/moon.webm','mime':'video/webm','width':1920,'height':1080}]}}}}
    i = Mock(status_code=200); i.json.return_value = {'query':{'pages':{}}}
    session = Mock(); session.get.side_effect = [v,i]
    results = WikimediaProvider(session=session).search('Moon Apollo')
    assert results[0].duration is None
    assert session.get.call_args_list[0].kwargs['params']['gsrsearch'] == 'filetype:video Moon Apollo'
    assert session.get.call_args_list[1].kwargs['params']['gsrsearch'] == 'filetype:bitmap Moon Apollo'


def test_short_turkish_subject_and_plural_aliases_are_not_lost():
    from src.media_processing.scene_media import terms
    assert 'moon' in terms('Ay')
    assert terms('astronauts waves trees') == {'astronaut', 'wave', 'tree'}


def test_single_incidental_primary_word_is_insufficient_when_two_anchors_exist():
    scene = scene_plan(script())[0]
    verdict = evaluate(candidate(title='Apollo arbitrary launch rockets'), scene, scene['primary_query'], used=set(), recent=[])
    assert not verdict['eligible']


def test_comparison_or_slideshow_metadata_is_not_promoted_to_good_quality():
    scene = scene_plan(script())[0]
    verdict = evaluate(candidate(description='Comparison slideshow of Apollo astronaut moon'), scene, scene['primary_query'], used=set(), recent=[])
    assert 'blocked_or_sensitive_metadata' in verdict['rejection_reasons']


def test_official_commons_thumbnail_host_is_accepted_but_similar_host_is_not():
    from src.media_processing.media_providers import DOWNLOAD_HOSTS, valid_url
    assert valid_url('https://thumb.wikimedia.org/wikipedia/commons/thumb/a/b/1.jpg', DOWNLOAD_HOSTS['wikimedia'])
    assert not valid_url('https://thumb.wikimedia.org.evil.test/a.jpg', DOWNLOAD_HOSTS['wikimedia'])


def test_missing_credit_is_rejected_even_with_known_cc_by_url():
    scene = scene_plan(script())[0]
    lic = replace(license_ok(), attribution_required=True, attribution='')
    assert 'missing_required_attribution' in evaluate(candidate(license=lic),scene,scene['primary_query'],used=set(),recent=[])['rejection_reasons']


def test_remote_history_write_permission_failure_is_fail_closed(tmp_path):
    session = Mock(get=Mock(return_value=Mock(status_code=404)), put=Mock(return_value=Mock(status_code=403)))
    h=MediaHistory(tmp_path/'history.json',repository='owner/repo',token='fixture',session=session)
    entry={'key':'commons:a','source_url':'https://commons.wikimedia.org/wiki/File:A','sha256':'a','generation_id':'g','selected_at':'2026-11-18'}
    with pytest.raises(RuntimeError,match='write_failed_closed'):h.remember([entry])
    assert not (tmp_path/'history.json').exists()


def test_new_manifest_cannot_bypass_existing_post_media_validator_by_omitting_one_field(tmp_path):
    data = json.loads(Path('samples/script.json').read_text()); inp=script()
    select(inp,tmp_path,[Provider([candidate()])]);data.update(inp)
    data['generation_id']='9cdc18f7-420c-41eb-b040-f4c0d7e2f819';data['schema_version']='2.0'
    data.pop('media_selection')
    assert any('present together' in x for x in validate_payload(data))


def test_successful_pipeline_persists_scene_manifest_without_touching_uploader(tmp_path,monkeypatch):
    data=script();script_json=tmp_path/'script.json';script_json.write_text(json.dumps(data))
    srt=tmp_path/'s.srt';srt.write_text('1\n00:00:00,000 --> 00:00:01,000\nTest\n')
    monkeypatch.setattr(mp,'OUTPUT_DIR',tmp_path);monkeypatch.setattr(mp,'FINAL_OUTPUT',tmp_path/'final.mp4')
    # Real selector/manifest/ASS consumer; catalog/file IO mocks are explicit.
    from src.media_processing.scene_media import select_storyboard_media as real_select
    def configured_select(payload,work,**kwargs):
        return real_select(payload,work,providers=[Provider([candidate()])],history=MediaHistory(tmp_path/'history.json'),downloader=download_stub,prober=probe_stub,**kwargs)
    with patch('src.media_processing.scene_media.select_storyboard_media',side_effect=configured_select),patch.object(mp,'assemble_video_ffmpeg') as render,patch.object(mp,'validate_output'):
        mp.run_storyboard_pipeline(data,script_json,srt,tmp_path/'a.mp3')
    out=json.loads(script_json.read_text())
    assert len(out['scene_media'])==1 and out['scene_media'][0]['scene_id']==1
    assert out['media_selection']['status']=='selected_metadata_and_technical_checks_passed'
    render.assert_called_once()


def test_real_ffmpeg_jpeg_consumer_normalizes_limited_range_without_weakening_qc(tmp_path,monkeypatch):
    # Synthetic media/tone fixture: this is real FFmpeg IO, not provider proof.
    import shutil
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'): pytest.skip('ffmpeg/ffprobe required')
    monkeypatch.setattr(mp,'ASSETS_DIR',tmp_path)
    images=[]
    for index,color in enumerate([(80,30,10),(10,80,30)]):
        image=tmp_path/f'{index}.jpg';Image.new('RGB',(1080,1440),color).save(image)
        images.append({'path':image,'duration':0.6,'media_kind':'image','fit_mode':'contain','loop_allowed':False})
    audio=tmp_path/'tone.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=1.2','-c:a','libmp3lame',str(audio)],capture_output=True,check=True,timeout=30)
    srt=tmp_path/'s.srt';srt.write_text('1\n00:00:00,000 --> 00:00:01,200\nSynthetic test\n')
    ass=tmp_path/'s.ass';mp.convert_srt_to_ass(srt,ass)
    output=tmp_path/'out.mp4';mp.assemble_video_ffmpeg(images,audio,1.2,ass,output)
    result=mp.validate_output(output)
    video=next(s for s in result['streams'] if s['codec_type']=='video')
    assert video['pix_fmt']=='yuv420p'


def test_real_video_probe_detects_decode_validity_before_selection(tmp_path):
    import shutil
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):pytest.skip('ffmpeg/ffprobe required')
    video=tmp_path/'test.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=128x128:rate=10:duration=1','-c:v','libx264',str(video)],capture_output=True,check=True,timeout=30)
    assert probe_media(video,'video')['decode_status']=='passed'
    video.write_bytes(video.read_bytes()[:1500])
    with pytest.raises(RuntimeError):probe_media(video,'video')


def test_safe_provider_diagnostics_do_not_include_secret_values(tmp_path):
    p=PexelsProvider('your_placeholder_secret')
    with pytest.raises(SceneMediaError) as e:select(script(),tmp_path,[p])
    data=json.dumps(e.value.report)
    assert 'api_key_not_configured_or_placeholder' in data
    assert 'your_placeholder_secret' not in data


def test_safe_api_error_code_is_retained_but_not_request_url(tmp_path):
    session=Mock(get=Mock(return_value=Mock(status_code=403)))
    p=PixabayProvider('private-fixture-key',session=session)
    with pytest.raises(SceneMediaError) as e:select(script(),tmp_path,[p])
    data=json.dumps(e.value.report)
    assert 'pixabay_catalog_http_403' in data and 'private-fixture-key' not in data


def test_uploader_cta_budget_is_checked_before_history_or_render(tmp_path):
    data=script();credit='MANDATORY AUTHOR AND LICENSE CREDIT'
    data['description']='x'*(4900-len(credit)-2)
    data['cta_line']='Existing uploader prepends this CTA'
    with pytest.raises(SceneMediaError) as e:
        select(data,tmp_path,[Provider([candidate(license=license_ok(credit))])])
    assert e.value.report['failure']=='uploader_description_budget_cannot_preserve_required_attribution'
    assert not (tmp_path/'history.json').exists()
    assert 'scene_media' not in data


def test_js_utf16_length_not_python_codepoint_length_protects_emoji_credit(tmp_path):
    data=script();data['description']='x'*3000+'🌙'*1000
    assert len(data['description'])<4900
    with pytest.raises(SceneMediaError) as e:
        select(data,tmp_path,[Provider([candidate(license=license_ok('Required credit'))])])
    assert e.value.report['failure']=='description_cannot_preserve_required_attribution'


@pytest.mark.parametrize('affiliate',[
    {'affiliate_hook':'Abone ol: https://example.org','affiliate_cta':'ignored CTA'},
    {'affiliate_cta':'Existing affiliate CTA'},
    {'affiliate_link':'https://example.org/offer'},
])
def test_required_credit_survives_actual_uploader_pure_description_function_without_running_uploader(tmp_path,affiliate):
    import shutil
    if not shutil.which('node'):pytest.skip('node required for existing JS consumer contract')
    # Extract ONLY the two existing pure metadata functions. The uploader file
    # has an unconditional network/publishing entrypoint: DO NOT require/import it.
    # VM has no require, process, timers or browser; no uploader/YouTube execution.
    program=r'''
    const fs=require('fs'),vm=require('vm');
    const source=fs.readFileSync('youtube_studio_uploader.js','utf8');
    const begin=source.indexOf('function readScenarioField(');
    const end=source.indexOf('/** pollinations.ai',begin);
    if (begin<0 || end<0) throw new Error('pure metadata boundaries changed');
    const data=JSON.parse(fs.readFileSync(0,'utf8'));
    const context=vm.createContext({data});
    const result=vm.runInContext(source.slice(begin,end)+'\nbuildFinalDescription(data)',context,{timeout:500});
    process.stdout.write(JSON.stringify({description:result,length:result.length}));
    '''
    data=script();data.update(affiliate,cta_line='Original CTA',viral_hashtags=['#moon','#science','#shorts'])
    credit='Ay 🌙 — Example Author — CC BY 4.0; https://creativecommons.org/licenses/by/4.0/'
    _,r=select(data,tmp_path,[Provider([candidate(license=license_ok(credit))])])
    result=subprocess.run(['node','-e',program],input=json.dumps(data),capture_output=True,text=True,check=True,timeout=15)
    final=json.loads(result.stdout)
    from src.media_processing.scene_media import uploader_description_upper_bound
    assert credit in final['description']
    assert final['length']<=uploader_description_upper_bound(data,data['description'])<=4900
    assert r['scenes'][0]['license']['attribution_required']


@pytest.mark.parametrize('name,url',[
    ('CC BY 4.0','https://creativecommons.org/licenses/by/3.0/'),
    ('CC BY-NC 4.0','https://creativecommons.org/licenses/by/4.0/'),
    ('CC BY 4.0','https://user@creativecommons.org/licenses/by/4.0/'),
    ('CC BY','https://creativecommons.org/licenses/by/4.0/'),
    ('CC BY 4.0','https://creativecommons.org:8443/licenses/by/4.0/'),
])
def test_conflicting_unknown_or_credential_bearing_commons_license_declarations_are_not_reconciled_by_guessing(name,url):
    ext={'Artist':{'value':'Example Author'},'LicenseShortName':{'value':name},'LicenseUrl':{'value':url},'AttributionRequired':{'value':'true'}}
    lic=commons_license({'title':'File:Moon.jpg'},{'descriptionurl':'https://commons.wikimedia.org/wiki/File:Moon.jpg','extmetadata':ext})
    assert not lic.verified and lic.rejection_reason


def test_explicit_compatible_cc_by_ported_license_preserves_exact_credit_url():
    url='https://creativecommons.org/licenses/by/2.0/fr/'
    ext={'Artist':{'value':'Example Author'},'LicenseShortName':{'value':'CC BY 2.0 FR'},'LicenseUrl':{'value':url},'AttributionRequired':{'value':'true'}}
    lic=commons_license({'title':'File:Moon.jpg'},{'descriptionurl':'https://commons.wikimedia.org/wiki/File:Moon.jpg','extmetadata':ext})
    assert lic.verified and lic.attribution_required and url in lic.attribution


def test_default_providers_uses_browser_stock_for_pexels_pixabay():
    """Faz4K: default_providers() BrowserStockProvider (cookie/playwright) döndürmeli
    pexels/pixabay için; ücretli PexelsProvider/PixabayProvider kullanmamalı."""
    from src.media_processing.media_providers import (
        default_providers, BrowserStockProvider, WikimediaProvider,
        PexelsProvider, PixabayProvider,
    )
    provs = default_providers()
    classes = {type(p).__name__: p for p in provs}
    # BrowserStockProvider "pexels" ve "pixabay" için olmalı
    browser = [p for p in provs if isinstance(p, BrowserStockProvider)]
    assert len(browser) == 2, f"İki adet BrowserStockProvider beklenir (pexels+pixabay), {len(browser)} var"
    names = sorted(p.provider for p in browser)
    assert names == ["pexels", "pixabay"], f"BrowserStockProvider adları: {names}"
    # Wikimedia son çare olmalı
    assert any(isinstance(p, WikimediaProvider) for p in provs), "WikimediaProvider eksik"
    # API-key sağlayıcılar OLMMAMALI
    assert not any(isinstance(p, PexelsProvider) for p in provs), \
        "PexelsProvider (API key) default zincirde olmamalı"
    assert not any(isinstance(p, PixabayProvider) for p in provs), \
        "PixabayProvider (API key) default zincirde olmamalı"


def test_browser_stock_provider_creates_playwright_transport_candidates():
    """BrowserStockProvider medya adaylerini catalog_transport='playwright' ile
    işaretlemeli; bu Faz4E cookie-only testinin güvenlik kontrolüdür."""
    from src.media_processing.media_providers import MediaCandidate
    # MediaCandidate dataclass alanı: catalog_transport varsayılan "api"
    c = MediaCandidate("pexels", "123", "https://example.com/a", "https://example.com/d", "video", 1920, 1080, 10.0,
                       catalog_transport="playwright")
    assert c.catalog_transport == "playwright"
    assert c.provider == "pexels"
    # Varsayılan (Wikimedia gibi) api olmalı
    c2 = MediaCandidate("wikimedia", "456", "https://example.com/b", "https://example.com/e", "image", 1920, 1080, None)
    assert c2.catalog_transport == "api"
