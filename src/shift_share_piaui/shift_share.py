"""Decomposição shift-share de Montañia & Márquez e a tipologia de regiões.

Porte de ``shift.montania.marquez()`` e ``tipo_regiao()``, idênticos nos dois
scripts em R. A versão em Python é vetorizada, mas preserva a aritmética do R,
inclusive o que acontece quando o estoque inicial é zero: a divisão gera
``inf`` ou ``nan``, e é isso que alimenta a classificação.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Componentes na ordem em que o R os empilhava no data.frame consolidado.
COMPONENTES: tuple[str, ...] = ("NE", "IM", "CE", "RIE", "RSE", "RCCE")

COLUNAS_RESULTADO: tuple[str, ...] = COMPONENTES + (
    "Estoque_mun_t0",
    "Estoque_mun_t1",
    "Estoque_nac_t0",
    "Estoque_nac_t1",
    "VarTot",
    "conferencia",
    "status",
    "classificacao_regiao",
)

# Octantes de sinais (CE, RIE, RSE) -> tipo. Fora deles (algum efeito igual a
# zero, ou indefinido) a região cai em 'T-1'.
_TIPOS_POR_SINAL: dict[tuple[int, int, int], str] = {
    (1, 1, 1): "T1",
    (1, 1, -1): "T2",
    (1, -1, 1): "T3",
    (1, -1, -1): "T4",
    (-1, 1, 1): "T5",
    (-1, 1, -1): "T6",
    (-1, -1, 1): "T7",
    (-1, -1, -1): "T8",
}

TIPO_INDEFINIDO = "T-1"

# Status do par de estoques (mesma convenção do R).
STATUS_OK = 0
STATUS_ENTRADA = 1  # estoque zero em t0 e positivo em t1
STATUS_VAZIO = 2  # estoque zero nos dois anos


def tipo_regiao(ce: float, rie: float, rse: float) -> str:
    """Classifica um setor pelo sinal dos efeitos CE, RIE e RSE.

    Qualquer valor ausente (``nan``) devolve ``'T-1'``, assim como as
    fronteiras em que algum efeito é exatamente zero.
    """
    valores = (ce, rie, rse)
    if any(valor is None or (isinstance(valor, float) and np.isnan(valor)) for valor in valores):
        return TIPO_INDEFINIDO
    if any(pd.isna(valor) for valor in valores):
        return TIPO_INDEFINIDO
    sinais = tuple(int(np.sign(valor)) for valor in valores)
    return _TIPOS_POR_SINAL.get(sinais, TIPO_INDEFINIDO)


def classificar_regioes(ce, rie, rse) -> np.ndarray:
    """Versão vetorizada de :func:`tipo_regiao`."""
    ce = np.asarray(ce, dtype="float64")
    rie = np.asarray(rie, dtype="float64")
    rse = np.asarray(rse, dtype="float64")

    tipos = np.full(ce.shape, TIPO_INDEFINIDO, dtype=object)
    definidos = ~(np.isnan(ce) | np.isnan(rie) | np.isnan(rse))
    sinais = np.stack(
        [np.sign(ce), np.sign(rie), np.sign(rse)],
        axis=-1,
    )
    for chave, rotulo in _TIPOS_POR_SINAL.items():
        casa = definidos & np.all(sinais == np.asarray(chave, dtype="float64"), axis=-1)
        tipos[casa] = rotulo
    return tipos


def _status(regiao_t0: np.ndarray, regiao_t1: np.ndarray) -> np.ndarray:
    status = np.full(regiao_t0.shape, STATUS_OK, dtype="int64")
    status[(regiao_t0 == 0) & (regiao_t1 == 0)] = STATUS_VAZIO
    status[(regiao_t0 == 0) & (regiao_t1 > 0)] = STATUS_ENTRADA
    return status


def shift_montania_marquez(
    regiao_t0,
    regiao_t1,
    nacao_t0,
    nacao_t1,
) -> pd.DataFrame:
    """Decompõe a variação do estoque de cada setor de uma região.

    Parameters
    ----------
    regiao_t0, regiao_t1:
        Estoque por setor da região analisada nos anos inicial e final.
    nacao_t0, nacao_t1:
        Estoque por setor da referência de comparação (Piauí, Nordeste ou
        Brasil), nos mesmos setores e na mesma ordem.

    Returns
    -------
    DataFrame com uma linha por setor e as colunas de
    :data:`COLUNAS_RESULTADO`.

    Notes
    -----
    Sendo ``G`` o crescimento da referência, ``g`` o da região, ``Gi`` o do
    setor na referência e ``gi`` o do setor na região, os componentes são::

        NE   = G  * E0        efeito nacional
        IM   = (Gi - G) * E0  efeito estrutural (mix industrial)
        CE   = (gi - Gi) * E0 efeito competitivo
        RIE  = (gi - g)  * E0 efeito diferencial intrarregional
        RSE  = (g  - G)  * E0 efeito regional
        RCCE = (G  - gi) * E0 efeito cruzado, que fecha a identidade

    Somados, devolvem a variação observada (``VarTot`` == ``conferencia``)
    sempre que o estoque inicial do setor é positivo.
    """
    regiao_t0 = np.asarray(regiao_t0, dtype="float64")
    regiao_t1 = np.asarray(regiao_t1, dtype="float64")
    nacao_t0 = np.asarray(nacao_t0, dtype="float64")
    nacao_t1 = np.asarray(nacao_t1, dtype="float64")

    tamanhos = {
        len(regiao_t0),
        len(regiao_t1),
        len(nacao_t0),
        len(nacao_t1),
    }
    if len(tamanhos) != 1:
        raise ValueError(
            "Os quatro vetores de estoque precisam ter o mesmo número de setores; "
            f"recebi {sorted(tamanhos)}."
        )

    soma_regiao_t0 = regiao_t0.sum()
    soma_regiao_t1 = regiao_t1.sum()
    soma_nacao_t0 = nacao_t0.sum()
    soma_nacao_t1 = nacao_t1.sum()

    # Estoque inicial zerado produz inf/nan de propósito: é o que o R fazia, e
    # é o que leva o setor para a classificação 'T-1'.
    with np.errstate(divide="ignore", invalid="ignore"):
        crescimento_nacao = (soma_nacao_t1 - soma_nacao_t0) / soma_nacao_t0
        crescimento_regiao = (soma_regiao_t1 - soma_regiao_t0) / soma_regiao_t0
        crescimento_setor_regiao = (regiao_t1 - regiao_t0) / regiao_t0
        crescimento_setor_nacao = (nacao_t1 - nacao_t0) / nacao_t0

        efeito_nacional = crescimento_nacao * regiao_t0
        efeito_estrutural = (crescimento_setor_nacao - crescimento_nacao) * regiao_t0
        efeito_competitivo = (crescimento_setor_regiao - crescimento_setor_nacao) * regiao_t0
        efeito_intrarregional = (crescimento_setor_regiao - crescimento_regiao) * regiao_t0
        efeito_regional = (crescimento_regiao - crescimento_nacao) * regiao_t0
        efeito_cruzado = (crescimento_nacao - crescimento_setor_regiao) * regiao_t0

        # Somar inf com -inf também devolve nan de propósito: o setor entrou
        # do zero e a decomposição não se fecha para ele.
        variacao_total = (
            efeito_nacional
            + efeito_estrutural
            + efeito_competitivo
            + efeito_intrarregional
            + efeito_regional
            + efeito_cruzado
        )

    return pd.DataFrame(
        {
            "NE": efeito_nacional,
            "IM": efeito_estrutural,
            "CE": efeito_competitivo,
            "RIE": efeito_intrarregional,
            "RSE": efeito_regional,
            "RCCE": efeito_cruzado,
            "Estoque_mun_t0": regiao_t0.astype("int64"),
            "Estoque_mun_t1": regiao_t1.astype("int64"),
            "Estoque_nac_t0": nacao_t0.astype("int64"),
            "Estoque_nac_t1": nacao_t1.astype("int64"),
            "VarTot": variacao_total,
            "conferencia": (regiao_t1 - regiao_t0).astype("int64"),
            "status": _status(regiao_t0, regiao_t1),
            "classificacao_regiao": classificar_regioes(
                efeito_competitivo, efeito_intrarregional, efeito_regional
            ),
        }
    )
