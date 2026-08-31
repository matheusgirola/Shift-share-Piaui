"""O ``make.names()`` do R é o que dá nome aos setores no pipeline inteiro."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from shift_share_piaui.r_compat import escrever_csv_r, ler_csv_r, make_names


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        # Casos reais dos extratos, conferidos contra o que o R produz.
        ("Município", "Município"),
        ("Suíno - total", "Suíno...total"),
        ("Galináceos - total", "Galináceos...total"),
        ("Arroz (em casca)", "Arroz..em.casca."),
        ("Coco-da-baía*", "Coco.da.baía."),
        ("Carnaúba - pó", "Carnaúba...pó"),
        ("CNAE 2.0 Subclasse", "CNAE.2.0.Subclasse"),
        ("PI-BARRA D ALCANTARA", "PI.BARRA.D.ALCANTARA"),
        ("Centro-Oeste", "Centro.Oeste"),
        # Prefixo X: nome que começa por dígito, ou por ponto seguido de dígito.
        ("1 - Alimentícios", "X1...Alimentícios"),
        ("1.2 - Castanha-de-caju", "X1.2...Castanha.de.caju"),
        ("_interno", "X_interno"),
        ("", "X"),
        # Palavra reservada do R ganha ponto no fim.
        ("if", "if."),
    ],
)
def test_make_names_reproduz_o_r(entrada: str, esperado: str):
    assert make_names([entrada]) == [esperado]


def test_make_names_desambigua_repeticoes():
    # É o que o read.csv() do R faz com check.names=TRUE.
    assert make_names(["Outros", "Outros", "Outros"]) == [
        "Outros",
        "Outros.1",
        "Outros.2",
    ]


def test_make_names_sem_unique_mantem_repeticoes():
    assert make_names(["Outros", "Outros"], unique=False) == ["Outros", "Outros"]


def test_csv_no_formato_do_r_faz_ida_e_volta(tmp_path: Path):
    original = pd.DataFrame(
        {
            "NM_MUN_RAIS": ["PI.ACAUA", "PI.BOM.JESUS"],
            "CE": [1234.5, -0.25],
            "classificacao_regiao": ["T1", "T-1"],
        }
    )
    caminho = escrever_csv_r(original, tmp_path / "consolidado.csv")

    bruto = caminho.read_text(encoding="latin-1")
    assert ";" in bruto
    assert "1234,5" in bruto  # vírgula decimal, como no write.table do R
    assert '"NM_MUN_RAIS"' in bruto  # cabeçalho entre aspas

    pd.testing.assert_frame_equal(ler_csv_r(caminho), original)


def test_csv_no_formato_do_r_preserva_ausentes(tmp_path: Path):
    # Setores que entram do zero têm VarTot indefinido; o valor precisa voltar
    # como ausente, e não como texto ou zero.
    caminho = escrever_csv_r(pd.DataFrame({"VarTot": [float("nan"), 1.5]}), tmp_path / "vazio.csv")
    lido = ler_csv_r(caminho)
    assert lido["VarTot"].isna().tolist() == [True, False]
    assert lido["VarTot"].iloc[1] == 1.5
