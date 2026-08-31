"""Linha de comando do pipeline.

    uv run ssp-shift-share tudo            # roda as quatro etapas em ordem
    uv run ssp-shift-share rais            # só o shift-share da RAIS
    uv run ssp-shift-share sidra           # só o das pesquisas do IBGE
    uv run ssp-shift-share tratamento      # consolida por tipo de região
    uv run ssp-shift-share potencialidades --tipos T1 T2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shift_share_piaui.config import ARQUIVO_DE_CONFIGURACAO, TIPOS, Config


def _config(argumentos: argparse.Namespace) -> Config:
    return Config.de_arquivo(argumentos.raiz)


def _rais(argumentos: argparse.Namespace) -> None:
    from shift_share_piaui import pipeline_rais

    for referencia, caminho in pipeline_rais.executar(
        _config(argumentos), verbose=not argumentos.silencioso
    ).items():
        print(f"{referencia}: {caminho}")


def _sidra(argumentos: argparse.Namespace) -> None:
    from shift_share_piaui import pipeline_sidra

    for fonte, caminho in pipeline_sidra.executar(
        _config(argumentos), verbose=not argumentos.silencioso
    ).items():
        print(f"{fonte}: {caminho}")


def _tratamento(argumentos: argparse.Namespace) -> None:
    from shift_share_piaui import tratamento

    for rotulo, caminho in tratamento.executar(
        _config(argumentos), verbose=not argumentos.silencioso
    ).items():
        print(f"{rotulo}: {caminho}")


def _potencialidades(argumentos: argparse.Namespace) -> None:
    from shift_share_piaui import potencialidades

    for nome, caminho in potencialidades.executar(
        _config(argumentos),
        tipos=tuple(argumentos.tipos),
        verbose=not argumentos.silencioso,
    ).items():
        print(f"{nome}: {caminho}")


def _tudo(argumentos: argparse.Namespace) -> None:
    _sidra(argumentos)
    _rais(argumentos)
    _tratamento(argumentos)
    _potencialidades(argumentos)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ssp-shift-share",
        description="Pipeline de shift-share e potencialidades produtivas do Piauí.",
    )
    parser.add_argument(
        "--raiz",
        default=None,
        help=(
            "Raiz do projeto (padrão: a do repositório em que o pacote está "
            f"instalado). Os parâmetros saem de {ARQUIVO_DE_CONFIGURACAO}, se existir."
        ),
    )
    parser.add_argument(
        "--silencioso",
        action="store_true",
        help="Não imprime o andamento de cada etapa.",
    )

    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("rais", help="Shift-share dos vínculos da RAIS.").set_defaults(
        funcao=_rais
    )
    comandos.add_parser(
        "sidra", help="Shift-share das pesquisas agropecuárias do IBGE."
    ).set_defaults(funcao=_sidra)
    comandos.add_parser(
        "tratamento", help="Consolida as bases por tipo de região."
    ).set_defaults(funcao=_tratamento)

    potencialidades = comandos.add_parser(
        "potencialidades", help="Categoriza as potencialidades e gera os recortes."
    )
    potencialidades.add_argument(
        "--tipos",
        nargs="+",
        default=["T1", "T2"],
        choices=list(TIPOS),
        help="Tipos de região considerados (padrão: T1 T2, o do mapa físico).",
    )
    potencialidades.set_defaults(funcao=_potencialidades)

    comandos.add_parser("tudo", help="Roda as quatro etapas em ordem.").set_defaults(
        funcao=_tudo, tipos=["T1", "T2"]
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argumentos = construir_parser().parse_args(argv)
    argumentos.funcao(argumentos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
