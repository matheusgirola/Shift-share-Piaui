"""Categorização das potencialidades produtivas por município.

Segunda metade do notebook ``Potencialidades-todas-categorias e anos``: a
partir dos ``.xlsx`` por tipo de região, mantém os setores de um ou mais tipos
(``T1`` sozinho, ou ``T1``+``T2`` para o Mapa de Potencialidades físico),
agrupa cada setor em uma potencialidade e produz os recortes usados no mapa e
no relatório.

Duas classificações convivem aqui, como no notebook:

* as bases do IBGE são categorizadas por lista de produtos
  (:func:`classificar_agropecuaria`);
* a RAIS é categorizada pela faixa do código da CNAE 2.0
  (:func:`classificar_rais`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from shift_share_piaui.config import (
    COLUNAS_POTENCIALIDADES,
    DEFAULT_CONFIG,
    Config,
)
from shift_share_piaui.tratamento import (
    FONTE_RAIS,
    carregar_cods_ibge,
    carregar_dicionario_cnae,
    completar_dicionario,
)

# Rótulo usado quando o setor não se encaixa em nenhuma potencialidade. É um
# espaço porque foi assim que a coluna nasceu no notebook, e as planilhas já
# distribuídas dependem desse valor.
SEM_CATEGORIA = " "

# Produtos das pesquisas do IBGE agrupados em potencialidades.
CATEGORIAS_AGROPECUARIAS: dict[str, tuple[str, ...]] = {
    "Ovinocaprinocultura": ("Caprino", "Ovino"),
    "Avicultura": (
        "Galináceos total",
        "Ovino",
        "Codornas",
        "Ovos de galinha",
        "Ovos de codorna",
    ),
    "Bovinocultura": ("Bovino", "Bubalino", "Leite"),
    "Equinocultura": ("Equino",),
    "Apicultura e Meliponicultura": ("Mel de abelha",),
    "Suinocultura": ("Suíno total",),
    "Pesca, Piscicultura e Aquicultura": (
        "Tambacu tambatinga",
        "Pintado cachara cachapira e pintachara surubim",
        "Pirarucu",
        "Tilápia",
        "Tambaqui",
        "Camarão",
        "Outros peixes",
        "Traíra e trairão",
        "Piau piapara piauçu piava",
        "Carpa",
        "Alevinos",
    ),
    "Agronegócio": (
        "Milho em grão",
        "Soja em grão",
        "Sorgo em grão",
        "Batata doce",
        "Cebola",
        "Arroz em casca",
        "Fava em grão",
        "Amendoim em casca",
        "Feijão em grão",
        "Algodão herbáceo em caroço",
        "Mandioca",
        "Cana de açúcar",
    ),
    "Extrativismo": (
        "Lenha",
        "Alimentícios",
        "Carvão vegetal",
        "Ceras",
        "Carnaúba pó",
        "Pequi fruto",
        "Madeira em tora",
        "Babaçu amêndoa",
        "Oleaginosos",
        "Maracujá",
    ),
    "Hortifruticultura": (
        "Uva",
        "Melão",
        "Tomate",
        "Manga",
        "Coco da baía",
        "Melancia",
        "Banana cacho",
        "Laranja",
        "Castanha de caju",
    ),
}

# Faixas de código da CNAE 2.0 -> potencialidade, na ordem de avaliação.
FAIXAS_POTENCIALIDADE: tuple[tuple[int, int, str], ...] = (
    (500_000, 1_000_000, "Mineração"),
    (1_000_000, 4_000_000, "Indústria"),
    (4_100_000, 4_400_000, "Construção"),
    (4_900_000, 5_400_000, "Transporte, armazenagem e correio"),
    (5_500_000, 5_700_000, "Alojamento e alimentação"),
    (5_800_000, 6_400_000, "Informação e comunicação"),
    (6_900_000, 7_300_000, "Atividades profissionais, científicas e técnicas"),
    (8_500_000, 8_600_000, "Polo de educação"),
    (8_600_000, 9_000_000, "Polo de saúde"),
    (9_000_000, 9_400_000, "Artes, cultura, esporte e recreação"),
)

FAIXA_ABERTA_FINAL = (9_400_000, "Outras atividades de serviço")

_PRODUTO_PARA_CATEGORIA: dict[str, str] = {}
for _categoria, _produtos in CATEGORIAS_AGROPECUARIAS.items():
    for _produto in _produtos:
        # "Ovino" está em dois grupos; como no encadeamento de ifs original,
        # a primeira ocorrência é a que vale.
        _PRODUTO_PARA_CATEGORIA.setdefault(_produto, _categoria)


def classificar_agropecuaria(subclasse: str) -> str:
    """Potencialidade de um produto das pesquisas do IBGE."""
    return _PRODUTO_PARA_CATEGORIA.get(subclasse, SEM_CATEGORIA)


def classificar_rais(subclasse: str, codigo: float | int | None) -> str | None:
    """Potencialidade de uma subclasse da CNAE 2.0.

    O artesanato é reconhecido pelo nome porque atravessa várias divisões da
    CNAE; o resto sai da faixa numérica do código.
    """
    if isinstance(subclasse, str) and "Artesanato" in subclasse:
        return "Artesanato"
    if codigo is None or pd.isna(codigo):
        return None
    codigo = float(codigo)
    for inicio, fim, potencialidade in FAIXAS_POTENCIALIDADE:
        if inicio < codigo < fim:
            return potencialidade
    inicio, potencialidade = FAIXA_ABERTA_FINAL
    if codigo > inicio:
        return potencialidade
    return None


# ---------------------------------------------------------------------------
# Consolidação por tipo de região
# ---------------------------------------------------------------------------
def empilhar_rodadas(
    cfg: Config = DEFAULT_CONFIG,
    tipo: str = "T1",
    colunas: tuple[str, ...] = COLUNAS_POTENCIALIDADES,
) -> pd.DataFrame:
    """Empilha a aba ``tipo`` de todas as rodadas e remove repetições.

    Um mesmo setor pode ser potencialidade em mais de uma rodada; fica a
    primeira ocorrência, isto é, a rodada mais antiga em que ele aparece.
    """
    partes = []
    for rodada in cfg.rodadas:
        caminho = cfg.bruto_por_tipo(rodada.rotulo)
        parte = pd.read_excel(caminho, sheet_name=tipo)
        parte["ANO"] = rodada.rotulo
        partes.append(parte)

    empilhado = pd.concat(partes, ignore_index=True)
    faltando = [coluna for coluna in colunas if coluna not in empilhado.columns]
    for coluna in faltando:
        empilhado[coluna] = pd.Series(dtype="object")
    empilhado = empilhado[list(colunas)]
    empilhado = empilhado.drop_duplicates(subset=["subclasse", "NM_MUN"], keep="first")
    return empilhado.sort_values(by="NM_MUN", kind="stable").reset_index(drop=True)


def categorizar(
    empilhado: pd.DataFrame,
    dicionario_cnae: pd.DataFrame,
    normalizar_subclasses: bool = True,
) -> pd.DataFrame:
    """Acrescenta a coluna ``Potencialidade`` a cada setor."""
    rais = empilhado[empilhado["Fonte"] == FONTE_RAIS].copy()
    # O mesmo casamento tolerante usado no tratamento: sem ele, as subclasses
    # recuperadas lá chegariam aqui sem código e ficariam sem potencialidade.
    dicionario_cnae, _ = completar_dicionario(
        dicionario_cnae, rais["subclasse"], normalizar=normalizar_subclasses
    )
    rais = rais.merge(dicionario_cnae, on="subclasse", how="left", validate="m:1")
    # pyrefly: ignore[unsupported-operation]  # stub do pandas não cobre atribuir list a coluna
    rais["Potencialidade"] = [
        classificar_rais(subclasse, codigo)
        for subclasse, codigo in zip(rais["subclasse"], rais["Código"], strict=True)
    ]
    rais = rais.drop(columns=["Código"])

    agro = empilhado[empilhado["Fonte"] != FONTE_RAIS].copy()
    agro["Potencialidade"] = agro["subclasse"].map(classificar_agropecuaria)

    return pd.concat([rais, agro], ignore_index=True)


# ---------------------------------------------------------------------------
# Recortes derivados
# ---------------------------------------------------------------------------
def contar_potencialidades(categorizado: pd.DataFrame) -> pd.DataFrame:
    """Municípios x potencialidades, com a contagem de setores em cada uma."""
    tabela = pd.pivot_table(
        categorizado,
        index="NM_MUN",
        columns="Potencialidade",
        values="subclasse",
        aggfunc="count",
        fill_value=0,
    )
    tabela.columns.name = None
    return tabela.reset_index()


def binarizar_potencialidades(
    contagem: pd.DataFrame,
    cods_ibge: pd.DataFrame,
) -> pd.DataFrame:
    """Versão 0/1 da contagem, com o código do IBGE e todos os municípios.

    Municípios sem nenhuma potencialidade do tipo entram zerados -- no
    notebook eles ficavam vazios, o que virava buraco no mapa.
    """
    binario = contagem.set_index("NM_MUN")
    binario = (binario != 0).astype("int64")
    completo = cods_ibge.set_index("NM_MUN")[["CD_MUN"]].join(binario, how="left").reset_index()
    colunas_potencialidade = [
        coluna for coluna in completo.columns if coluna not in {"NM_MUN", "CD_MUN"}
    ]
    completo[colunas_potencialidade] = completo[colunas_potencialidade].fillna(0).astype("int64")
    return completo


def descrever_por_territorio(
    categorizado: pd.DataFrame,
    territorios: pd.DataFrame,
    quantidade: int = 5,
) -> str:
    """Texto com os principais setores de cada potencialidade, por território.

    O ranking usa ``Estoque_mun_t1`` como está, sem converter unidades -- os
    setores de um mesmo grupo podem estar em cabeças, pessoas ou mil reais.
    """
    base = categorizado.merge(territorios[["NM_MUN", "pi_micro_m"]], on="NM_MUN")
    base = base[["pi_micro_m", "subclasse", "Potencialidade", "Estoque_mun_t1"]]

    linhas: list[str] = []
    for territorio in base["pi_micro_m"].unique():
        linhas.append(f"\n### {territorio} ###################################\n")
        recorte = base[base["pi_micro_m"] == territorio]
        for potencialidade in recorte["Potencialidade"].unique():
            principais = (
                recorte[recorte["Potencialidade"] == potencialidade]
                .groupby("subclasse")[["Estoque_mun_t1"]]
                .sum()
                .sort_values("Estoque_mun_t1", ascending=False)
                .head(quantidade)
            )
            linhas.append(f"{potencialidade} - {', '.join(principais.index)}\n\n")
    return "".join(linhas)


def subclasses_por_potencialidade(
    categorizado: pd.DataFrame,
) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    """Para cada potencialidade, dois quadros município x subclasse.

    O primeiro traz o estoque de t1 com as unidades em ``mil reais``
    convertidas para reais; o segundo, a versão 0/1. A conversão é feita linha
    a linha (o notebook usava a unidade da primeira linha do grupo, o que
    misturava cabeças e reais em grupos como a bovinocultura).
    """
    base = categorizado.copy()
    fator = np.where(base["Unidade de medida"] == "mil reais", 1000, 1)
    base["Estoque_convertido"] = base["Estoque_mun_t1"] * fator

    quadros: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for potencialidade in base["Potencialidade"].dropna().unique():
        recorte = base[base["Potencialidade"] == potencialidade]
        com_valor = pd.pivot_table(
            recorte,
            index="NM_MUN",
            columns="subclasse",
            values="Estoque_convertido",
            aggfunc="sum",
            fill_value=0,
        )
        com_valor.columns.name = None
        binario = (com_valor != 0).astype("int64")
        quadros[potencialidade] = (com_valor, binario)
    return quadros


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
def _nome_de_arquivo(rotulo: str) -> str:
    return rotulo.replace("/", "-").replace(" ", "_")


def executar(
    cfg: Config = DEFAULT_CONFIG,
    tipos: tuple[str, ...] = ("T1", "T2"),
    verbose: bool = True,
) -> dict[str, Path]:
    """Categoriza os tipos pedidos e grava todos os recortes derivados.

    ``tipos=('T1',)`` reproduz o recorte usado no relatório; ``('T1', 'T2')``
    é o do Mapa de Potencialidades físico.
    """
    cods_ibge = carregar_cods_ibge(cfg)
    dicionario_cnae = carregar_dicionario_cnae(cfg)
    territorios = pd.read_excel(cfg.territorios)

    destino = cfg.saida_tratamento
    destino.mkdir(parents=True, exist_ok=True)
    escritos: dict[str, Path] = {}

    categorizados = []
    for tipo in tipos:
        if verbose:
            print(f"Categorizando as potencialidades do tipo {tipo}")
        categorizado = categorizar(
            empilhar_rodadas(cfg, tipo),
            dicionario_cnae,
            normalizar_subclasses=cfg.casar_subclasse_normalizada,
        )
        categorizados.append(categorizado)
        caminho = cfg.categorizado(tipo)
        categorizado.to_excel(caminho, index=False)
        escritos[f"categorizado_{tipo}"] = caminho

    consolidado = pd.concat(categorizados, ignore_index=True)

    contagem = contar_potencialidades(consolidado)
    caminho = cfg.com_numeros(tipos)
    contagem.to_excel(caminho, index=False)
    escritos["com_numeros"] = caminho

    binario = binarizar_potencialidades(contagem, cods_ibge)
    caminho = cfg.binario(tipos)
    binario.to_excel(caminho, index=False)
    escritos["binario"] = caminho

    caminho = cfg.descricao_territorios(tipos)
    caminho.write_text(descrever_por_territorio(consolidado, territorios), encoding="utf-8")
    escritos["descricao"] = caminho

    pasta_valor = destino / "Subclasses_dummy" / "Com_valor"
    pasta_binario = destino / "Subclasses_dummy" / "Binario"
    pasta_valor.mkdir(parents=True, exist_ok=True)
    pasta_binario.mkdir(parents=True, exist_ok=True)
    for potencialidade, (com_valor, dummy) in subclasses_por_potencialidade(consolidado).items():
        nome = _nome_de_arquivo(potencialidade.strip() or "Sem_categoria")
        com_valor.to_excel(pasta_valor / f"{nome}_subclasses_com_valor.xlsx")
        dummy.to_excel(pasta_binario / f"{nome}_subclasses_binario.xlsx")
    escritos["subclasses_dummy"] = destino / "Subclasses_dummy"

    if verbose:
        print(f"Arquivos gravados em {destino}")
    return escritos
