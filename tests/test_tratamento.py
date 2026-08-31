"""Tratamento: padronização de rótulos, recortes e consolidação por tipo."""

from __future__ import annotations

import pandas as pd
import pytest

from shift_share_piaui import tratamento
from shift_share_piaui.config import FONTES_SIDRA, Config
from shift_share_piaui.tratamento import (
    ErroDeTratamento,
    carregar_cods_ibge,
    carregar_dicionario_cnae,
    conferir_classificacao_unica,
    consolidar_por_tipo,
    formatar_texto_producao,
    padronizar_nome_rais,
    remover_uf,
    tratar_base_rais,
    tratar_base_sidra,
)

REBANHOS = next(f for f in FONTES_SIDRA if f.prefixo == "PPM_Efetivo_rebanhos")


# --- padronização de rótulos ------------------------------------------------
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("PI-ACAUA", "PI.ACAUA"),
        ("PI-BARRA D ALCANTARA", "PI.BARRA.D.ALCANTARA"),
        ("PI-SAO JOAO DA FRONTEIRA", "PI.SAO.JOAO.DA.FRONTEIRA"),
    ],
)
def test_nome_da_rais_vira_a_forma_usada_nas_colunas(entrada, esperado):
    assert padronizar_nome_rais(entrada) == esperado


def test_remover_uf_tira_o_sufixo_do_sidra():
    assert remover_uf("Acauã (PI)") == "Acauã"
    assert remover_uf("Brasil") == "Brasil"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        # Rótulos como saem do make.names() do R, e como precisam ficar para
        # bater com as listas de categorização.
        ("Suíno...total", "Suíno total"),
        ("Galináceos...total", "Galináceos total"),
        ("Arroz..em.casca.", "Arroz em casca"),
        ("Coco.da.baía.", "Coco da baía"),
        ("Carnaúba...pó", "Carnaúba pó"),
        ("X1...Alimentícios", "Alimentícios"),
        ("X1.2...Castanha.de.caju", "Castanha de caju"),
        ("Bovino", "Bovino"),
    ],
)
def test_limpeza_do_rotulo_de_producao(entrada, esperado):
    assert formatar_texto_producao(entrada) == esperado


def test_limpeza_nao_deixa_espacos_dobrados_nem_nas_pontas():
    limpo = formatar_texto_producao("X2.1...Lenha..m3.")
    assert limpo == "Lenha m"
    assert "  " not in limpo


# --- tabelas de apoio -------------------------------------------------------
def test_dicionario_da_cnae_e_deduplicado(tmp_path, projeto: Config):
    # Duas subclasses com a mesma descrição capitalizada: sem deduplicar, a
    # junção com a RAIS vira um-para-muitos e replica linhas.
    caminho = projeto.tabelas_correlacao / "dicionario_cnae_subclasse.csv"
    pd.DataFrame(
        {
            "Código": [3511500, 3511501, 1092900],
            "Descrição": [
                "Geração de energia elétrica",
                "GERAÇÃO DE ENERGIA ELÉTRICA",
                "Fabricação de biscoitos",
            ],
        }
    ).to_csv(caminho, index=False)

    dicionario = carregar_dicionario_cnae(projeto)
    assert dicionario["subclasse"].is_unique
    assert len(dicionario) == 2
    assert dicionario.loc[
        dicionario["subclasse"] == "Geração de energia elétrica", "Código"
    ].tolist() == [3511500]


def test_dicionario_ausente_da_mensagem_util(projeto: Config):
    projeto.dicionario_cnae.unlink()
    with pytest.raises(FileNotFoundError, match="SHIFT_SHARE_DICIONARIO_CNAE"):
        carregar_dicionario_cnae(projeto)


def test_dicionario_sem_as_colunas_certas_e_erro(projeto: Config):
    pd.DataFrame({"cnae": [1], "nome": ["x"]}).to_csv(
        projeto.dicionario_cnae, index=False
    )
    with pytest.raises(ErroDeTratamento, match="faltam as colunas"):
        carregar_dicionario_cnae(projeto)


