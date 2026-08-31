"""Categorização das potencialidades e os recortes derivados."""

from __future__ import annotations

import pandas as pd
import pytest
from pandas.errors import MergeError

from shift_share_piaui import potencialidades, tratamento
from shift_share_piaui.config import Config
from shift_share_piaui.potencialidades import (
    SEM_CATEGORIA,
    binarizar_potencialidades,
    categorizar,
    classificar_agropecuaria,
    classificar_rais,
    contar_potencialidades,
    descrever_por_territorio,
    empilhar_rodadas,
    subclasses_por_potencialidade,
)


# --- classificação dos produtos do IBGE -------------------------------------
@pytest.mark.parametrize(
    ("produto", "esperado"),
    [
        ("Caprino", "Ovinocaprinocultura"),
        ("Bovino", "Bovinocultura"),
        ("Leite", "Bovinocultura"),
        ("Mel de abelha", "Apicultura e Meliponicultura"),
        ("Suíno total", "Suinocultura"),
        ("Tilápia", "Pesca, Piscicultura e Aquicultura"),
        ("Soja em grão", "Agronegócio"),
        ("Carnaúba pó", "Extrativismo"),
        ("Melancia", "Hortifruticultura"),
        ("Equino", "Equinocultura"),
    ],
)
def test_produto_do_ibge_vai_para_a_potencialidade_certa(produto: str, esperado: str):
    assert classificar_agropecuaria(produto) == esperado


def test_ovino_fica_na_ovinocaprinocultura():
    # "Ovino" está listado em dois grupos; a primeira ocorrência é a que vale,
    # como no encadeamento de ifs do notebook.
    assert classificar_agropecuaria("Ovino") == "Ovinocaprinocultura"


def test_produto_desconhecido_fica_sem_categoria():
    assert classificar_agropecuaria("Kiwi") == SEM_CATEGORIA


# --- classificação da RAIS --------------------------------------------------
@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        (510000, "Mineração"),
        (1092900, "Indústria"),
        (4120400, "Construção"),
        (4929902, "Transporte, armazenagem e correio"),
        (5510801, "Alojamento e alimentação"),
        (6201501, "Informação e comunicação"),
        (6920601, "Atividades profissionais, científicas e técnicas"),
        (8513900, "Polo de educação"),
        (8630503, "Polo de saúde"),
        (9001901, "Artes, cultura, esporte e recreação"),
        (9602501, "Outras atividades de serviço"),
    ],
)
def test_faixa_do_codigo_da_cnae_define_a_potencialidade(codigo: int, esperado: str):
    assert classificar_rais("qualquer subclasse", codigo) == esperado


def test_artesanato_e_reconhecido_pelo_nome():
    # Atravessa várias divisões da CNAE, então não sai da faixa numérica.
    assert classificar_rais("Artesanato em madeira", 1610203) == "Artesanato"


def test_subclasse_sem_codigo_fica_sem_potencialidade():
    assert classificar_rais("Subclasse órfã", None) is None
    assert classificar_rais("Subclasse órfã", float("nan")) is None


def test_codigo_fora_de_todas_as_faixas_fica_sem_potencialidade():
    assert classificar_rais("Comércio varejista", 4711301) is None


# --- empilhamento e categorização -------------------------------------------
def test_empilhar_mantem_a_primeira_rodada_em_que_o_setor_aparece(
    projeto_processado: Config,
):
    from shift_share_piaui.config import Rodada

    cfg = projeto_processado.com(
        rodadas=(
            projeto_processado.rodadas[0],
            Rodada(rotulo=2016, ano_t0_rais=2013, ano_t0_sidra=2013),
        )
    )
    tratamento.executar(cfg, verbose=False)

    empilhado = empilhar_rodadas(cfg, "T1")
    # As duas rodadas leem os mesmos anos, então todo par (setor, município)
    # aparece duas vezes e precisa sobrar só a primeira, de 2013.
    assert not empilhado.duplicated(subset=["subclasse", "NM_MUN"]).any()
    assert empilhado["ANO"].unique().tolist() == [2013]


def test_categorizar_separa_rais_de_ibge():
    empilhado = pd.DataFrame(
        {
            "subclasse": ["Fabricação de biscoitos", "Bovino"],
            "NM_MUN": ["Acauã", "Acauã"],
            "Fonte": ["RAIS", "PPM"],
            "Estoque_mun_t1": [10, 20],
            "Unidade de medida": ["pessoas", "cabeças"],
            "classificacao_regiao": ["T1", "T1"],
            "ANO": [2013, 2013],
        }
    )
    dicionario = pd.DataFrame({"subclasse": ["Fabricação de biscoitos"], "Código": [1092900]})

    categorizado = categorizar(empilhado, dicionario)
    por_setor = dict(zip(categorizado["subclasse"], categorizado["Potencialidade"], strict=True))
    assert por_setor == {"Fabricação de biscoitos": "Indústria", "Bovino": "Bovinocultura"}
    assert "Código" not in categorizado.columns


