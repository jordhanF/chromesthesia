# tests/test_milk_parser.py
from indexer.milk_parser import parse_milk_text


def test_le_pares_chave_valor():
    texto = "MILKDROP_PRESET_VERSION=201\nfDecay=0.980\nzoom=1.01191\n"
    assert parse_milk_text(texto) == {
        "MILKDROP_PRESET_VERSION": "201",
        "fDecay": "0.980",
        "zoom": "1.01191",
    }


def test_ignora_cabecalho_de_secao_e_linhas_vazias():
    texto = "[preset00]\n\nfDecay=0.5\n"
    assert parse_milk_text(texto) == {"fDecay": "0.5"}


def test_preserva_espacos_do_valor_em_linhas_de_shader():
    texto = "warp_3=`    ret = tex2D( sampler_main, uv ).xyz*.5;\n"
    assert parse_milk_text(texto)["warp_3"] == "`    ret = tex2D( sampler_main, uv ).xyz*.5;"


def test_linha_sem_igual_e_ignorada():
    assert parse_milk_text("lixo sem igual\nfDecay=0.5\n") == {"fDecay": "0.5"}


def test_chave_repetida_primeira_vence():
    """PresetFileParser.cpp:174-178 da libprojectM: so a primeira ocorrencia
    de uma chave e guardada ("Only add first occurrence to mimic Milkdrop
    behaviour"), para mimetizar o Milkdrop.
    """
    texto = "warp=0\nwarp=1\nwarp=2\n"
    assert parse_milk_text(texto) == {"warp": "0"}


def test_chave_repetida_primeira_vence_com_linha_de_equacao_orfa():
    """Regressao de corpus: Dancer/Glowsticks/15.milk define zoom=1.00000 e,
    na ultima linha do arquivo, uma equacao orfa sem prefixo de indice
    ('zoom = zoom + 0.1*sin(time*3.14);'). Ambas as linhas usam a chave
    'zoom'; a primeira deve vencer.
    """
    texto = "zoom=1.00000\nzoom = zoom + 0.1*sin(time*3.14);\n"
    assert parse_milk_text(texto) == {"zoom": "1.00000"}


from indexer.milk_parser import read_bool, read_float, read_int


def test_read_float_usa_padrao_quando_ausente():
    assert read_float({}, "fDecay", 0.96) == 0.96


def test_read_float_usa_padrao_quando_invalido():
    assert read_float({"fDecay": "abc"}, "fDecay", 0.96) == 0.96


def test_read_float_aceita_espacos():
    assert read_float({"zoom": "  1.5 "}, "zoom", 0.0) == 1.5


def test_read_bool_trata_zero_e_um():
    assert read_bool({"bInvert": "1"}, "bInvert") is True
    assert read_bool({"bInvert": "0"}, "bInvert") is False
    assert read_bool({}, "bInvert") is False


def test_read_int_trunca_float():
    assert read_int({"PSVERSION": "2.000"}, "PSVERSION", 0) == 2


from indexer.milk_parser import count_enabled, has_shader


def test_count_enabled_conta_so_os_ligados():
    raw = {
        "shapecode_0_enabled": "1",
        "shapecode_1_enabled": "0",
        "shapecode_2_enabled": "1",
        "shapecode_2_sides": "4",
    }
    assert count_enabled(raw, "shapecode") == 2


def test_count_enabled_zero_quando_nenhum():
    assert count_enabled({"fDecay": "0.5"}, "shapecode") == 0


def test_count_enabled_nao_confunde_prefixos():
    raw = {"wavecode_0_enabled": "1", "shapecode_0_enabled": "1"}
    assert count_enabled(raw, "wavecode") == 1


def test_has_shader_detecta_primeira_linha():
    assert has_shader({"warp_1": "`shader_body"}, "warp") is True
    assert has_shader({"comp_1": "`shader_body"}, "warp") is False
    assert has_shader({}, "comp") is False


from pathlib import Path

from indexer.milk_parser import derive_taxonomy


def test_taxonomia_com_subfamilia():
    root = Path("C:/x/presets")
    p = root / "presets-cream-of-the-crop" / "Hypnotic" / "Polar Warp" / "foo.milk"
    assert derive_taxonomy(p, root) == ("Hypnotic", "Polar Warp", False)


def test_taxonomia_sem_subfamilia():
    root = Path("C:/x/presets")
    p = root / "presets-cream-of-the-crop" / "! Transition" / "bar.milk"
    assert derive_taxonomy(p, root) == ("! Transition", "", False)


def test_taxonomia_marca_espelhado():
    root = Path("C:/x/presets")
    p = root / "presets-cream-of-the-crop" / "Dancer" / "Whirl Mirror" / "baz.milk"
    assert derive_taxonomy(p, root) == ("Dancer", "Whirl Mirror", True)


def test_taxonomia_fora_da_raiz_vira_desconhecido():
    assert derive_taxonomy(Path("C:/outro/foo.milk"), Path("C:/x/presets")) == ("", "", False)


from indexer.milk_parser import PresetFeatures, parse_preset_file


