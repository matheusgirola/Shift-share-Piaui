"""Fixtures compartilhadas: um projeto de brinquedo, completo e minúsculo.

Os testes não dependem dos dados reais do repositório. Eles montam, num
diretório temporário, extratos com o mesmo formato dos originais (mesmo
separador, mesma codificação, mesmos rodapés) e rodam o pipeline inteiro em
cima deles -- o que permite conferir números calculados à mão.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from shift_share_piaui.config import FONTES_SIDRA, Config, Rodada

REBANHOS = tuple(f for f in FONTES_SIDRA if f.prefixo == "PPM_Efetivo_rebanhos")

# --- projeto de brinquedo --------------------------------------------------
# Dois municípios, duas subclasses na RAIS e dois produtos no SIDRA.
MUNICIPIOS = ["PI-ACAUA", "PI-BOM JESUS"]
SUBCLASSES_RAIS = ["Extração de carvão mineral", "Fabricação de biscoitos"]
PRODUTOS_SIDRA = ["Bovino", "Suíno - total"]

# Códigos da CNAE 2.0 correspondentes às subclasses acima (faixa da mineração
# e faixa da indústria).
DICIONARIO_CNAE = pd.DataFrame(
    {
        "Código": [510000, 1092900],
        "Descrição": ["Extração de carvão mineral", "Fabricação de biscoitos"],
    }
)

# Estoques da RAIS por ano: {ano: {unidade: [subclasse1, subclasse2]}}
RAIS_MUNICIPIOS = {
    2013: {"PI-ACAUA": [10, 5], "PI-BOM JESUS": [4, 20]},
    2020: {"PI-ACAUA": [30, 5], "PI-BOM JESUS": [2, 60]},
}
RAIS_REGIOES = {
    2013: {
        "Norte": [100, 100],
        "Nordeste": [200, 400],
        "Sudeste": [300, 300],
        "Sul": [100, 100],
        "Centro-Oeste": [100, 100],
    },
    2020: {
        "Norte": [110, 150],
        "Nordeste": [260, 700],
        "Sudeste": [330, 450],
        "Sul": [110, 150],
        "Centro-Oeste": [110, 150],
    },
}

# Estoques do SIDRA por ano: linhas de agregado + municípios.
SIDRA = {
    2013: {
        "Brasil": [1000, 800],
        "Nordeste": [400, 300],
        "Piauí": [100, 60],
        "Acauã (PI)": [40, 10],
        "Bom Jesus (PI)": [60, 50],
    },
    2021: {
        "Brasil": [1500, 900],
        "Nordeste": [700, 330],
        "Piauí": [200, 66],
        "Acauã (PI)": [120, 6],
        "Bom Jesus (PI)": [80, 60],
    },
}


# Assinatura de _escrever_rais, devolvida pela fixture escrever_extrato_rais.
EscritorDeExtratoRais = Callable[[Path, list[str], dict[str, list[int]], int], None]


def _escrever_rais(
    caminho: Path, colunas: list[str], estoques: dict[str, list[int]], ano: int
) -> None:
    """Reproduz o layout do extrato do BGCAGED, rodapé incluído."""
    linhas = ["Coluna;Unidade", "CNAE 2.0 Subclasse;" + ";".join(colunas)]
    for posicao, subclasse in enumerate(SUBCLASSES_RAIS):
        valores = [str(estoques[coluna][posicao]) for coluna in colunas]
        linhas.append(f"{subclasse};" + ";".join(valores))
    linhas += ["", "Seleções vigentes", "Variável;Critério;Valor", f"Ano;igual a;{ano}"]
    caminho.write_text("\n".join(linhas) + "\n", encoding="latin-1")


def _escrever_sidra(caminho: Path, estoques: dict[str, list[int]]) -> None:
    """Reproduz o layout do extrato do SIDRA, com BOM, aspas e ausentes."""
    cabecalho = ";".join(f'"{nome}"' for nome in ["Município", *PRODUTOS_SIDRA])
    linhas = [cabecalho]
    for unidade, valores in estoques.items():
        celulas = [f'"{unidade}"'] + ['"-"' if valor == 0 else f'"{valor}"' for valor in valores]
        linhas.append(";".join(celulas))
    caminho.write_text("﻿" + "\n".join(linhas) + "\n", encoding="utf-8")


@pytest.fixture
def projeto(tmp_path: Path) -> Config:
    """Um projeto completo em disco, pronto para rodar o pipeline."""
    dados = tmp_path / "Dados"
    tabelas = tmp_path / "Tabelas-Correlacao"
    dados.mkdir()
    tabelas.mkdir()

    for ano, estoques in RAIS_MUNICIPIOS.items():
        _escrever_rais(
            dados / f"vinculos_{ano}_ClasseCNAE_municipiosPI.csv",
            MUNICIPIOS,
            estoques,
            ano,
        )
    for ano, estoques in RAIS_REGIOES.items():
        _escrever_rais(
            dados / f"vinculos_{ano}_ClasseCNAE_regioes.csv",
            list(estoques),
            estoques,
            ano,
        )
    for ano, estoques in SIDRA.items():
        _escrever_sidra(dados / f"PPM_Efetivo_rebanhos_{ano}_municipiosPI.csv", estoques)

    pd.DataFrame(
        {
            "CD_MUN": [2200053, 2201638],
            "NM_MUN": ["Acauã", "Bom Jesus"],
            "NM_MUN_RAIS": MUNICIPIOS,
            "CD_MUN_6DIG": [220005, 220163],
        }
    ).to_excel(tabelas / "cidades-RAIS-IBGE.xlsx", index=False)

    pd.DataFrame(
        {
            "CD_MUN": [2200053, 2201638],
            "NM_MUN": ["Acauã", "Bom Jesus"],
            "pi_micro_m": ["Chapada Vale do Itaim", "Serra da Capivara"],
            "CD_MUN_6DIG": [220005, 220163],
        }
    ).to_excel(tabelas / "territorios_desenvolvimento.xlsx", index=False)

    DICIONARIO_CNAE.to_csv(tabelas / "dicionario_cnae_subclasse.csv", index=False, encoding="utf-8")

    (tmp_path / "shift-share.toml").write_text(
        "\n".join(
            [
                "[anos]",
                "ano_t1_rais = 2020",
                "ano_t1_sidra = 2021",
                "",
                "[[rodadas]]",
                "rotulo = 2013",
                "ano_t0_rais = 2013",
                "ano_t0_sidra = 2013",
                "",
                "[dados]",
                f"linhas_rais = {len(SUBCLASSES_RAIS)}",
                'fontes_sidra = ["PPM_Efetivo_rebanhos"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    return Config(
        raiz=tmp_path,
        ano_t1_rais=2020,
        ano_t1_sidra=2021,
        rodadas=(Rodada(rotulo=2013, ano_t0_rais=2013, ano_t0_sidra=2013),),
        linhas_rais=len(SUBCLASSES_RAIS),
        fontes_sidra=REBANHOS,
    )


@pytest.fixture
def escrever_extrato_rais() -> EscritorDeExtratoRais:
    """Permite a um teste reescrever um extrato da RAIS do projeto."""
    return _escrever_rais


@pytest.fixture
def projeto_processado(projeto: Config) -> Config:
    """O projeto de brinquedo com as duas etapas de shift-share já rodadas."""
    from shift_share_piaui import pipeline_rais, pipeline_sidra

    pipeline_rais.executar(projeto, verbose=False)
    pipeline_sidra.executar(projeto, verbose=False)
    return projeto
