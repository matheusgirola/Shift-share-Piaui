"""Leitura dos extratos brutos: formato, ausentes e conferência de ano."""

from __future__ import annotations

import pytest

from shift_share_piaui.config import Config
from shift_share_piaui.leitura import (
    ErroDeLeitura,
    ano_declarado,
    conferir_ano,
    formatar_dados_rais,
    formatar_dados_sidra,
)


def test_rais_e_transposta_para_unidades_por_subclasse(projeto: Config):
    dados = formatar_dados_rais(projeto.arquivo_rais(2013, "municipiosPI"), linhas=2)

    assert dados["Municipio"].tolist() == ["PI.ACAUA", "PI.BOM.JESUS"]
    assert list(dados.columns) == [
        "Municipio",
        "Extração de carvão mineral",
        "Fabricação de biscoitos",
    ]
    # Acauã: 10 na mineração, 5 na indústria.
    assert dados.loc[0, "Extração de carvão mineral"] == 10
    assert dados.loc[0, "Fabricação de biscoitos"] == 5


def test_rais_recusa_arquivo_com_menos_linhas_que_o_esperado(projeto: Config):
    with pytest.raises(ErroDeLeitura, match="esperava 99 subclasses"):
        formatar_dados_rais(projeto.arquivo_rais(2013, "municipiosPI"), linhas=99)


def test_sidra_traz_agregados_e_municipios_na_mesma_coluna(projeto: Config):
    dados = formatar_dados_sidra(
        projeto.dados / "PPM_Efetivo_rebanhos_2013_municipiosPI.csv"
    )

    assert dados["Município"].tolist() == [
        "Brasil",
        "Nordeste",
        "Piauí",
        "Acauã (PI)",
        "Bom Jesus (PI)",
    ]
    # O nome do produto passa pelo make.names(), como no R.
    assert list(dados.columns) == ["Município", "Bovino", "Suíno...total"]


def test_sidra_converte_ausentes_para_zero(projeto: Config, tmp_path):
    caminho = tmp_path / "PPM_teste.csv"
    caminho.write_text(
        '﻿"Município";"Bovino"\n"Brasil";"-"\n"Acauã (PI)";"..."\n',
        encoding="utf-8",
    )
    dados = formatar_dados_sidra(caminho)
    assert dados["Bovino"].tolist() == [0, 0]
    assert dados["Bovino"].dtype == "int64"


def test_sidra_recusa_valor_que_nao_e_numero(tmp_path):
    caminho = tmp_path / "PPM_quebrado.csv"
    caminho.write_text(
        '﻿"Município";"Bovino"\n"Brasil";"mil e duzentos"\n', encoding="utf-8"
    )
    with pytest.raises(ErroDeLeitura, match="não numéricos"):
        formatar_dados_sidra(caminho)


def test_ano_declarado_vem_do_rodape(projeto: Config):
    assert ano_declarado(projeto.arquivo_rais(2013, "municipiosPI")) == 2013


def test_conferir_ano_avisa_quando_o_rodape_diverge_do_nome(projeto: Config):
    caminho = projeto.arquivo_rais(2013, "municipiosPI")
    assert conferir_ano(caminho, 2013) is True
    with pytest.warns(UserWarning, match="declara o ano 2013"):
        assert conferir_ano(caminho, 2020) is False