def test_categorizar_nao_multiplica_linhas_com_dicionario_repetido():
    # Descrições repetidas no dicionário multiplicavam as linhas da RAIS na
    # versão original; a junção agora é validada como muitos-para-um.
    empilhado = pd.DataFrame(
        {
            "subclasse": ["Geração de energia elétrica"],
            "NM_MUN": ["Parnaíba"],
            "Fonte": ["RAIS"],
            "Estoque_mun_t1": [3],
            "Unidade de medida": ["pessoas"],
            "classificacao_regiao": ["T1"],
            "ANO": [2013],
        }
    )
    dicionario = pd.DataFrame(
        {
            "subclasse": ["Geração de energia elétrica", "Geração de energia elétrica"],
            "Código": [3511500, 3511501],
        }
    )
    # A validação m:1 do merge é o que barra o dicionário repetido; esperar
    # MergeError garante que o teste falhe se ela for removida, em vez de
    # passar por qualquer outra exceção.
    with pytest.raises(MergeError):
        categorizar(empilhado, dicionario)


# --- recortes derivados -----------------------------------------------------
def _categorizado_falso() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "subclasse": ["Bovino", "Leite", "Fabricação de biscoitos"],
            "NM_MUN": ["Acauã", "Acauã", "Bom Jesus"],
            "Estoque_mun_t1": [100, 7, 12],
            "Fonte": ["PPM", "PPM", "RAIS"],
            "Unidade de medida": ["cabeças", "mil reais", "pessoas"],
            "ANO": [2013, 2013, 2013],
            "Potencialidade": ["Bovinocultura", "Bovinocultura", "Indústria"],
        }
    )


def test_contagem_conta_setores_por_municipio():
    contagem = contar_potencialidades(_categorizado_falso())
    linha = contagem.set_index("NM_MUN")

    assert linha.loc["Acauã", "Bovinocultura"] == 2
    assert linha.loc["Acauã", "Indústria"] == 0
    assert linha.loc["Bom Jesus", "Indústria"] == 1


def test_binario_zera_municipio_sem_potencialidade():
    cods = pd.DataFrame({"NM_MUN": ["Acauã", "Bom Jesus", "Teresina"], "CD_MUN": [1, 2, 3]})
    binario = binarizar_potencialidades(contar_potencialidades(_categorizado_falso()), cods)
    linha = binario.set_index("NM_MUN")

    assert linha.loc["Acauã", "Bovinocultura"] == 1  # 2 setores viram 1
    assert linha.loc["Bom Jesus", "Bovinocultura"] == 0
    # Município sem nenhum setor entra zerado, não vazio.
    # pyrefly: ignore[not-callable]  # stub do pandas: .loc devolve Series | DataFrame
    assert linha.loc["Teresina"].drop("CD_MUN").tolist() == [0, 0]
    assert linha["CD_MUN"].tolist() == [1, 2, 3]


def test_subclasses_convertem_mil_reais_linha_a_linha():
    # A bovinocultura mistura cabeças (Bovino) e mil reais (Leite); a conversão
    # tem de olhar a unidade de cada linha.
    com_valor, binario = subclasses_por_potencialidade(_categorizado_falso())["Bovinocultura"]
    assert com_valor.loc["Acauã", "Bovino"] == 100
    assert com_valor.loc["Acauã", "Leite"] == 7000
    # pyrefly: ignore[not-callable]  # stub do pandas: .loc devolve Series | DataFrame
    assert binario.loc["Acauã"].tolist() == [1, 1]


def test_descricao_lista_os_maiores_setores_de_cada_territorio():
    territorios = pd.DataFrame(
        {
            "NM_MUN": ["Acauã", "Bom Jesus"],
            "pi_micro_m": ["Chapada Vale do Itaim", "Serra da Capivara"],
        }
    )
    texto = descrever_por_territorio(_categorizado_falso(), territorios, quantidade=1)

    assert "### Chapada Vale do Itaim" in texto
    assert "Bovinocultura - Bovino" in texto  # 100 > 7
    assert "Indústria - Fabricação de biscoitos" in texto


# --- etapa completa ---------------------------------------------------------
def test_etapa_completa_grava_todos_os_recortes(projeto_processado: Config):
    tratamento.executar(projeto_processado, verbose=False)
    escritos = potencialidades.executar(projeto_processado, tipos=("T1", "T2"), verbose=False)

    assert set(escritos) == {
        "categorizado_T1",
        "categorizado_T2",
        "com_numeros",
        "binario",
        "descricao",
        "subclasses_dummy",
    }
    for caminho in escritos.values():
        assert caminho.exists()

    categorizado = pd.read_excel(escritos["categorizado_T1"])
    assert categorizado["classificacao_regiao"].unique().tolist() == ["T1"]
    assert "Potencialidade" in categorizado.columns


def test_binario_cobre_todos_os_municipios_do_estado(projeto_processado: Config):
    tratamento.executar(projeto_processado, verbose=False)
    escritos = potencialidades.executar(projeto_processado, tipos=("T1",), verbose=False)

    binario = pd.read_excel(escritos["binario"])
    assert set(binario["NM_MUN"]) == {"Acauã", "Bom Jesus"}
    assert binario.notna().all().all()
