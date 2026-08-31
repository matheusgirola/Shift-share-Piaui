"""Tratamento e consolidação dos resultados do shift-share.

Primeira metade do notebook ``Potencialidades-todas-categorias e anos``: junta
as seis bases de shift-share (RAIS + as cinco pesquisas do IBGE), padroniza os
nomes de municípios e de setores, recorta a comparação nacional e grava um
``.xlsx`` por rodada, com uma aba por tipo de região.
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from shift_share_piaui.config import (
    AGREGADOS_SIDRA,
    TIPOS,
    Config,
    DEFAULT_CONFIG,
    FonteSidra,
    Rodada,
)
from shift_share_piaui.shift_share import STATUS_VAZIO

UNIDADE_RAIS = "pessoas"
FONTE_RAIS = "RAIS"

# Faixas de código da CNAE 2.0 mantidas na base de vínculos: tira agropecuária
# (que vem das pesquisas do IBGE), comércio e administração pública.
FAIXAS_CNAE: tuple[tuple[int, int], ...] = (
    (500_000, 4_500_000),
    (4_900_000, 6_300_000),
    (6_900_000, 7_300_000),
    (8_500_000, 9_000_000),
)

# Caracteres que sobraram do ``make.names()`` do R nos rótulos do SIDRA.
_RUIDO_SIDRA = re.compile(r"[X0-9.]")

_ESPACOS = re.compile(r"\s+")


class ErroDeTratamento(ValueError):
    """A base tratada não satisfaz uma invariante do pipeline."""


# ---------------------------------------------------------------------------
# Padronização de rótulos
# ---------------------------------------------------------------------------
def padronizar_nome_rais(nome_municipio: str) -> str:
    """``PI-BARRA D ALCANTARA`` -> ``PI.BARRA.D.ALCANTARA``.

    É a forma que o nome ganha ao virar cabeçalho de coluna no R, e é por ela
    que a tabela de correlação se liga aos resultados da RAIS.
    """
    return nome_municipio.replace("-", " ").replace(" ", ".")


def remover_uf(nome_municipio: str) -> str:
    """``Acauã (PI)`` -> ``Acauã``."""
    return nome_municipio.replace(" (PI)", "")


def formatar_texto_producao(texto: str) -> str:
    """Limpa o rótulo de um produto do SIDRA.

    ``Suíno...total`` -> ``Suíno total``; ``X1.2...Castanha.de.caju`` ->
    ``Castanha de caju``. Dígitos, pontos e o ``X`` que o R usa como prefixo
    viram espaço, e os espaços repetidos colapsam.
    """
    limpo = _RUIDO_SIDRA.sub(" ", texto)
    return " ".join(pedaco for pedaco in limpo.split(" ") if pedaco)


def filtrar(base: pd.DataFrame, municipio: str, tipo: str) -> pd.DataFrame:
    """Recorte de uma base por município e tipo de região."""
    return base[(base["NM_MUN"] == municipio) & (base["classificacao_regiao"] == tipo)]


# ---------------------------------------------------------------------------
# Tabelas de apoio
# ---------------------------------------------------------------------------
def carregar_cods_ibge(cfg: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    """Correlação entre nomes da RAIS, nomes e códigos do IBGE."""
    cods = pd.read_excel(cfg.cidades_rais_ibge)
    cods["NM_MUN_RAIS"] = cods["NM_MUN_RAIS"].map(padronizar_nome_rais)
    return cods


def carregar_dicionario_cnae(cfg: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    """Dicionário de subclasses da CNAE 2.0: descrição -> código numérico.

    Aceita ``.xlsx`` (aba ``subclasse``, formato do dicionário do CAGED) ou
    ``.csv``. A descrição é capitalizada porque é assim que ela aparece nos
    extratos da RAIS, que é a chave da junção.
    """
    caminho = Path(cfg.dicionario_cnae)
    if not caminho.exists():
        raise FileNotFoundError(
            "Dicionário de subclasses da CNAE 2.0 não encontrado em "
            f"{caminho}. Coloque o arquivo (colunas 'Código' e 'Descrição') em "
            "Tabelas-Correlacao/ ou aponte SHIFT_SHARE_DICIONARIO_CNAE para ele."
        )

    if caminho.suffix.lower() in {".xlsx", ".xls", ".xlsm"}:
        # O dicionário do CAGED tem duas dezenas de abas; a que interessa é a
        # "subclasse". Arquivos reduzidos, com uma aba só, também servem.
        with pd.ExcelFile(caminho) as planilha:
            aba = "subclasse" if "subclasse" in planilha.sheet_names else planilha.sheet_names[0]
            dicionario = pd.read_excel(planilha, sheet_name=aba)
    else:
        dicionario = pd.read_csv(caminho, sep=None, engine="python")

    renomear = {"Descrição": "subclasse", "Descricao": "subclasse", "Codigo": "Código"}
    dicionario = dicionario.rename(columns=renomear)
    faltando = {"subclasse", "Código"} - set(dicionario.columns)
    if faltando:
        raise ErroDeTratamento(
            f"{caminho.name}: faltam as colunas {sorted(faltando)} no dicionário da CNAE."
        )

    dicionario = dicionario[["subclasse", "Código"]].copy()
    dicionario["subclasse"] = dicionario["subclasse"].astype(str).str.capitalize()
    dicionario["Código"] = pd.to_numeric(dicionario["Código"], errors="coerce")
    # A descrição capitalizada não é única no dicionário original; sem
    # deduplicar, a junção vira um-para-muitos e replica linhas da RAIS.
    return dicionario.drop_duplicates(subset="subclasse", keep="first")


# ---------------------------------------------------------------------------
# Preparação de cada base
# ---------------------------------------------------------------------------
def normalizar_rotulo(texto: str) -> str:
    """Forma canônica de um rótulo de subclasse, para casamento tolerante.

    Ignora acentuação, caixa e espaçamento (inclusive o espaço não separável
    que aparece em alguns rótulos do BGCAGED). Serve só para reencontrar no
    dicionário rótulos que diferem por detalhes tipográficos -- "gás
    liqüefeito" contra "gás liquefeito", "Defesa Civil" contra "Defesa civil".
    """
    decomposto = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return _ESPACOS.sub(" ", sem_acento).strip().casefold()


def completar_dicionario(
    dicionario_cnae: pd.DataFrame,
    subclasses: Iterable[str],
    normalizar: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    """Acrescenta ao dicionário os rótulos recuperáveis por normalização.

    O dicionário do CAGED e os extratos da RAIS escrevem a mesma subclasse de
    formas ligeiramente diferentes, e o casamento exato deixava 61 subclasses
    sem código -- que eram descartadas em silêncio. Aqui, um rótulo sem
    correspondência exata é reaproveitado quando sua forma normalizada aponta
    para um único código.

    Returns
    -------
    (dicionário acrescido, rótulos que continuaram sem código)
    """
    conhecidos = set(dicionario_cnae["subclasse"])
    pendentes = [
        rotulo
        for rotulo in dict.fromkeys(subclasses)
        if isinstance(rotulo, str) and rotulo not in conhecidos
    ]
    if not pendentes:
        return dicionario_cnae, []
    if not normalizar:
        return dicionario_cnae, pendentes

    por_forma_normal: dict[str, set[float]] = {}
    for rotulo, codigo in zip(dicionario_cnae["subclasse"], dicionario_cnae["Código"]):
        por_forma_normal.setdefault(normalizar_rotulo(rotulo), set()).add(codigo)

    recuperados: list[dict[str, object]] = []
    sem_codigo: list[str] = []
    for rotulo in pendentes:
        # Só aproveita quando a forma normalizada é inequívoca.
        codigos = por_forma_normal.get(normalizar_rotulo(rotulo), set())
        if len(codigos) == 1:
            recuperados.append({"subclasse": rotulo, "Código": next(iter(codigos))})
        else:
            sem_codigo.append(rotulo)

    if not recuperados:
        return dicionario_cnae, sem_codigo
    completo = pd.concat(
        [dicionario_cnae, pd.DataFrame(recuperados)], ignore_index=True
    )
    return completo, sem_codigo


def conferir_classificacao_unica(base: pd.DataFrame, contexto: str) -> None:
    """Garante uma única classificação por (município, setor).

    Se estourar, alguma referência geográfica ou algum ano inicial vazou para
    dentro do recorte -- foi exatamente o que produziu setores com até seis
    classificações simultâneas na versão original.
    """
    chave = ["NM_MUN_RAIS", "subclasse"] if "NM_MUN_RAIS" in base.columns else ["NM_MUN", "subclasse"]
    contagem = base.groupby(chave, dropna=False)["classificacao_regiao"].nunique()
    if (contagem > 1).any():
        exemplos = contagem[contagem > 1].head(3).index.tolist()
        raise ErroDeTratamento(
            f"{contexto}: há setores com mais de uma classificação, ex.: {exemplos}"
        )


def tratar_base_rais(
    consolidado: pd.DataFrame,
    cods_ibge: pd.DataFrame,
    dicionario_cnae: pd.DataFrame,
    ano_t0: int,
    referencia: str = "Brasil",
    normalizar_subclasses: bool = True,
) -> pd.DataFrame:
    """Recorta e enriquece o shift-share da RAIS para uma rodada."""
    dicionario_cnae, sem_codigo = completar_dicionario(
        dicionario_cnae, consolidado["subclasse"], normalizar=normalizar_subclasses
    )
    if sem_codigo:
        # Sem código não há como saber se a subclasse fica ou sai: ela é
        # descartada, mas nunca em silêncio.
        warnings.warn(
            f"{len(sem_codigo)} subclasse(s) da RAIS sem código no dicionário da "
            f"CNAE serão descartadas, ex.: {sem_codigo[:3]}",
            stacklevel=2,
        )

    base = consolidado.join(cods_ibge.set_index("NM_MUN_RAIS"), on="NM_MUN_RAIS")
    base = base.merge(dicionario_cnae, on="subclasse", how="left", validate="m:1")

    dentro_da_faixa = np.zeros(len(base), dtype=bool)
    for inicio, fim in FAIXAS_CNAE:
        dentro_da_faixa |= (base["Código"] > inicio) & (base["Código"] < fim)
    base = base[dentro_da_faixa]

    base = base[base["status"] != STATUS_VAZIO]
    base = base[base["REFERENCIA_GEOGRAFICA"] == referencia]
    base = base[base["ANO_T0"] == ano_t0].copy()

    base["Fonte"] = FONTE_RAIS
    base["Unidade de medida"] = UNIDADE_RAIS
    conferir_classificacao_unica(base, f"RAIS {ano_t0}/{referencia}")
    return base


def tratar_base_sidra(
    consolidado: pd.DataFrame,
    cods_ibge: pd.DataFrame,
    fonte: FonteSidra,
    ano_t0: int,
    referencia: str = "Brasil",
) -> pd.DataFrame:
    """Recorta e enriquece o shift-share de uma pesquisa do IBGE."""
    base = consolidado.copy()
    base["NM_MUN_RAIS"] = base["NM_MUN_RAIS"].map(remover_uf)
    base = base.rename(columns={"NM_MUN_RAIS": "NM_MUN"})
    base = base.join(cods_ibge.set_index("NM_MUN"), on="NM_MUN")
    # As linhas de Brasil, grandes regiões e Piauí vêm junto no extrato do
    # SIDRA; aqui só interessam os municípios.
    base = base[~base["NM_MUN"].isin(AGREGADOS_SIDRA)]
    base = base[base["status"] != STATUS_VAZIO]
    base = base[base["ANO_T0"] == ano_t0]
    base = base[base["REFERENCIA_GEOGRAFICA"] == referencia].copy()

    base["Fonte"] = fonte.nome
    base["Unidade de medida"] = fonte.unidade
    conferir_classificacao_unica(base, f"{fonte.prefixo} {ano_t0}/{referencia}")
    return base


# ---------------------------------------------------------------------------
# Consolidação por tipo de região
# ---------------------------------------------------------------------------
def consolidar_por_tipo(
    bases: list[pd.DataFrame],
    cods_ibge: pd.DataFrame,
    tipo: str,
) -> pd.DataFrame:
    """Empilha as bases já tratadas para um tipo de região.

    A ordem das linhas reproduz a do notebook -- município a município, na
    ordem da tabela de correlação, e dentro de cada município na ordem em que
    as bases são passadas -- porque é ela que decide qual fonte prevalece
    quando o mesmo setor aparece em mais de uma rodada.
    """
    ordem_municipios = {
        municipio: posicao
        for posicao, municipio in enumerate(cods_ibge["NM_MUN"].unique())
    }

    recortes = []
    for posicao_base, base in enumerate(bases):
        recorte = base[
            (base["classificacao_regiao"] == tipo) & (base["NM_MUN"].isin(ordem_municipios))
        ].copy()
        if recorte.empty:
            continue
        recorte["subclasse"] = recorte["subclasse"].map(formatar_texto_producao)
        recorte["_ordem_municipio"] = recorte["NM_MUN"].map(ordem_municipios)
        recorte["_ordem_base"] = posicao_base
        recortes.append(recorte)

    if not recortes:
        # Um tipo sem nenhum setor ainda precisa devolver as colunas certas:
        # a aba correspondente é gravada vazia, mas com cabeçalho.
        return pd.concat([base.head(0) for base in bases], ignore_index=True)

    consolidado = pd.concat(recortes, ignore_index=True)
    consolidado = consolidado.sort_values(
        ["_ordem_municipio", "_ordem_base"], kind="stable"
    )
    consolidado = consolidado.drop(columns=["_ordem_municipio", "_ordem_base"])
    # Rede de segurança contra linhas 100% idênticas -- por exemplo, dois
    # produtos cujos rótulos colapsam no mesmo texto depois da limpeza.
    return consolidado.drop_duplicates().reset_index(drop=True)


def carregar_bases_da_rodada(
    rodada: Rodada,
    cfg: Config = DEFAULT_CONFIG,
    cods_ibge: pd.DataFrame | None = None,
    dicionario_cnae: pd.DataFrame | None = None,
) -> list[pd.DataFrame]:
    """Lê e trata as seis bases de uma rodada, na ordem usada no notebook."""
    from shift_share_piaui.r_compat import ler_csv_r

    cods_ibge = carregar_cods_ibge(cfg) if cods_ibge is None else cods_ibge
    dicionario_cnae = (
        carregar_dicionario_cnae(cfg) if dicionario_cnae is None else dicionario_cnae
    )

    bases = [
        tratar_base_sidra(
            ler_csv_r(cfg.consolidado_sidra(fonte)),
            cods_ibge=cods_ibge,
            fonte=fonte,
            ano_t0=rodada.ano_t0_sidra,
            referencia=cfg.referencia,
        )
        for fonte in cfg.fontes_sidra
    ]
    bases.append(
        tratar_base_rais(
            ler_csv_r(cfg.consolidado_rais()),
            cods_ibge=cods_ibge,
            dicionario_cnae=dicionario_cnae,
            ano_t0=rodada.ano_t0_rais,
            referencia=cfg.referencia,
            normalizar_subclasses=cfg.casar_subclasse_normalizada,
        )
    )
    return bases


def executar(
    cfg: Config = DEFAULT_CONFIG,
    tipos: tuple[str, ...] = TIPOS,
    verbose: bool = True,
) -> dict[int, Path]:
    """Grava um ``.xlsx`` por rodada, com uma aba por tipo de região."""
    cods_ibge = carregar_cods_ibge(cfg)
    dicionario_cnae = carregar_dicionario_cnae(cfg)

    escritos: dict[int, Path] = {}
    for rodada in cfg.rodadas:
        if verbose:
            print(
                f"Tratando a rodada {rodada.rotulo} "
                f"(RAIS {rodada.ano_t0_rais}, IBGE {rodada.ano_t0_sidra})"
            )
        bases = carregar_bases_da_rodada(rodada, cfg, cods_ibge, dicionario_cnae)
        destino = cfg.bruto_por_tipo(rodada.rotulo)
        destino.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
            for tipo in tipos:
                consolidado = consolidar_por_tipo(bases, cods_ibge, tipo)
                if verbose:
                    print(f"  {tipo}: {len(consolidado)} setores")
                consolidado.to_excel(escritor, sheet_name=tipo, index=False)
        escritos[rodada.rotulo] = destino
    return escritos
