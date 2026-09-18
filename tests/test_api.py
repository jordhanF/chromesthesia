# tests/test_api.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine.commands import CommandQueue, LoadPreset, StatePublisher
from indexer.db import connect, init_schema, upsert_preset
from indexer.milk_parser import PresetFeatures
from server.api import build_router


def _features(name, family="Hypnotic", subfamily="Polar Warp", decay=0.9, n_shapes=1):
    return PresetFeatures(
        path=f"C:/x/{family}/{subfamily}/{name}.milk", name=name, family=family,
        subfamily=subfamily, is_mirror=False, warp_anim_speed=1.0, zoom=1.0, rot=0.0,
        warp=0.2, zoom_exponent=1.0, sx=1.0, sy=1.0, decay=decay, echo_alpha=0.0,
        echo_zoom=1.0, gamma=1.2, brighten=False, darken=False, invert=False,
        solarize=False, darken_center=False, wave_r=0.3, wave_g=0.2, wave_b=0.6,
        wave_alpha=0.01, n_shapes=n_shapes, n_waves=0, has_warp_shader=True,
        has_comp_shader=True, psversion=2,
    )


@pytest.fixture()
def cliente(tmp_path):
    db = tmp_path / "t.sqlite"
    con = connect(db)
    init_schema(con)
    upsert_preset(con, _features("alfa"))
    upsert_preset(con, _features("beta", decay=0.5, n_shapes=4))
    upsert_preset(con, _features("gama", family="Geometric", subfamily="Cube"))
    con.commit()
    con.close()

    fila = CommandQueue()
    estado = StatePublisher()
    app = FastAPI()
    app.include_router(build_router(db, tmp_path / "previews", fila, estado))
    return TestClient(app), fila


def test_lista_familias_com_contagem(cliente):
    c, _ = cliente
    dados = c.get("/api/families").json()
    assert {"family": "Hypnotic", "count": 2} in dados
    assert {"family": "Geometric", "count": 1} in dados


def test_lista_presets_filtrando_por_familia(cliente):
    c, _ = cliente
    dados = c.get("/api/presets", params={"family": "Geometric"}).json()
    assert [p["name"] for p in dados["items"]] == ["gama"]
    assert dados["total"] == 1


def test_lista_pagina(cliente):
    c, _ = cliente
    dados = c.get("/api/presets", params={"limit": 1, "offset": 1}).json()
    assert len(dados["items"]) == 1
    assert dados["total"] == 3


def test_preset_traz_id_utilizavel(cliente):
    c, _ = cliente
    item = c.get("/api/presets").json()["items"][0]
    assert isinstance(item["id"], int) and item["id"] > 0


def test_carregar_preset_enfileira_comando(cliente):
    c, fila = cliente
    pid = c.get("/api/presets").json()["items"][0]["id"]
    assert c.post(f"/api/load/{pid}").status_code == 200
    comandos = fila.drain()
    assert len(comandos) == 1 and isinstance(comandos[0], LoadPreset)


def test_carregar_id_inexistente_da_404(cliente):
    c, _ = cliente
    assert c.post("/api/load/99999").status_code == 404


def test_similares_nao_incluem_o_proprio(cliente):
    c, _ = cliente
    pid = c.get("/api/presets").json()["items"][0]["id"]
    ids = [p["id"] for p in c.get(f"/api/similar/{pid}").json()]
    assert pid not in ids


def test_estado_do_motor(cliente):
    c, _ = cliente
    dados = c.get("/api/state").json()
    assert dados["frame"] == 0
    assert dados["audio_connected"] is False


def test_poster_ausente_da_404(cliente):
    c, _ = cliente
    pid = c.get("/api/presets").json()["items"][0]["id"]
    assert c.get(f"/api/poster/{pid}").status_code == 404
