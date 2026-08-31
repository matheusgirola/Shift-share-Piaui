"""A linha de comando: cada subcomando roda a etapa certa no projeto certo."""

from __future__ import annotations

import pandas as pd
import pytest

from shift_share_piaui.cli import construir_parser, main
from shift_share_piaui.config import Config


def test_subcomando_desconhecido_falha():
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["inventado"])


def test_tipo_invalido_e_recusado():
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["potencialidades", "--tipos", "T99"])


def test_sidra_pela_linha_de_comando(projeto: Config, capsys):
    assert main(["--raiz", str(projeto.raiz), "--silencioso", "sidra"]) == 0
    assert projeto.consolidado_sidra(projeto.fontes_sidra[0]).exists()
    assert "shift-share-consolidado_ppm" in capsys.readouterr().out


def test_rais_pela_linha_de_comando(projeto: Config):
    assert main(["--raiz", str(projeto.raiz), "--silencioso", "rais"]) == 0
    assert projeto.consolidado_rais("Brasil").exists()


def test_pipeline_completo_pela_linha_de_comando(projeto: Config):
    assert main(["--raiz", str(projeto.raiz), "--silencioso", "tudo"]) == 0

    assert projeto.bruto_por_tipo(2013).exists()
    categorizado = pd.read_excel(projeto.categorizado("T1"))
    assert "Potencialidade" in categorizado.columns
    assert projeto.binario(("T1", "T2")).exists()


def test_raiz_aponta_para_outro_projeto(projeto: Config, tmp_path):
    # Sem --raiz o pipeline usaria o repositório instalado; com ela, escreve
    # apenas dentro do projeto indicado.
    main(["--raiz", str(projeto.raiz), "--silencioso", "sidra"])
    assert (projeto.raiz / "Resultados").exists()


def test_configuracao_vem_do_arquivo_do_projeto(projeto: Config):
    from shift_share_piaui.config import Config as ConfigDeArquivo

    lida = ConfigDeArquivo.de_arquivo(projeto.raiz)

    assert lida.ano_t1_rais == 2020
    assert lida.ano_t1_sidra == 2021
    assert lida.linhas_rais == len(["Extração de carvão mineral", "Fabricação de biscoitos"])
    assert [fonte.prefixo for fonte in lida.fontes_sidra] == ["PPM_Efetivo_rebanhos"]
    assert [rodada.rotulo for rodada in lida.rodadas] == [2013]


def test_pesquisa_desconhecida_no_arquivo_de_configuracao(projeto: Config):
    from shift_share_piaui.config import Config as ConfigDeArquivo

    (projeto.raiz / "shift-share.toml").write_text(
        '[dados]\nfontes_sidra = ["PESQUISA_QUE_NAO_EXISTE"]\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="desconhecida"):
        ConfigDeArquivo.de_arquivo(projeto.raiz)


def test_projeto_sem_arquivo_de_configuracao_usa_os_padroes(tmp_path):
    from shift_share_piaui.config import Config as ConfigDeArquivo

    padrao = ConfigDeArquivo.de_arquivo(tmp_path)
    assert padrao.raiz == tmp_path
    assert padrao.ano_t1_rais == 2025