# --- invariante de classificação --------------------------------------------
def test_classificacao_unica_aceita_base_bem_recortada():
    base = pd.DataFrame(
        {
            "NM_MUN": ["Acauã", "Acauã"],
            "subclasse": ["Bovino", "Ovino"],
            "classificacao_regiao": ["T1", "T3"],
        }
    )
    conferir_classificacao_unica(base, "teste")  # não levanta


def test_classificacao_duplicada_e_denunciada():
    # O mesmo setor com dois tipos: é o sintoma de referência ou ano vazando.
    base = pd.DataFrame(
        {
            "NM_MUN": ["Acauã", "Acauã"],
            "subclasse": ["Bovino", "Bovino"],
            "classificacao_regiao": ["T1", "T7"],
        }
    )
    with pytest.raises(ErroDeTratamento, match="mais de uma classificação"):
        conferir_classificacao_unica(base, "teste")


# --- recorte das bases ------------------------------------------------------
def test_base_sidra_perde_os_agregados_e_ganha_o_codigo(projeto_processado: Config):
    from shift_share_piaui.r_compat import ler_csv_r

    tratada = tratar_base_sidra(
        ler_csv_r(projeto_processado.consolidado_sidra(REBANHOS)),
        cods_ibge=carregar_cods_ibge(projeto_processado),
        fonte=REBANHOS,
        ano_t0=2013,
    )

    assert set(tratada["NM_MUN"]) == {"Acauã", "Bom Jesus"}
    assert "Brasil" not in set(tratada["NM_MUN"])
    assert tratada["REFERENCIA_GEOGRAFICA"].unique().tolist() == ["Brasil"]
    assert tratada["Fonte"].unique().tolist() == ["PPM"]
    assert tratada["Unidade de medida"].unique().tolist() == ["cabeças"]
    assert tratada["CD_MUN"].tolist() == sorted(tratada["CD_MUN"].tolist())[: len(tratada)]


def test_base_rais_fica_so_com_as_faixas_de_cnae_escolhidas(projeto_processado: Config):
    from shift_share_piaui.r_compat import ler_csv_r

    tratada = tratar_base_rais(
        ler_csv_r(projeto_processado.consolidado_rais("Brasil")),
        cods_ibge=carregar_cods_ibge(projeto_processado),
        dicionario_cnae=carregar_dicionario_cnae(projeto_processado),
        ano_t0=2013,
    )

    # As duas subclasses do projeto de brinquedo estão dentro das faixas.
    assert set(tratada["subclasse"]) == {
        "Extração de carvão mineral",
        "Fabricação de biscoitos",
    }
    assert tratada["Fonte"].unique().tolist() == ["RAIS"]
    assert tratada["Unidade de medida"].unique().tolist() == ["pessoas"]
    assert tratada["Código"].notna().all()


def test_base_rais_descarta_subclasse_fora_das_faixas(projeto_processado: Config):
    from shift_share_piaui.r_compat import ler_csv_r

    # Código de comércio varejista: fora de todas as faixas mantidas.
    dicionario = pd.DataFrame(
        {
            "subclasse": ["Extração de carvão mineral", "Fabricação de biscoitos"],
            "Código": [510000, 4711301],
        }
    )
    tratada = tratar_base_rais(
        ler_csv_r(projeto_processado.consolidado_rais("Brasil")),
        cods_ibge=carregar_cods_ibge(projeto_processado),
        dicionario_cnae=dicionario,
        ano_t0=2013,
    )
    assert set(tratada["subclasse"]) == {"Extração de carvão mineral"}


def test_base_rais_ignora_setores_zerados_nos_dois_anos(projeto_processado: Config):
    from shift_share_piaui.r_compat import ler_csv_r

    base = ler_csv_r(projeto_processado.consolidado_rais("Brasil"))
    tratada = tratar_base_rais(
        base,
        cods_ibge=carregar_cods_ibge(projeto_processado),
        dicionario_cnae=carregar_dicionario_cnae(projeto_processado),
        ano_t0=2013,
    )
    assert (tratada["status"] != 2).all()