MINIMO = """MILKDROP_PRESET_VERSION=201
PSVERSION=2
[preset00]
fDecay=0.950
fGammaAdj=1.900
fVideoEchoAlpha=0.250
fVideoEchoZoom=1.169
fWarpAnimSpeed=1.500
fZoomExponent=1.05000
zoom=1.01191
rot=0.02000
warp=0.26300
sx=1.02000
sy=0.98000
bInvert=1
bBrighten=1
bDarken=1
bSolarize=1
bDarkenCenter=1
wave_r=0.300
wave_g=0.250
wave_b=0.600
fWaveAlpha=0.001
shapecode_0_enabled=1
shapecode_1_enabled=0
wavecode_0_enabled=1
wavecode_1_enabled=1
warp_1=`shader_body
comp_1=`shader_body
"""


def test_parse_preset_file_monta_registro(tmp_path):
    """Cobre todos os 29 campos de PresetFeatures (mais 'path').

    A fixture MINIMO da a cada campo um valor distinto e diferente do
    padrao correspondente (ver tabela de defaults em parse_preset_file),
    para que um bug de copy-paste entre dois campos do mesmo tipo -- por
    exemplo, trocar as chaves de wave_r e wave_b -- derrube este teste em
    vez de passar em silencio.
    """
    root = tmp_path / "presets"
    d = root / "pack" / "Hypnotic" / "Polar Warp"
    d.mkdir(parents=True)
    f = d / "exemplo.milk"
    f.write_text(MINIMO, encoding="utf-8")

    feat = parse_preset_file(f, root)

    assert isinstance(feat, PresetFeatures)
    assert feat.path == str(f)
    assert feat.name == "exemplo"
    assert feat.family == "Hypnotic"
    assert feat.subfamily == "Polar Warp"
    assert feat.is_mirror is False
    assert feat.warp_anim_speed == 1.500
    assert feat.zoom == 1.01191
    assert feat.rot == 0.02000
    assert feat.warp == 0.26300
    assert feat.zoom_exponent == 1.05000
    assert feat.sx == 1.02000
    assert feat.sy == 0.98000
    assert feat.decay == 0.950
    assert feat.echo_alpha == 0.250
    assert feat.echo_zoom == 1.169
    assert feat.gamma == 1.900
    assert feat.brighten is True
    assert feat.darken is True
    assert feat.invert is True
    assert feat.solarize is True
    assert feat.darken_center is True
    assert feat.wave_r == 0.300
    assert feat.wave_g == 0.250
    assert feat.wave_b == 0.600
    assert feat.wave_alpha == 0.001
    assert feat.n_shapes == 1
    assert feat.n_waves == 2
    assert feat.has_warp_shader is True
    assert feat.has_comp_shader is True
    assert feat.psversion == 2


def test_parse_preset_file_tolera_campos_ausentes(tmp_path):
    """Campos ausentes devem cair nos padroes da libprojectM (PresetState.hpp),
    nao nas antigas medianas do corpus.
    """
    root = tmp_path / "presets"
    d = root / "pack" / "Geometric" / "Cube"
    d.mkdir(parents=True)
    f = d / "pelado.milk"
    f.write_text("MILKDROP_PRESET_VERSION=201\n[preset00]\n", encoding="utf-8")

    feat = parse_preset_file(f, root)

    assert feat.warp_anim_speed == 1.0
    assert feat.zoom == 1.0
    assert feat.decay == 0.98
    assert feat.gamma == 2.0
    assert feat.echo_zoom == 2.0
    assert feat.warp == 1.0
    assert feat.wave_r == 1.0
    assert feat.wave_g == 1.0
    assert feat.wave_b == 1.0
    assert feat.wave_alpha == 0.8
    assert feat.n_shapes == 0
    assert feat.has_warp_shader is False


def test_parse_preset_file_aceita_bytes_invalidos(tmp_path):
    """Varios presets do corpus tem bytes que nao sao UTF-8 validos."""
    root = tmp_path / "presets"
    d = root / "pack" / "Drawing" / "Liquid"
    d.mkdir(parents=True)
    f = d / "sujo.milk"
    f.write_bytes(b"[preset00]\nfDecay=0.5\n// coment\xe1rio latin1\n")

    feat = parse_preset_file(f, root)

    assert feat.decay == 0.5


def test_parse_preset_file_tolera_caminho_acima_de_max_path(tmp_path):
    """Regressao: achada ao validar contra o corpus real (Tarefa 5).

    Um preset do pacote cream-of-the-crop tem nome longo o bastante para que
    o caminho completo ultrapasse os 260 caracteres do limite MAX_PATH do
    Windows. path.read_text() falha com FileNotFoundError nesse caso mesmo
    o arquivo existindo; parse_preset_file precisa contornar isso.
    """
    root = tmp_path / "presets"
    d = root / "pack" / "Drawing" / "Explosions Mirror"
    d.mkdir(parents=True)
    nome_longo = ("x" * 220) + ".milk"
    f = d / nome_longo
    assert len(str(f)) > 260

    caminho_estendido = "\\\\?\\" + str(f.resolve())
    with open(caminho_estendido, "w", encoding="utf-8") as fh:
        fh.write("fDecay=0.5\n")

    feat = parse_preset_file(f, root)

    assert feat.decay == 0.5
