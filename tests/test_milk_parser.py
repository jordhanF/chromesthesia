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


# acrescentar em tests/test_milk_parser.py
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