# --- consolidação por tipo --------------------------------------------------
def _base_falsa(fonte: str, municipios: list[str], tipos: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "subclasse": [f"{fonte}.setor" for _ in municipios],
            "NM_MUN": municipios,
            "classificacao_regiao": tipos,
            "Fonte": fonte,
        }
    )


def test_consolidacao_mantem_so_o_tipo_pedido():
    cods = pd.DataFrame({"NM_MUN": ["Acauã", "Bom Jesus"]})
    base = _base_falsa("PAM", ["Acauã", "Bom Jesus"], ["T1", "T7"])

    consolidado = consolidar_por_tipo([base], cods, "T1")
    assert consolidado["NM_MUN"].tolist() == ["Acauã"]


def test_consolidacao_ordena_por_municipio_e_depois_por_base():
    cods = pd.DataFrame({"NM_MUN": ["Acauã", "Bom Jesus"]})
    primeira = _base_falsa("PAM", ["Acauã", "Bom Jesus"], ["T1", "T1"])
    segunda = _base_falsa("RAIS", ["Acauã", "Bom Jesus"], ["T1", "T1"])

    consolidado = consolidar_por_tipo([primeira, segunda], cods, "T1")
    assert consolidado["NM_MUN"].tolist() == ["Acauã", "Acauã", "Bom Jesus", "Bom Jesus"]
    assert consolidado["Fonte"].tolist() == ["PAM", "RAIS", "PAM", "RAIS"]


def test_consolidacao_descarta_municipio_fora_da_tabela_de_correlacao():
    cods = pd.DataFrame({"NM_MUN": ["Acauã"]})
    base = _base_falsa("PAM", ["Acauã", "Brasil"], ["T1", "T1"])

    consolidado = consolidar_por_tipo([base], cods, "T1")
    assert consolidado["NM_MUN"].tolist() == ["Acauã"]


def test_consolidacao_limpa_o_rotulo_do_produto():
    cods = pd.DataFrame({"NM_MUN": ["Acauã"]})
    base = pd.DataFrame(
        {
            "subclasse": ["Suíno...total"],
            "NM_MUN": ["Acauã"],
            "classificacao_regiao": ["T1"],
            "Fonte": ["PPM"],
        }
    )
    assert consolidar_por_tipo([base], cods, "T1")["subclasse"].tolist() == [
        "Suíno total"
    ]


def test_consolidacao_de_tipo_sem_setor_devolve_quadro_vazio():
    cods = pd.DataFrame({"NM_MUN": ["Acauã"]})
    base = _base_falsa("PAM", ["Acauã"], ["T1"])
    assert consolidar_por_tipo([base], cods, "T8").empty


# --- etapa completa ---------------------------------------------------------
def test_tratamento_grava_uma_aba_por_tipo(projeto_processado: Config):
    escritos = tratamento.executar(projeto_processado, verbose=False)
    caminho = escritos[2013]

    assert caminho.exists()
    assert pd.ExcelFile(caminho).sheet_names == [
        "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T-1",
    ]


def test_tratamento_junta_rais_e_ibge_no_mesmo_arquivo(projeto_processado: Config):
    tratamento.executar(projeto_processado, verbose=False)
    caminho = projeto_processado.bruto_por_tipo(2013)

    fontes = set()
    for aba in pd.ExcelFile(caminho).sheet_names:
        fontes.update(pd.read_excel(caminho, sheet_name=aba).get("Fonte", pd.Series()))
    assert fontes == {"RAIS", "PPM"}


# --- casamento tolerante de rótulos -----------------------------------------
def test_normalizacao_ignora_acento_caixa_e_espacamento():
    from shift_share_piaui.tratamento import normalizar_rotulo

    assert normalizar_rotulo("Gás liqüefeito") == normalizar_rotulo("gas liquefeito")
    assert normalizar_rotulo("Defesa Civil") == normalizar_rotulo("defesa civil")
    # Espaço não separável, como aparece em alguns rótulos do BGCAGED.
    assert normalizar_rotulo("Atividades de\xa0franqueadas") == "atividades de franqueadas"


