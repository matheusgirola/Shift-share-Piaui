"""Shift-share dos vínculos da RAIS por subclasse da CNAE 2.0.

Conversão de ``Economia-Regional-R/shift_share_vinculosRAIS.R``. Para cada ano
inicial e cada referência geográfica (Piauí, Nordeste, Brasil), decompõe a
variação do estoque de vínculos de cada município do Piauí e grava um CSV por
referência -- de modo que o arquivo do Brasil já vem com uma única
classificação por (município, subclasse).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from shift_share_piaui.config import DEFAULT_CONFIG, REGIOES, Config
from shift_share_piaui.leitura import (
    COLUNA_MUNICIPIO_RAIS,
    ErroDeLeitura,
    conferir_ano,
    formatar_dados_rais,
)
from shift_share_piaui.shift_share import shift_montania_marquez

# Quando o extrato de regiões não traz a linha "Brasil", somar exatamente estas
# cinco linhas reconstrói o total nacional -- e só nesse caso a soma é segura.
MACRORREGIOES: tuple[str, ...] = ("Norte", "Nordeste", "Sudeste", "Sul", "Centro.Oeste")


def _matriz(df: pd.DataFrame) -> tuple[list[str], np.ndarray]:
    """Separa a coluna de unidade geográfica da matriz de estoques."""
    unidades = df[COLUNA_MUNICIPIO_RAIS].astype(str).tolist()
    return unidades, df.drop(columns=[COLUNA_MUNICIPIO_RAIS]).to_numpy(dtype="int64")


def _conferir_subclasses(esquerda: pd.DataFrame, direita: pd.DataFrame, contexto: str) -> None:
    colunas_esquerda = list(esquerda.columns)
    colunas_direita = list(direita.columns)
    if colunas_esquerda != colunas_direita:
        faltando = set(colunas_esquerda) ^ set(colunas_direita)
        raise ErroDeLeitura(
            f"{contexto}: as subclasses não coincidem entre os arquivos "
            f"({len(faltando)} divergência(s), ex.: {sorted(faltando)[:3]})."
        )


def estoque_nacional(regioes: pd.DataFrame) -> np.ndarray:
    """Estoque do Brasil a partir do extrato de regiões.

    Usa a linha ``Brasil`` quando ela existe. Só soma as grandes regiões como
    último recurso -- assim não há risco de somar Piauí/Nordeste/Brasil e
    duplicar o denominador.
    """
    unidades, matriz = _matriz(regioes)
    if "Brasil" in unidades:
        return matriz[unidades.index("Brasil")]
    if set(unidades) != set(MACRORREGIOES):
        warnings.warn(
            "Sem linha 'Brasil' no extrato de regiões, e as linhas presentes "
            f"não são as cinco grandes regiões ({unidades}); somando mesmo assim.",
            stacklevel=2,
        )
    return matriz.sum(axis=0)


def estoque_de_referencia(
    referencia: str,
    municipios: pd.DataFrame,
    regioes: pd.DataFrame,
) -> np.ndarray:
    """Vetor de estoques por subclasse da referência de comparação.

    Fica fora do laço de municípios de propósito: é uma definição por
    referência, e calculá-la uma única vez elimina a chance de passar o
    benchmark errado adiante.
    """
    if referencia == "Piauí":
        # O total estadual é a soma dos municípios do próprio extrato.
        return _matriz(municipios)[1].sum(axis=0)
    if referencia == "Brasil":
        return estoque_nacional(regioes)

    unidades, matriz = _matriz(regioes)
    if referencia not in unidades:
        raise ErroDeLeitura(
            f"Referência {referencia!r} ausente do extrato de regiões (disponíveis: {unidades})."
        )
    return matriz[unidades.index(referencia)]


def shift_share_de_um_ano(
    ano_t0: int,
    ano_t1: int,
    municipios_t0: pd.DataFrame,
    municipios_t1: pd.DataFrame,
    regioes_t0: pd.DataFrame,
    regioes_t1: pd.DataFrame,
    referencias: tuple[str, ...] = REGIOES,
    verbose: bool = True,
) -> pd.DataFrame:
    """Decomposição de todos os municípios para um par de anos."""
    _conferir_subclasses(municipios_t0, municipios_t1, f"RAIS {ano_t0} x {ano_t1}")
    _conferir_subclasses(municipios_t0, regioes_t0, f"RAIS {ano_t0} municípios x regiões")
    _conferir_subclasses(municipios_t1, regioes_t1, f"RAIS {ano_t1} municípios x regiões")

    subclasses = list(municipios_t0.columns.drop(COLUNA_MUNICIPIO_RAIS))
    nomes_t0, matriz_t0 = _matriz(municipios_t0)
    nomes_t1, matriz_t1 = _matriz(municipios_t1)
    indice_t0 = {nome: posicao for posicao, nome in enumerate(nomes_t0)}

    partes: list[pd.DataFrame] = []
    for referencia in referencias:
        if verbose:
            print(f"Shift-share RAIS {ano_t0}->{ano_t1} | referência: {referencia}")
        nacao_t0 = estoque_de_referencia(referencia, municipios_t0, regioes_t0)
        nacao_t1 = estoque_de_referencia(referencia, municipios_t1, regioes_t1)

        for posicao_t1, municipio in enumerate(nomes_t1):
            if municipio not in indice_t0:
                raise ErroDeLeitura(
                    f"Município {municipio!r} está em {ano_t1} mas não em {ano_t0}."
                )
            estoque_t0 = matriz_t0[indice_t0[municipio]]
            estoque_t1 = matriz_t1[posicao_t1]

            # Municípios sem nenhum vínculo nos dois anos não têm o que
            # decompor; qualquer subclasse com estoque já basta para entrar.
            if not ((estoque_t0 == 0) & (estoque_t1 == 0)).all():
                tabela = shift_montania_marquez(estoque_t0, estoque_t1, nacao_t0, nacao_t1)
                tabela["subclasse"] = subclasses
                tabela["NM_MUN_RAIS"] = municipio
                tabela["ANO_T0"] = ano_t0
                tabela["ANO_T1"] = ano_t1
                tabela["REFERENCIA_GEOGRAFICA"] = referencia
                partes.append(tabela)
            elif verbose:
                print(f"  estoque zerado para o município: {municipio}")

    if not partes:
        return pd.DataFrame()
    return pd.concat(partes, ignore_index=True)


def executar(cfg: Config = DEFAULT_CONFIG, verbose: bool = True) -> dict[str, Path]:
    """Roda o shift-share da RAIS e grava um CSV por referência geográfica."""
    partes: list[pd.DataFrame] = []
    municipios_t1 = formatar_dados_rais(
        cfg.arquivo_rais(cfg.ano_t1_rais, "municipiosPI"), cfg.linhas_rais
    )
    regioes_t1 = formatar_dados_rais(cfg.arquivo_rais(cfg.ano_t1_rais, "regioes"), cfg.linhas_rais)
    conferir_ano(cfg.arquivo_rais(cfg.ano_t1_rais, "municipiosPI"), cfg.ano_t1_rais)

    for ano_t0 in cfg.anos_t0_rais:
        caminho_municipios = cfg.arquivo_rais(ano_t0, "municipiosPI")
        caminho_regioes = cfg.arquivo_rais(ano_t0, "regioes")
        conferir_ano(caminho_municipios, ano_t0)
        conferir_ano(caminho_regioes, ano_t0)

        partes.append(
            shift_share_de_um_ano(
                ano_t0=ano_t0,
                ano_t1=cfg.ano_t1_rais,
                municipios_t0=formatar_dados_rais(caminho_municipios, cfg.linhas_rais),
                municipios_t1=municipios_t1,
                regioes_t0=formatar_dados_rais(caminho_regioes, cfg.linhas_rais),
                regioes_t1=regioes_t1,
                verbose=verbose,
            )
        )

    consolidado = pd.concat(partes, ignore_index=True)
    return gravar_por_referencia(consolidado, cfg)


def gravar_por_referencia(
    consolidado: pd.DataFrame, cfg: Config = DEFAULT_CONFIG
) -> dict[str, Path]:
    """Grava um arquivo por referência geográfica, como o script em R fazia."""
    from shift_share_piaui.r_compat import escrever_csv_r

    escritos: dict[str, Path] = {}
    for referencia in REGIOES:
        recorte = consolidado[consolidado["REFERENCIA_GEOGRAFICA"] == referencia]
        if recorte.empty:
            continue
        escritos[referencia] = escrever_csv_r(recorte, cfg.consolidado_rais(referencia))
    return escritos
