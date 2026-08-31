"""Regressão contra o resultado que os scripts em R produziram.

O repositório traz ``python/Shift_share_todos_tipos_2013_bruto_brasil.xlsx``,
gerado pelo pipeline antigo (R + notebook). Este teste refaz em Python o
shift-share das linhas do PPM daquele arquivo e confere valor por valor -- é o
que sustenta a afirmação de que a conversão não mudou os números.

Os testes são pulados quando os dados reais não estão à mão (por exemplo, numa
cópia do repositório sem a pasta ``Dados/``).
"""

from __future__ import annotations

import pandas as pd
import pytest

from shift_share_piaui.config import DEFAULT_CONFIG
from shift_share_piaui.leitura import formatar_dados_sidra
from shift_share_piaui.pipeline_sidra import shift_share_de_um_ano
from shift_share_piaui.tratamento import formatar_texto_producao, remover_uf

ANO_T0, ANO_T1 = 2013, 2024
COMPONENTES = ["NE", "IM", "CE", "RIE", "RSE", "RCCE"]

_FONTE = next(f for f in DEFAULT_CONFIG.fontes_sidra if f.prefixo == "PPM_Efetivo_rebanhos")
_REFERENCIA_R = (
    DEFAULT_CONFIG.raiz / "python" / (f"Shift_share_todos_tipos_{ANO_T0}_bruto_brasil.xlsx")
)
_ENTRADAS = [
    DEFAULT_CONFIG.arquivo_sidra(_FONTE, ANO_T0),
    DEFAULT_CONFIG.arquivo_sidra(_FONTE, ANO_T1),
]

pytestmark = pytest.mark.skipif(
    not _REFERENCIA_R.exists() or not all(caminho.exists() for caminho in _ENTRADAS),
    reason="dados reais do repositório indisponíveis",
)


@pytest.fixture(scope="module")
def resultado_r() -> pd.DataFrame:
    """Linhas do PPM de efetivo de rebanhos na saída do pipeline antigo."""
    abas = pd.ExcelFile(_REFERENCIA_R)
    partes = [pd.read_excel(abas, aba) for aba in abas.sheet_names]
    completo = pd.concat(partes, ignore_index=True)
    return completo[(completo["Fonte"] == "PPM") & (completo["Unidade de medida"] == "cabeças")]


@pytest.fixture(scope="module")
def resultado_python() -> pd.DataFrame:
    """O mesmo recorte, recalculado pelo pipeline em Python."""
    calculado = shift_share_de_um_ano(
        ano_t0=ANO_T0,
        ano_t1=ANO_T1,
        dados_t0=formatar_dados_sidra(_ENTRADAS[0]),
        dados_t1=formatar_dados_sidra(_ENTRADAS[1]),
        referencias=("Brasil",),
        verbose=False,
    )
    calculado["NM_MUN"] = calculado["NM_MUN_RAIS"].map(remover_uf)
    calculado["subclasse"] = calculado["subclasse"].map(formatar_texto_producao)
    return calculado


def _alinhar(resultado_r: pd.DataFrame, resultado_python: pd.DataFrame) -> pd.DataFrame:
    chave = ["NM_MUN", "subclasse"]
    return resultado_r.merge(resultado_python, on=chave, suffixes=("_r", "_py"), validate="1:1")


def test_o_recorte_de_referencia_nao_esta_vazio(resultado_r: pd.DataFrame):
    assert len(resultado_r) > 100


def test_todas_as_linhas_do_r_foram_reencontradas(
    resultado_r: pd.DataFrame, resultado_python: pd.DataFrame
):
    alinhado = _alinhar(resultado_r, resultado_python)
    assert len(alinhado) == len(resultado_r)


@pytest.mark.parametrize("componente", COMPONENTES)
def test_cada_componente_bate_com_o_resultado_do_r(
    resultado_r: pd.DataFrame, resultado_python: pd.DataFrame, componente: str
):
    alinhado = _alinhar(resultado_r, resultado_python)
    assert alinhado[f"{componente}_py"].to_numpy() == pytest.approx(
        alinhado[f"{componente}_r"].to_numpy(), rel=1e-9, nan_ok=True
    )


def test_estoques_e_classificacao_batem_com_o_resultado_do_r(
    resultado_r: pd.DataFrame, resultado_python: pd.DataFrame
):
    alinhado = _alinhar(resultado_r, resultado_python)
    for coluna in ["Estoque_mun_t0", "Estoque_mun_t1", "Estoque_nac_t0", "Estoque_nac_t1"]:
        assert alinhado[f"{coluna}_py"].tolist() == alinhado[f"{coluna}_r"].tolist()
    assert (
        alinhado["classificacao_regiao_py"].tolist() == alinhado["classificacao_regiao_r"].tolist()
    )
