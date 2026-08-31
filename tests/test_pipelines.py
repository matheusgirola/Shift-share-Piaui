"""As duas etapas de shift-share, de ponta a ponta no projeto de brinquedo."""

from __future__ import annotations

import warnings

import pandas as pd
import pytest
from conftest import EscritorDeExtratoRais

from shift_share_piaui import pipeline_rais, pipeline_sidra
from shift_share_piaui.config import FONTES_SIDRA, Config
from shift_share_piaui.leitura import ErroDeLeitura, formatar_dados_rais
from shift_share_piaui.r_compat import ler_csv_r

REBANHOS = tuple(f for f in FONTES_SIDRA if f.prefixo == "PPM_Efetivo_rebanhos")


# --- referência de comparação ----------------------------------------------
def test_referencia_piaui_e_a_soma_dos_municipios(projeto: Config):
    municipios = formatar_dados_rais(projeto.arquivo_rais(2013, "municipiosPI"), 2)
    regioes = formatar_dados_rais(projeto.arquivo_rais(2013, "regioes"), 2)

    # Acauã (10, 5) + Bom Jesus (4, 20).
    assert pipeline_rais.estoque_de_referencia("Piauí", municipios, regioes).tolist() == [14, 25]


def test_referencia_brasil_soma_as_grandes_regioes_sem_avisar(projeto: Config):
    municipios = formatar_dados_rais(projeto.arquivo_rais(2013, "municipiosPI"), 2)
    regioes = formatar_dados_rais(projeto.arquivo_rais(2013, "regioes"), 2)

    with warnings.catch_warnings():
        # O extrato traz as cinco grandes regiões: somá-las é o total nacional,
        # e nesse caso a soma não deve gerar aviso nenhum.
        warnings.simplefilter("error")
        brasil = pipeline_rais.estoque_de_referencia("Brasil", municipios, regioes)
    # 100+200+300+100+100 e 100+400+300+100+100.
    assert brasil.tolist() == [800, 1000]


def test_referencia_brasil_prefere_a_linha_brasil_quando_ela_existe():
    regioes = pd.DataFrame(
        {
            "Municipio": ["Nordeste", "Brasil"],
            "setor": [10, 999],
        }
    )
    assert pipeline_rais.estoque_nacional(regioes).tolist() == [999]


def test_referencia_ausente_e_erro():
    regioes = pd.DataFrame({"Municipio": ["Norte"], "setor": [1]})
    municipios = pd.DataFrame({"Municipio": ["PI.ACAUA"], "setor": [1]})
    with pytest.raises(ErroDeLeitura, match="Nordeste"):
        pipeline_rais.estoque_de_referencia("Nordeste", municipios, regioes)


# --- pipeline da RAIS -------------------------------------------------------
def test_rais_grava_um_arquivo_por_referencia(projeto: Config):
    escritos = pipeline_rais.executar(projeto, verbose=False)

    assert set(escritos) == {"Piauí", "Nordeste", "Brasil"}
    for referencia, caminho in escritos.items():
        base = ler_csv_r(caminho)
        assert base["REFERENCIA_GEOGRAFICA"].unique().tolist() == [referencia]


def test_rais_cobre_todos_os_municipios_e_subclasses(projeto: Config):
    pipeline_rais.executar(projeto, verbose=False)
    base = ler_csv_r(projeto.consolidado_rais("Brasil"))

    # 2 municípios x 2 subclasses x 1 rodada.
    assert len(base) == 4
    assert set(base["NM_MUN_RAIS"]) == {"PI.ACAUA", "PI.BOM.JESUS"}
    assert base["ANO_T0"].unique().tolist() == [2013]
    assert base["ANO_T1"].unique().tolist() == [2020]


