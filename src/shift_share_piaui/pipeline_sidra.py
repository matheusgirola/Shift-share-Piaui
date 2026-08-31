"""Shift-share das pesquisas agropecuárias do IBGE (PAM, PEVS, PPM).

Conversão de ``Economia-Regional-R/shift_share_ppm_todos_municipios.R``. O
script em R cobria uma pesquisa por vez, com o nome do arquivo escrito à mão;
aqui as cinco pesquisas estão declaradas em
:data:`shift_share_piaui.config.FONTES_SIDRA` e rodam no mesmo comando.

Os extratos do SIDRA já trazem Brasil, grandes regiões e Piauí como linhas ao
lado dos municípios, então a referência de comparação sai do próprio arquivo.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from shift_share_piaui.config import (
    REGIOES,
    Config,
    DEFAULT_CONFIG,
    FonteSidra,
)
from shift_share_piaui.leitura import (
    COLUNA_MUNICIPIO_SIDRA,
    ErroDeLeitura,
    formatar_dados_sidra,
)
from shift_share_piaui.r_compat import escrever_csv_r
from shift_share_piaui.shift_share import shift_montania_marquez


def _matriz(df: pd.DataFrame) -> tuple[list[str], np.ndarray]:
    unidades = df[COLUNA_MUNICIPIO_SIDRA].astype(str).tolist()
    return unidades, df.drop(columns=[COLUNA_MUNICIPIO_SIDRA]).to_numpy(dtype="int64")


def shift_share_de_um_ano(
    ano_t0: int,
    ano_t1: int,
    dados_t0: pd.DataFrame,
    dados_t1: pd.DataFrame,
    referencias: tuple[str, ...] = REGIOES,
    verbose: bool = True,
) -> pd.DataFrame:
    """Decomposição de todas as linhas do extrato para um par de anos.

    Todas as linhas mesmo: os agregados (Brasil, grandes regiões, Piauí)
    também são decompostos, como no script em R. O tratamento posterior os
    descarta -- ver :func:`shift_share_piaui.tratamento.tratar_base_sidra`.
    """
    if list(dados_t0.columns) != list(dados_t1.columns):
        raise ErroDeLeitura(
            f"SIDRA {ano_t0} x {ano_t1}: os produtos não coincidem entre os arquivos."
        )

    produtos = list(dados_t0.columns.drop(COLUNA_MUNICIPIO_SIDRA))
    nomes_t0, matriz_t0 = _matriz(dados_t0)
    nomes_t1, matriz_t1 = _matriz(dados_t1)
    indice_t0 = {nome: posicao for posicao, nome in enumerate(nomes_t0)}

    partes: list[pd.DataFrame] = []
    for referencia in referencias:
        if referencia not in indice_t0 or referencia not in nomes_t1:
            raise ErroDeLeitura(
                f"Referência {referencia!r} ausente do extrato do SIDRA."
            )
        if verbose:
            print(f"Shift-share SIDRA {ano_t0}->{ano_t1} | referência: {referencia}")

        nacao_t0 = matriz_t0[indice_t0[referencia]]
        nacao_t1 = matriz_t1[nomes_t1.index(referencia)]

        for posicao_t1, municipio in enumerate(nomes_t1):
            if municipio not in indice_t0:
                raise ErroDeLeitura(
                    f"Município {municipio!r} está em {ano_t1} mas não em {ano_t0}."
                )
            tabela = shift_montania_marquez(
                matriz_t0[indice_t0[municipio]],
                matriz_t1[posicao_t1],
                nacao_t0,
                nacao_t1,
            )
            tabela["subclasse"] = produtos
            tabela["NM_MUN_RAIS"] = municipio
            tabela["ANO_T0"] = ano_t0
            tabela["ANO_T1"] = ano_t1
            tabela["REFERENCIA_GEOGRAFICA"] = referencia
            partes.append(tabela)

    if not partes:
        return pd.DataFrame()
    return pd.concat(partes, ignore_index=True)


def executar_fonte(
    fonte: FonteSidra,
    cfg: Config = DEFAULT_CONFIG,
    verbose: bool = True,
) -> Path:
    """Roda o shift-share de uma pesquisa e grava o CSV consolidado."""
    dados_t1 = formatar_dados_sidra(cfg.arquivo_sidra(fonte, cfg.ano_t1_sidra))
    partes = [
        shift_share_de_um_ano(
            ano_t0=ano_t0,
            ano_t1=cfg.ano_t1_sidra,
            dados_t0=formatar_dados_sidra(cfg.arquivo_sidra(fonte, ano_t0)),
            dados_t1=dados_t1,
            verbose=verbose,
        )
        for ano_t0 in cfg.anos_t0_sidra
    ]
    consolidado = pd.concat(partes, ignore_index=True)
    return escrever_csv_r(consolidado, cfg.consolidado_sidra(fonte))


def executar(
    cfg: Config = DEFAULT_CONFIG,
    fontes: tuple[FonteSidra, ...] | None = None,
    verbose: bool = True,
) -> dict[str, Path]:
    """Roda o shift-share das pesquisas do IBGE configuradas."""
    fontes = cfg.fontes_sidra if fontes is None else fontes
    return {
        fonte.prefixo: executar_fonte(fonte, cfg=cfg, verbose=verbose) for fonte in fontes
    }
