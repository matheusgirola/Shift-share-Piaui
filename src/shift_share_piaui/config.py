"""Parâmetros e caminhos do pipeline.

Tudo o que antes estava espalhado como caminho absoluto de Windows ou como
constante no meio dos scripts fica aqui, num único objeto de configuração.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

# Referências geográficas usadas como "nação" no shift-share.
REGIOES: tuple[str, ...] = ("Piauí", "Nordeste", "Brasil")

# Linhas dos arquivos SIDRA que são agregados, não municípios.
AGREGADOS_SIDRA: tuple[str, ...] = (
    "Brasil",
    "Norte",
    "Sul",
    "Sudeste",
    "Centro-Oeste",
    "Nordeste",
    "Piauí",
)

# Tipologia de Montañia & Márquez: os oito octantes de sinais mais o resíduo.
TIPOS: tuple[str, ...] = ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T-1")

# Colunas mantidas no arquivo categorizado por tipo (mapa de potencialidades).
COLUNAS_POTENCIALIDADES: tuple[str, ...] = (
    "subclasse",
    "classificacao_regiao",
    "NM_MUN",
    "Estoque_mun_t1",
    "Fonte",
    "Unidade de medida",
    "ANO",
)


@dataclass(frozen=True)
class FonteSidra:
    """Uma das cinco pesquisas do IBGE lidas em formato SIDRA."""

    nome: str
    """Rótulo gravado na coluna ``Fonte`` (PAM, PEVS, PPM)."""

    prefixo: str
    """Prefixo do arquivo em ``Dados/``, sem o ano."""

    saida: str
    """Nome do CSV consolidado gravado por :mod:`shift_share_piaui.pipeline_sidra`."""

    unidade: str
    """Unidade de medida do estoque (``mil reais``, ``cabeças``)."""


FONTES_SIDRA: tuple[FonteSidra, ...] = (
    FonteSidra(
        nome="PAM",
        prefixo="PAM_prod_agricola",
        saida="shift-share-consolidado_pam_prod_agricola.csv",
        unidade="mil reais",
    ),
    FonteSidra(
        nome="PEVS",
        prefixo="PEVS_prod_extracao_vegetal",
        saida="shift-share-consolidado_pevs_prod_extracao_vegetal.csv",
        unidade="mil reais",
    ),
    FonteSidra(
        nome="PPM",
        prefixo="PPM_prod_aquicultura",
        saida="shift-share-consolidado_ppm_prod_aquicultura.csv",
        unidade="mil reais",
    ),
    FonteSidra(
        nome="PPM",
        prefixo="PPM_prod_origem_animal",
        saida="shift-share-consolidado_ppm_prod_origem_animal.csv",
        unidade="mil reais",
    ),
    FonteSidra(
        nome="PPM",
        prefixo="PPM_Efetivo_rebanhos",
        saida="shift-share-consolidado_ppm_efetivo_rebanhos.csv",
        unidade="cabeças",
    ),
)


ARQUIVO_DE_CONFIGURACAO = "shift-share.toml"


def raiz_padrao() -> Path:
    """Raiz do repositório.

    Respeita ``SHIFT_SHARE_PIAUI_ROOT`` para permitir rodar o pipeline sobre
    outra cópia dos dados (é o que os testes fazem).
    """
    env = os.environ.get("SHIFT_SHARE_PIAUI_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # src/shift_share_piaui/config.py -> src/shift_share_piaui -> src -> raiz
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Rodada:
    """Uma comparação temporal do estudo (o "há 10 anos", "há 5", "recente").

    A RAIS e as pesquisas do IBGE têm calendários próprios, e o ano inicial
    disponível em cada uma nem sempre é o mesmo. Em vez de deixar esse
    pareamento implícito -- os scripts em R derivavam os anos por aritmética
    sobre o ano final --, cada rodada declara explicitamente qual ano inicial
    usa em cada base.
    """

    rotulo: int
    """Ano que nomeia os arquivos de saída e preenche a coluna ``ANO``."""

    ano_t0_rais: int
    ano_t0_sidra: int


# Rodadas padrão. O terceiro ano inicial da RAIS é 2023 (e não 2022, como a
# aritmética do script em R sugeria) porque é o extrato que acompanha o
# repositório; troque aqui se baixar o de 2022.
RODADAS_PADRAO: tuple[Rodada, ...] = (
    Rodada(rotulo=2013, ano_t0_rais=2013, ano_t0_sidra=2013),
    Rodada(rotulo=2018, ano_t0_rais=2018, ano_t0_sidra=2018),
    Rodada(rotulo=2022, ano_t0_rais=2023, ano_t0_sidra=2022),
)


@dataclass(frozen=True)
class Config:
    """Caminhos e parâmetros de uma execução do pipeline."""

    raiz: Path = field(default_factory=raiz_padrao)

    # --- anos de referência ------------------------------------------------
    ano_t1_rais: int = 2025
    ano_t1_sidra: int = 2024
    rodadas: tuple[Rodada, ...] = RODADAS_PADRAO

    # Pesquisas do IBGE que o projeto tem em Dados/. Restrinja a lista para
    # rodar o pipeline sobre um subconjunto delas.
    fontes_sidra: tuple[FonteSidra, ...] = FONTES_SIDRA

    # Reencontra no dicionário da CNAE subclasses que só diferem por acento,
    # caixa ou espaçamento. Desligue para reproduzir o comportamento do
    # notebook antigo, que descartava esses rótulos.
    casar_subclasse_normalizada: bool = True

    @property
    def anos_t0_rais(self) -> tuple[int, ...]:
        return tuple(rodada.ano_t0_rais for rodada in self.rodadas)

    @property
    def anos_t0_sidra(self) -> tuple[int, ...]:
        return tuple(rodada.ano_t0_sidra for rodada in self.rodadas)

    # Referência usada no tratamento/categorização. O R grava um CSV por
    # referência; o tratamento consome apenas uma delas.
    referencia: str = "Brasil"

    # Número de linhas de dados dos extratos da RAIS (BGCAGED): a primeira
    # linha é um cabeçalho de bloco, e depois das subclasses vem o rodapé com
    # as seleções da consulta.
    linhas_rais: int = 1363

    @property
    def dados(self) -> Path:
        return self.raiz / "Dados"

    @property
    def tabelas_correlacao(self) -> Path:
        return self.raiz / "Tabelas-Correlacao"

    @property
    def saida_shift_share(self) -> Path:
        """Onde vão os CSVs consolidados (o antigo diretório dos scripts R)."""
        return self.raiz / "Resultados" / "shift-share"

    @property
    def saida_tratamento(self) -> Path:
        """Onde vão os .xlsx brutos por tipo e os arquivos categorizados."""
        return self.raiz / "Resultados" / "potencialidades"

    @property
    def cidades_rais_ibge(self) -> Path:
        return self._primeiro_existente("cidades-RAIS-IBGE.xlsx")

    @property
    def territorios(self) -> Path:
        return self._primeiro_existente("territorios_desenvolvimento.xlsx")

    @property
    def dicionario_cnae(self) -> Path:
        """Dicionário de subclasses da CNAE 2.0 (código + descrição).

        Vem do dicionário do CAGED/CNAE. Pode ser apontado por
        ``SHIFT_SHARE_DICIONARIO_CNAE``; senão é procurado em
        ``Tabelas-Correlacao/`` e ``Dados/``.
        """
        env = os.environ.get("SHIFT_SHARE_DICIONARIO_CNAE")
        if env:
            return Path(env).expanduser()
        for nome in (
            "dicionario_cnae_subclasse.csv",
            "dicionario_cnae_subclasse.xlsx",
            "dicionário_caged.xlsx",
            "dicionario_caged.xlsx",
        ):
            for pasta in (self.tabelas_correlacao, self.dados):
                candidato = pasta / nome
                if candidato.exists():
                    return candidato
        return self.tabelas_correlacao / "dicionario_cnae_subclasse.csv"

    def _primeiro_existente(self, nome: str) -> Path:
        for pasta in (self.tabelas_correlacao, self.dados):
            candidato = pasta / nome
            if candidato.exists():
                return candidato
        return self.tabelas_correlacao / nome

    # --- caminhos derivados dos arquivos de entrada ------------------------
    def arquivo_rais(self, ano: int, escopo: str) -> Path:
        """``escopo`` é ``municipiosPI`` ou ``regioes``."""
        return self.dados / f"vinculos_{ano}_ClasseCNAE_{escopo}.csv"

    def arquivo_sidra(self, fonte: FonteSidra, ano: int) -> Path:
        return self.dados / f"{fonte.prefixo}_{ano}_municipiosPI.csv"

    def consolidado_rais(self, referencia: str | None = None) -> Path:
        ref = self.referencia if referencia is None else referencia
        return self.saida_shift_share / f"shift-share-consolidado-{ref}.csv"

    def consolidado_sidra(self, fonte: FonteSidra) -> Path:
        return self.saida_shift_share / fonte.saida

    def bruto_por_tipo(self, rotulo: int) -> Path:
        return self.saida_tratamento / (
            f"Shift_share_todos_tipos_{rotulo}_bruto_{self.referencia.lower()}.xlsx"
        )

    def categorizado(self, tipo: str) -> Path:
        alvo = tipo.lower().replace("-", "_")
        return self.saida_tratamento / f"somente_{alvo}_categorizado_{self.ano_t1_rais}.xlsx"

    def com_numeros(self, tipos: tuple[str, ...]) -> Path:
        return self.saida_tratamento / (
            f"potencialidades_com_numeros_{'_'.join(tipos).lower()}_{self.ano_t1_rais}.xlsx"
        )

    def binario(self, tipos: tuple[str, ...]) -> Path:
        return self.saida_tratamento / (
            f"potencialidades_binario_{'_'.join(tipos).lower()}_{self.ano_t1_rais}.xlsx"
        )

    def descricao_territorios(self, tipos: tuple[str, ...]) -> Path:
        return self.saida_tratamento / (
            f"potencialidades_descricao_{'_'.join(tipos).lower()}_{self.ano_t1_rais}.txt"
        )

    def com(self, **alteracoes: Any) -> Config:
        """Cópia da configuração com alguns campos trocados."""
        return replace(self, **alteracoes)

    @classmethod
    def de_arquivo(cls, raiz: Path | str | None = None) -> Config:
        """Lê ``shift-share.toml`` na raiz do projeto, se existir.

        É o que permite versionar os parâmetros do estudo (anos de referência,
        rodadas, pesquisas usadas) junto com os dados, em vez de deixá-los
        espalhados pelo código.
        """
        raiz = raiz_padrao() if raiz is None else Path(raiz).expanduser().resolve()
        arquivo = raiz / ARQUIVO_DE_CONFIGURACAO
        if not arquivo.exists():
            return cls(raiz=raiz)

        with arquivo.open("rb") as conteudo:
            bruto = tomllib.load(conteudo)

        campos: dict[str, Any] = {"raiz": raiz}
        anos = bruto.get("anos", {})
        for nome in ("ano_t1_rais", "ano_t1_sidra"):
            if nome in anos:
                campos[nome] = int(anos[nome])

        if "rodadas" in bruto:
            campos["rodadas"] = tuple(
                Rodada(
                    rotulo=int(rodada["rotulo"]),
                    ano_t0_rais=int(rodada["ano_t0_rais"]),
                    ano_t0_sidra=int(rodada["ano_t0_sidra"]),
                )
                for rodada in bruto["rodadas"]
            )

        dados = bruto.get("dados", {})
        if "referencia" in dados:
            campos["referencia"] = str(dados["referencia"])
        if "linhas_rais" in dados:
            campos["linhas_rais"] = int(dados["linhas_rais"])
        if "casar_subclasse_normalizada" in dados:
            campos["casar_subclasse_normalizada"] = bool(dados["casar_subclasse_normalizada"])
        if "fontes_sidra" in dados:
            pedidas = list(dados["fontes_sidra"])
            por_prefixo = {fonte.prefixo: fonte for fonte in FONTES_SIDRA}
            desconhecidas = [nome for nome in pedidas if nome not in por_prefixo]
            if desconhecidas:
                raise ValueError(
                    f"{ARQUIVO_DE_CONFIGURACAO}: pesquisa(s) desconhecida(s) "
                    f"{desconhecidas}; disponíveis: {sorted(por_prefixo)}"
                )
            campos["fontes_sidra"] = tuple(por_prefixo[nome] for nome in pedidas)

        return cls(**campos)


DEFAULT_CONFIG = Config()