def test_rais_calcula_o_shift_share_do_municipio_contra_o_brasil(projeto: Config):
    pipeline_rais.executar(projeto, verbose=False)
    base = ler_csv_r(projeto.consolidado_rais("Brasil"))

    linha = base[
        (base["NM_MUN_RAIS"] == "PI.ACAUA") & (base["subclasse"] == "Extração de carvão mineral")
    ].iloc[0]

    # Brasil (soma das grandes regiões): 1800 -> 2520, logo G = 0,40.
    # Setor no Brasil: 800 -> 920 (Gi = 0,15).
    # Acauã: 15 -> 35 (g = 1,3333...); setor em Acauã: 10 -> 30 (gi = 2).
    assert linha["NE"] == pytest.approx((2520 - 1800) / 1800 * 10)
    assert linha["CE"] == pytest.approx((2 - 0.15) * 10)
    assert linha["RSE"] == pytest.approx((4 / 3 - 0.4) * 10)
    assert linha["Estoque_nac_t0"] == 800
    assert linha["Estoque_mun_t1"] == 30
    assert linha["classificacao_regiao"] == "T1"


def test_rais_pula_municipio_sem_nenhum_vinculo(
    projeto: Config, escrever_extrato_rais: EscritorDeExtratoRais
):
    # Um terceiro município totalmente zerado nos dois anos.
    colunas = ["PI-ACAUA", "PI-BOM JESUS", "PI-VAZIO"]
    por_ano = {
        2013: {"PI-ACAUA": [10, 5], "PI-BOM JESUS": [4, 20], "PI-VAZIO": [0, 0]},
        2020: {"PI-ACAUA": [30, 5], "PI-BOM JESUS": [2, 60], "PI-VAZIO": [0, 0]},
    }
    for ano, estoques in por_ano.items():
        escrever_extrato_rais(projeto.arquivo_rais(ano, "municipiosPI"), colunas, estoques, ano)

    pipeline_rais.executar(projeto, verbose=False)
    base = ler_csv_r(projeto.consolidado_rais("Brasil"))
    assert "PI.VAZIO" not in set(base["NM_MUN_RAIS"])


# --- pipeline do SIDRA ------------------------------------------------------
def test_sidra_grava_um_arquivo_por_pesquisa(projeto: Config):
    escritos = pipeline_sidra.executar(projeto, fontes=REBANHOS, verbose=False)
    caminho = escritos["PPM_Efetivo_rebanhos"]

    assert caminho.name == "shift-share-consolidado_ppm_efetivo_rebanhos.csv"
    base = ler_csv_r(caminho)
    # 5 linhas (3 agregados + 2 municípios) x 2 produtos x 3 referências.
    assert len(base) == 30
    assert set(base["REFERENCIA_GEOGRAFICA"]) == {"Piauí", "Nordeste", "Brasil"}


def test_sidra_usa_a_propria_linha_do_extrato_como_referencia(projeto: Config):
    pipeline_sidra.executar(projeto, fontes=REBANHOS, verbose=False)
    base = ler_csv_r(projeto.consolidado_sidra(REBANHOS[0]))

    linha = base[
        (base["NM_MUN_RAIS"] == "Acauã (PI)")
        & (base["subclasse"] == "Bovino")
        & (base["REFERENCIA_GEOGRAFICA"] == "Brasil")
    ].iloc[0]

    assert linha["Estoque_nac_t0"] == 1000  # linha "Brasil" do extrato
    assert linha["Estoque_nac_t1"] == 1500
    assert linha["Estoque_mun_t0"] == 40
    assert linha["Estoque_mun_t1"] == 120


def test_sidra_recusa_anos_com_produtos_diferentes(projeto: Config):
    caminho = projeto.dados / "PPM_Efetivo_rebanhos_2021_municipiosPI.csv"
    caminho.write_text('﻿"Município";"Bovino"\n"Brasil";"10"\n', encoding="utf-8")
    with pytest.raises(ErroDeLeitura, match="não coincidem"):
        pipeline_sidra.executar(projeto, fontes=REBANHOS, verbose=False)
