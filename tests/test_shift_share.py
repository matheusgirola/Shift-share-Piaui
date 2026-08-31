"""A decomposição shift-share e a tipologia de regiões.

Os valores esperados são calculados à mão a partir da definição dos
componentes -- não do próprio código -- para que o teste falhe se a fórmula
mudar.
"""

from __future__ import annotations

import numpy as np
import pytest

from shift_share_piaui.shift_share import (
    STATUS_ENTRADA,
    STATUS_OK,
    STATUS_VAZIO,
    classificar_regioes,
    shift_montania_marquez,
    tipo_regiao,
)


@pytest.mark.parametrize(
    ("sinais", "esperado"),
    [
        ((1, 1, 1), "T1"),
        ((1, 1, -1), "T2"),
        ((1, -1, 1), "T3"),
        ((1, -1, -1), "T4"),
        ((-1, 1, 1), "T5"),
        ((-1, 1, -1), "T6"),
        ((-1, -1, 1), "T7"),
        ((-1, -1, -1), "T8"),
    ],
)
def test_os_oito_octantes_de_sinais(sinais: tuple[int, int, int], esperado: str):
    ce, rie, rse = (valor * 3.7 for valor in sinais)
    assert tipo_regiao(ce, rie, rse) == esperado


def test_efeito_exatamente_zero_cai_no_residuo():
    # Fronteira entre octantes: não pertence a nenhum tipo.
    assert tipo_regiao(1.0, 0.0, -1.0) == "T-1"


def test_efeito_indefinido_cai_no_residuo():
    assert tipo_regiao(float("nan"), 1.0, 1.0) == "T-1"


def test_classificacao_vetorizada_bate_com_a_escalar():
    ce = [1.0, -2.0, 0.0, float("nan"), 5.0]
    rie = [1.0, 3.0, 1.0, 1.0, -1.0]
    rse = [1.0, -1.0, 1.0, 1.0, 1.0]
    assert list(classificar_regioes(ce, rie, rse)) == [
        tipo_regiao(*valores) for valores in zip(ce, rie, rse, strict=True)
    ]


def test_componentes_conferem_com_a_conta_manual():
    # Uma região com dois setores. Referência: 100 -> 150 (G = 0,5).
    regiao_t0, regiao_t1 = [10, 20], [20, 20]
    nacao_t0, nacao_t1 = [40, 60], [80, 70]

    resultado = shift_montania_marquez(regiao_t0, regiao_t1, nacao_t0, nacao_t1)

    crescimento_nacao = (150 - 100) / 100  # G  = 0,50
    crescimento_regiao = (40 - 30) / 30  # g  = 0,3333...
    crescimento_setor = (20 - 10) / 10  # gi = 1,00 (setor 0)
    crescimento_setor_nacao = (80 - 40) / 40  # Gi = 1,00 (setor 0)

    primeiro = resultado.iloc[0]
    assert primeiro["NE"] == pytest.approx(crescimento_nacao * 10)
    assert primeiro["IM"] == pytest.approx((crescimento_setor_nacao - crescimento_nacao) * 10)
    assert primeiro["CE"] == pytest.approx((crescimento_setor - crescimento_setor_nacao) * 10)
    assert primeiro["RIE"] == pytest.approx((crescimento_setor - crescimento_regiao) * 10)
    assert primeiro["RSE"] == pytest.approx((crescimento_regiao - crescimento_nacao) * 10)
    assert primeiro["RCCE"] == pytest.approx((crescimento_nacao - crescimento_setor) * 10)


def test_a_decomposicao_fecha_na_variacao_observada():
    resultado = shift_montania_marquez([10, 20, 7], [20, 20, 3], [40, 60, 30], [80, 70, 25])
    assert resultado["VarTot"].to_numpy() == pytest.approx(resultado["conferencia"].to_numpy())


def test_status_distingue_setor_vazio_de_setor_que_nasce():
    resultado = shift_montania_marquez([0, 0, 5], [0, 3, 8], [10, 10, 10], [12, 12, 12])
    assert resultado["status"].tolist() == [STATUS_VAZIO, STATUS_ENTRADA, STATUS_OK]


def test_setor_que_nasce_do_zero_fica_sem_classificacao():
    # Estoque inicial zero deixa a taxa de crescimento indefinida; o setor não
    # entra em nenhum octante.
    resultado = shift_montania_marquez([0, 5], [3, 8], [10, 10], [12, 12])
    assert resultado.loc[0, "classificacao_regiao"] == "T-1"
    # pyrefly: ignore[no-matching-overload]  # stub do numpy: .loc[0, "CE"] é escalar
    assert np.isnan(resultado.loc[0, "CE"])
    assert resultado.loc[1, "classificacao_regiao"] != "T-1"


def test_estoques_sao_devolvidos_sem_alteracao():
    resultado = shift_montania_marquez([10, 20], [20, 25], [40, 60], [80, 70])
    assert resultado["Estoque_mun_t0"].tolist() == [10, 20]
    assert resultado["Estoque_mun_t1"].tolist() == [20, 25]
    assert resultado["Estoque_nac_t0"].tolist() == [40, 60]
    assert resultado["Estoque_nac_t1"].tolist() == [80, 70]
    assert resultado["conferencia"].tolist() == [10, 5]


def test_vetores_de_tamanhos_diferentes_sao_recusados():
    with pytest.raises(ValueError, match="mesmo número de setores"):
        shift_montania_marquez([1, 2], [1, 2, 3], [1, 2], [1, 2])


def test_uma_regiao_que_cresce_menos_que_a_nacao_tem_rse_negativo():
    # Região estagnada (30 -> 31) contra referência que cresce 50%.
    resultado = shift_montania_marquez([10, 20], [11, 20], [40, 60], [80, 70])
    assert (resultado["RSE"] < 0).all()
