# Shift-share do Piauí

Pipeline reprodutível de shift-share municipal e de mapeamento das
potencialidades produtivas do Piauí de 2026.

## Como rodar

O pipelçine roda com apenas um comando

Pré-requisito: [uv](https://docs.astral.sh/uv/).

```bash
uv sync --group dev      # cria o ambiente e instala as dependências
uv run ssp-shift-share tudo
```

As etapas também rodam isoladamente:

```bash
uv run ssp-shift-share sidra            # shift-share das pesquisas do IBGE
uv run ssp-shift-share rais             # shift-share dos vínculos da RAIS
uv run ssp-shift-share tratamento       # consolida por tipo de região
uv run ssp-shift-share potencialidades --tipos T1 T2
```

Os testes:

```bash
uv run pytest
```

## As quatro etapas

| Etapa | Entra | Sai | Vinha de |
| --- | --- | --- | --- |
| `sidra` | `Dados/PAM_*`, `PEVS_*`, `PPM_*` | `Resultados/shift-share/shift-share-consolidado_*.csv` | `shift_share_ppm_todos_municipios.R` |
| `rais` | `Dados/vinculos_*` | `Resultados/shift-share/shift-share-consolidado-{Piauí,Nordeste,Brasil}.csv` | `shift_share_vinculosRAIS.R` |
| `tratamento` | os CSVs acima | `Resultados/potencialidades/Shift_share_todos_tipos_{ano}_bruto_brasil.xlsx` | notebook, 1ª metade |
| `potencialidades` | os `.xlsx` acima | `somente_t1_categorizado_*.xlsx`, `potencialidades_binario_*.xlsx`, `Subclasses_dummy/`, descrição por território | notebook, 2ª metade |

`tratamento` grava uma aba por tipo de região (T1 a T8 e T-1).
`potencialidades` recorta os tipos pedidos: `--tipos T1` reproduz o recorte do
relatório, e `--tipos T1 T2` é o do Mapa de Potencialidades físico.

## Configuração

Todos os parâmetros do estudo estão em [`shift-share.toml`](shift-share.toml):
anos de referência, o pareamento de anos de cada rodada e quais pesquisas do
IBGE existem em `Dados/`. Nenhum ano ou caminho está escrito no código.

Duas variáveis de ambiente ajudam a rodar sobre outra cópia dos dados:

- `SHIFT_SHARE_PIAUI_ROOT` — raiz do projeto (o mesmo que `--raiz`);
- `SHIFT_SHARE_DICIONARIO_CNAE` — caminho do dicionário da CNAE 2.0.

Todas as entradas necessárias estão no repositório: `Dados/` (extratos do
BGCAGED e do SIDRA), `Dados/cidades-RAIS-IBGE.xlsx`,
`Dados/territorios_desenvolvimento.xlsx` e
`Tabelas-Correlacao/dicionario_caged.xlsx`. Não há nada a baixar.

## Dicionário da CNAE 2.0

`Tabelas-Correlacao/dicionario_caged.xlsx` é o dicionário do Novo CAGED, e a
aba `subclasse` traz o par código/descrição de 1357 subclasses. É a única
entrada que não vem do IBGE nem da RAIS.

O código é usado em dois pontos: para tirar da RAIS a agropecuária, o comércio
e a administração pública e para agrupar cada subclasse em uma potencialidade pela faixa da CNAE.

### Rótulos que não casam exatamente

O extrato da RAIS e o dicionário escrevem a mesma subclasse de formas um pouco
diferentes — "gás liqüefeito" contra "gás liquefeito", "Defesa Civil" contra
"Defesa civil", um espaço não separável no meio de "Atividades de franqueadas".
O casamento exato deixava **61 das 1363 subclasses sem código** e elas podem ser
descartadas sem aviso.

O pipeline reencontra esses rótulos comparando a forma normalizada
(sem acento, sem caixa, espaçamento colapsado), e só quando ela aponta para um
único código. Isso recupera 39 das 61. As 22 restantes (subclasses desativadas ausentes do dicionário, mais as linhas de
controle `Invalida`, `Ignorada`, `{ñ class}`) continuam de fora, com um
aviso dizendo quantas são e quais.

## Estrutura

```
src/shift_share_piaui/
    config.py           parâmetros, caminhos e leitura do shift-share.toml
    r_compat.py         make.names() do R e o formato de CSV que ele gravava
    leitura.py          extratos brutos da RAIS (BGCAGED) e do SIDRA
    shift_share.py      decomposição de Montañia & Márquez e a tipologia
    pipeline_rais.py    etapa `rais`
    pipeline_sidra.py   etapa `sidra`
    tratamento.py       etapa `tratamento`
    potencialidades.py  etapa `potencialidades`
    cli.py              linha de comando
tests/                  143 testes; nenhum depende dos dados reais, exceto
                        test_regressao_r.py, que é pulado se eles faltarem
```

## Método

Utilizamos a decomposição shift-share de Montania et al. (2024). Para cada município `r`, setor `i` e par de anos, sendo `G` o crescimento da
referência de comparação, `g` o do município, `Gi` o do setor na referência e
`gi` o do setor no município:

```
NE   = G  * E0          efeito nacional
IM   = (Gi - G) * E0    efeito estrutural (mix industrial)
CE   = (gi - Gi) * E0   efeito competitivo
RIE  = (gi - g)  * E0   efeito diferencial intrarregional
RSE  = (g  - G)  * E0   efeito regional
RCCE = (G  - gi) * E0   efeito cruzado, que fecha a identidade
```

O tipo da região sai dos sinais de `(CE, RIE, RSE)`: `(+,+,+)` é T1, `(+,+,-)` é
T2, e assim por diante até T8. Setores em que algum efeito é exatamente zero, ou
que nascem do zero (crescimento indefinido), ficam em `T-1`.

O shift-share é calculado contra três referências — Piauí, Nordeste e Brasil —
e cada uma vai para um arquivo próprio. O tratamento para o mapa usa só a comparação
nacional.

## Reprodutibilidade

O ambiente é fixado por `pyproject.toml` e `uv.lock`; `uv sync` reconstrói as
versões exatas. Os resultados intermediários (`Resultados/`) ficam fora do
controle de versão — são cerca de 420 MB — e são regerados por
`uv run ssp-shift-share tudo` em pouco mais de um minuto.
