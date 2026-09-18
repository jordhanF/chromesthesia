# tests/test_similarity.py
import numpy as np
import pytest

from server.similarity import nearest_ids, normalize_matrix


def test_normaliza_cada_coluna_para_zero_um():
    m = normalize_matrix(np.array([[0.0, 10.0], [5.0, 20.0], [10.0, 30.0]]))
    assert m[:, 0].tolist() == [0.0, 0.5, 1.0]
    assert m[:, 1].tolist() == [0.0, 0.5, 1.0]


def test_coluna_constante_vira_zero_em_vez_de_nan():
    """Divisao por amplitude zero nao pode virar NaN e contaminar a distancia."""
    m = normalize_matrix(np.array([[7.0, 1.0], [7.0, 2.0]]))
    assert m[:, 0].tolist() == [0.0, 0.0]
    assert not np.isnan(m).any()


def test_vizinhos_vem_do_mais_proximo_para_o_mais_distante():
    m = np.array([[0.0], [0.1], [0.5], [1.0]])
    assert nearest_ids(m, [10, 11, 12, 13], target_id=10, k=2) == [11, 12]


def test_o_proprio_alvo_nao_aparece_entre_os_vizinhos():
    m = np.array([[0.0], [0.1], [0.2]])
    assert 10 not in nearest_ids(m, [10, 11, 12], target_id=10, k=2)


def test_k_maior_que_o_disponivel_devolve_o_que_existe():
    m = np.array([[0.0], [1.0]])
    assert len(nearest_ids(m, [1, 2], target_id=1, k=99)) == 1


def test_id_desconhecido_e_erro():
    with pytest.raises(KeyError):
        nearest_ids(np.array([[0.0]]), [1], target_id=999, k=1)