def test_dicionario_recupera_rotulo_que_so_difere_por_tipografia():
    from shift_share_piaui.tratamento import completar_dicionario

    dicionario = pd.DataFrame(
        {
            "subclasse": ["Comércio varejista de gás liquefeito de petróleo (glp)"],
            "Código": [4784900],
        }
    )
    completo, sem_codigo = completar_dicionario(
        dicionario, ["Comércio varejista de gás liqüefeito de petróleo (GLP)"]
    )

    assert sem_codigo == []
    recuperado = completo[
        completo["subclasse"] == "Comércio varejista de gás liqüefeito de petróleo (GLP)"
    ]
    assert recuperado["Código"].tolist() == [4784900]


def test_dicionario_nao_inventa_codigo_para_rotulo_ambiguo():
    from shift_share_piaui.tratamento import completar_dicionario

    # Duas subclasses cuja forma normalizada coincide: não há como escolher.
    dicionario = pd.DataFrame(
        {
            "subclasse": ["Geração de energia elétrica", "Geracao de energia eletrica"],
            "Código": [3511500, 3511501],
        }
    )
    completo, sem_codigo = completar_dicionario(dicionario, ["GERAÇÃO DE ENERGIA ELÉTRICA"])

    assert sem_codigo == ["GERAÇÃO DE ENERGIA ELÉTRICA"]
    assert len(completo) == 2


def test_dicionario_devolve_rotulo_sem_correspondencia_nenhuma():
    from shift_share_piaui.tratamento import completar_dicionario

    dicionario = pd.DataFrame({"subclasse": ["Cultivo de arroz"], "Código": [111301]})
    completo, sem_codigo = completar_dicionario(dicionario, ["Invalida", "Ignorada"])

    assert sem_codigo == ["Invalida", "Ignorada"]
    assert len(completo) == 1


def test_normalizacao_pode_ser_desligada():
    from shift_share_piaui.tratamento import completar_dicionario

    dicionario = pd.DataFrame({"subclasse": ["Defesa civil"], "Código": [8425600]})
    completo, sem_codigo = completar_dicionario(
        dicionario, ["Defesa Civil"], normalizar=False
    )

    assert sem_codigo == ["Defesa Civil"]
    assert len(completo) == 1


def test_subclasse_sem_codigo_gera_aviso_em_vez_de_sumir(projeto_processado: Config):
    from shift_share_piaui.r_compat import ler_csv_r

    # Dicionário que não cobre uma das duas subclasses do projeto.
    dicionario = pd.DataFrame(
        {"subclasse": ["Extração de carvão mineral"], "Código": [510000]}
    )
    with pytest.warns(UserWarning, match="sem código no dicionário"):
        tratada = tratar_base_rais(
            ler_csv_r(projeto_processado.consolidado_rais("Brasil")),
            cods_ibge=carregar_cods_ibge(projeto_processado),
            dicionario_cnae=dicionario,
            ano_t0=2013,
        )
    assert set(tratada["subclasse"]) == {"Extração de carvão mineral"}


def test_dicionario_do_caged_e_lido_da_aba_subclasse(projeto: Config):
    # O arquivo real tem 24 abas; a que interessa é "subclasse".
    caminho = projeto.tabelas_correlacao / "dicionario_cnae_subclasse.xlsx"
    with pd.ExcelWriter(caminho) as escritor:
        pd.DataFrame({"Código": [1], "Descrição": ["Errado"]}).to_excel(
            escritor, sheet_name="região", index=False
        )
        pd.DataFrame({"Código": [111301], "Descrição": ["Cultivo de Arroz"]}).to_excel(
            escritor, sheet_name="subclasse", index=False
        )
    (projeto.tabelas_correlacao / "dicionario_cnae_subclasse.csv").unlink()

    dicionario = carregar_dicionario_cnae(projeto)
    assert dicionario["subclasse"].tolist() == ["Cultivo de arroz"]
