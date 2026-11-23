"""experiment_ledger.py birim testleri (BOBI SKILL §5 deney makine kaydı)."""

import json
import pathlib

import scripts.experiment_ledger as ledger


def test_load_missing_file_returns_empty_schema(tmp_path: pathlib.Path):
    data = ledger.load(tmp_path / "yok.json")
    assert data == {"version": 1, "experiments": []}


def test_upsert_appends_new_record():
    records = []
    out = ledger.upsert(records, {"id": "E1", "variant": "A", "status": "active"})
    assert len(out) == 1
    assert out[0]["id"] == "E1"


def test_upsert_same_id_variant_updates_in_place():
    records = [{"id": "E1", "variant": "A", "status": "planned", "note": "ilk"}]
    out = ledger.upsert(records, {"id": "E1", "variant": "A", "status": "measuring", "note": "ölçülüyor"})
    assert len(out) == 1
    assert out[0]["status"] == "measuring"
    assert out[0]["note"] == "ölçülüyor"


def test_upsert_different_variant_is_separate_record():
    records = [{"id": "E1", "variant": "A"}]
    out = ledger.upsert(records, {"id": "E1", "variant": "B"})
    assert len(out) == 2


def test_rejects_unknown_status():
    errors = ledger.validate({"id": "E1", "status": "super-hizli"})
    assert any("status" in e for e in errors)


def test_rejects_empty_id_and_unknown_field():
    errors = ledger.validate({"id": "", "status": "active"})
    assert any("id" in e for e in errors)
    errors2 = ledger.validate({"id": "E1", "tezgah": "x"})
    assert any("alanlar" in e for e in errors2)


def test_add_writes_json_and_list_cli_shape(tmp_path: pathlib.Path, capsys):
    path = tmp_path / "experiments.json"
    entry = ledger.add(
        path, id="E9", variant="48h", hypothesis="gecikmeli dagilim",
        metric="total views, deleted count", window="14d", status="active",
        note="kurulu kontrol grubu",
    )
    assert entry["status"] == "active"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["experiments"][0]["id"] == "E9"
    lines = ledger.format_list(data["experiments"])
    assert "E9" in lines and "active" in lines


def test_add_invalid_status_raises(tmp_path: pathlib.Path):
    try:
        ledger.add(tmp_path / "x.json", id="E1", status="patlatildi")
    except ValueError:
        return
    raise AssertionError("geçersiz status ValueError vermeli")
