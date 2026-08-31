"""Leitura dos extratos brutos da RAIS (BGCAGED) e do SIDRA (IBGE).

Porte direto de ``formatar_dados_rais()`` e ``formatar_dados_sidra()`` dos
scripts em R, com duas diferenças deliberadas:

* os rótulos passam pelo :func:`shift_share_piaui.r_compat.make_names`, para
  que o resto do pipeline veja exatamente os mesmos nomes que via antes;
* valores que não são inteiros levantam erro em vez de virar ``NA`` silencioso.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd

from shift_share_piaui.r_compat import make_names

# No SIDRA, "-" é zero (não houve produção) e "..." é dado não disponível.
# Os scripts em R tratavam os dois como zero; mantemos a mesma convenção.
AUSENTES_SIDRA: tuple[str, ...] = ("-", "...", "..", "X", "")

COLUNA_MUNICIPIO_SIDRA = "Município"
COLUNA_MUNICIPIO_RAIS = "Municipio"
COLUNA_SUBCLASSE_RAIS = "CNAE.2.0.Subclasse"

_RODAPE_ANO = re.compile(r"^\s*Ano\s*;\s*igual a\s*;\s*(\d{4})", re.IGNORECASE)


class ErroDeLeitura(ValueError):
    """Arquivo de entrada fora do formato esperado."""


def _para_inteiro(df: pd.DataFrame, coluna_chave: str, origem: Path) -> pd.DataFrame:
    """Converte todas as colunas de estoque para inteiro, com erro explícito."""
    convertido = df.copy()
    for coluna in convertido.columns:
        if coluna == coluna_chave:
            continue
        numerico = pd.to_numeric(convertido[coluna], errors="coerce")
        invalidos = numerico.isna() & convertido[coluna].notna()
        if invalidos.any():
            exemplos = convertido.loc[invalidos, coluna].unique()[:3].tolist()
            raise ErroDeLeitura(
                f"Valores não numéricos na coluna {coluna!r} de {origem.name}: {exemplos}"
            )
        convertido[coluna] = numerico.fillna(0).astype("int64")
    return convertido


def formatar_dados_sidra(caminho: Path | str) -> pd.DataFrame:
    """Lê um extrato do SIDRA no formato ``municípios x produtos``.

    A primeira coluna é ``Município`` (inclui Brasil, grandes regiões e Piauí
    além dos municípios); as demais são os produtos, já com os nomes na forma
    que o R produzia.
    """
    caminho = Path(caminho)
    bruto = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig")
    bruto.columns = make_names(bruto.columns)

    if bruto.columns[0] != COLUNA_MUNICIPIO_SIDRA:
        raise ErroDeLeitura(
            f"{caminho.name}: esperava a coluna {COLUNA_MUNICIPIO_SIDRA!r}, "
            f"encontrei {bruto.columns[0]!r}"
        )

    estoques = bruto.columns.drop(COLUNA_MUNICIPIO_SIDRA)
    bruto[estoques] = bruto[estoques].apply(
        lambda coluna: coluna.astype("string").str.strip().replace(list(AUSENTES_SIDRA), "0")
    )
    bruto[COLUNA_MUNICIPIO_SIDRA] = bruto[COLUNA_MUNICIPIO_SIDRA].astype("string").str.strip()
    return _para_inteiro(bruto, COLUNA_MUNICIPIO_SIDRA, caminho)


def formatar_dados_rais(caminho: Path | str, linhas: int = 1363) -> pd.DataFrame:
    """Lê um extrato da RAIS/BGCAGED e o transpõe para ``unidades x subclasses``.

    O arquivo vem com as subclasses da CNAE 2.0 nas linhas e as unidades
    geográficas nas colunas; ``linhas`` é a quantidade de subclasses (o que
    vem depois é o rodapé com as seleções da consulta).
    """
    caminho = Path(caminho)
    bruto = pd.read_csv(
        caminho,
        sep=";",
        skiprows=1,
        nrows=linhas,
        encoding="latin-1",
        dtype=str,
    )
    bruto.columns = make_names(bruto.columns)

    if bruto.columns[0] != COLUNA_SUBCLASSE_RAIS:
        raise ErroDeLeitura(
            f"{caminho.name}: esperava a coluna {COLUNA_SUBCLASSE_RAIS!r}, "
            f"encontrei {bruto.columns[0]!r}"
        )
    if len(bruto) != linhas:
        raise ErroDeLeitura(
            f"{caminho.name}: esperava {linhas} subclasses, encontrei {len(bruto)}"
        )

    subclasses = bruto[COLUNA_SUBCLASSE_RAIS].astype("string").str.strip().tolist()
    estoques = bruto.drop(columns=[COLUNA_SUBCLASSE_RAIS])

    transposto = estoques.T
    transposto.columns = subclasses
    transposto.insert(0, COLUNA_MUNICIPIO_RAIS, transposto.index.astype("string"))
    transposto = transposto.reset_index(drop=True)
    return _para_inteiro(transposto, COLUNA_MUNICIPIO_RAIS, caminho)


def ano_declarado(caminho: Path | str) -> int | None:
    """Ano informado no rodapé "Seleções vigentes" de um extrato da RAIS.

    Devolve ``None`` quando o rodapé não traz a linha do ano.
    """
    caminho = Path(caminho)
    with caminho.open(encoding="latin-1") as arquivo:
        for linha in arquivo:
            achado = _RODAPE_ANO.match(linha)
            if achado:
                return int(achado.group(1))
    return None


def conferir_ano(caminho: Path | str, ano_esperado: int) -> bool:
    """Avisa quando o ano do rodapé não bate com o ano do nome do arquivo.

    Existe porque o repositório traz um caso real assim: o extrato
    ``vinculos_2023_ClasseCNAE_regioes.csv`` declara 2022 no rodapé.
    """
    declarado = ano_declarado(caminho)
    if declarado is None or declarado == ano_esperado:
        return True
    warnings.warn(
        f"{Path(caminho).name} declara o ano {declarado} no rodapé, "
        f"mas está sendo usado como {ano_esperado}.",
        stacklevel=2,
    )
    return False
