# tests/test_db.py
from pathlib import Path

from indexer.db import connect, count_presets, init_schema, iter_presets, upsert_preset
from indexer.milk_parser import PresetFeatures


def _features(name="a", family="Hypnotic", subfamily="Polar Warp", decay=0.9, n_shapes=1):
    return PresetFeatures(
        path=f"C:/x/{family}/{subfamily}/{name}.milk", name=name, family=family,
        subfamily=subfamily, is_mirror=False, warp_anim_speed=1.0, zoom=1.0, rot=0.0,
        warp=0.2, zoom_exponent=1.0, sx=1.0, sy=1.0, decay=decay, echo_alpha=0.0,
        echo_zoom=1.0, gamma=1.2, brighten=False, darken=False, invert=False,
        solarize=False, darken_center=False, wave_r=0.3, wave_g=0.2, wave_b=0.6,
        wave_alpha=0.01, n_shapes=n_shapes, n_waves=0, has_warp_shader=True,
        has_comp_shader=True, psversion=2,
    )


def test_insere_e_recupera(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    upsert_preset(con, _features())
    con.commit()

    linhas = list(iter_presets(con))
    assert len(linhas) == 1
    assert linhas[0]["name"] == "a"
    assert linhas[0]["family"] == "Hypnotic"
    assert linhas[0]["has_warp_shader"] == 1


def test_upsert_e_idempotente(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    upsert_preset(con, _features(decay=0.9))
    upsert_preset(con, _features(decay=0.5))
    con.commit()

    assert count_presets(con) == 1
    assert list(iter_presets(con))[0]["decay"] == 0.5


def test_filtra_por_familia(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    upsert_preset(con, _features(name="a", family="Hypnotic"))
    upsert_preset(con, _features(name="b", family="Geometric"))
    con.commit()

    nomes = [r["name"] for r in iter_presets(con, family="Geometric")]
    assert nomes == ["b"]


def test_consulta_por_faixa_de_features(tmp_path):
    """A Fase 2 depende disso: e o motivo de ser SQLite e nao JSON."""
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    upsert_preset(con, _features(name="lento", decay=0.99, n_shapes=0))
    upsert_preset(con, _features(name="denso", decay=0.50, n_shapes=4))
    con.commit()

    cur = con.execute("SELECT name FROM presets WHERE decay < 0.8 AND n_shapes > 2")
    assert [r[0] for r in cur] == ["denso"]


def test_init_schema_e_reentrante(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    init_schema(con)
    assert count_presets(con) == 0
