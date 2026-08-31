"""Compatibilidade com o comportamento do R.

Os rótulos de subclasse que circulam pelo pipeline (e que as listas de
categorização em :mod:`shift_share_piaui.potencialidades` esperam encontrar)
nasceram do ``make.names()`` que o ``read.csv()`` do R aplica aos cabeçalhos.
"Suíno - total" vira ``Suíno...total``, "1.2 - Castanha-de-caju" vira
``X1.2...Castanha.de.caju`` -- e é justamente por isso que o tratamento em
Python removia ``X``, dígitos e pontos depois.

Reproduzir ``make.names()`` aqui é o que permite trocar o R por Python sem
mudar uma linha das listas de categorização.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

# Palavras reservadas do R: make.names() acrescenta um ponto ao final delas.
_RESERVADAS = frozenset(
    """if else repeat while function for next break TRUE FALSE NULL Inf NaN NA
    NA_integer_ NA_real_ NA_character_""".split()
)


def _valido(nome: str) -> str:
    """Aplica a ``make.names()`` de um único nome, sem tratar duplicatas."""
    convertido = "".join(
        caractere if (caractere.isalnum() or caractere in "._") else "."
        for caractere in nome
    )
    if not convertido:
        return "X"
    primeiro = convertido[0]
    precisa_prefixo = (
        primeiro.isdigit()
        or primeiro == "_"
        or (primeiro == "." and len(convertido) > 1 and convertido[1].isdigit())
    )
    if precisa_prefixo:
        convertido = "X" + convertido
    if convertido in _RESERVADAS:
        convertido += "."
    return convertido


def make_names(nomes: Iterable[str], unique: bool = True) -> list[str]:
    """Equivalente a ``make.names(nomes, unique=unique)`` do R.

    Com ``unique=True`` as repetições recebem sufixo ``.1``, ``.2``... a partir
    da segunda ocorrência, como o R faz ao ler um CSV com ``check.names=TRUE``.
    """
    convertidos = [_valido(nome) for nome in nomes]
    if not unique:
        return convertidos

    vistos: dict[str, int] = {}
    resultado: list[str] = []
    for nome in convertidos:
        if nome not in vistos:
            vistos[nome] = 0
            resultado.append(nome)
            continue
        while True:
            vistos[nome] += 1
            candidato = f"{nome}.{vistos[nome]}"
            if candidato not in vistos:
                break
        vistos[candidato] = 0
        resultado.append(candidato)
    return resultado


def escrever_csv_r(df: pd.DataFrame, caminho: Path | str, encoding: str = "latin-1") -> Path:
    """Grava no mesmo formato do ``write.table()`` usado nos scripts em R.

    Ou seja: separador ``;``, vírgula decimal, texto entre aspas, ``NA`` vazio,
    sem coluna de índice e em latin-1 -- exatamente o que o notebook lia de
    volta com ``pd.read_csv(sep=';', decimal=',', encoding='latin1')``.
    """
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        caminho,
        sep=";",
        decimal=",",
        index=False,
        na_rep="",
        encoding=encoding,
        quoting=csv.QUOTE_NONNUMERIC,
        errors="replace",
    )
    return caminho


def ler_csv_r(caminho: Path | str, encoding: str = "latin-1") -> pd.DataFrame:
    """Lê de volta um arquivo gravado por :func:`escrever_csv_r`."""
    return pd.read_csv(caminho, sep=";", decimal=",", encoding=encoding)


def colunas_de_subclasse(df: pd.DataFrame, coluna_chave: str) -> Sequence[str]:
    """Colunas de estoque de um quadro no formato ``chave x subclasses``."""
    return [coluna for coluna in df.columns if coluna != coluna_chave]
