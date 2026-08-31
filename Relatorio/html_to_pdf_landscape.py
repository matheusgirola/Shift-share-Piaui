#!/usr/bin/env python3
"""Converte a cartilha "Mapa de Potencialidades do Piauí" (HTML) um PDF

Requisitos
    pip install playwright
    playwright install chromium   # baixa o navegador, se necessário

Uso:
    python html_to_pdf_landscape.py [entrada.html] [saida.pdf]

"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# --------------------------------------------------------------------------
# Configuração da página impressa
# --------------------------------------------------------------------------
PAGE_FORMAT = "A4"
MARGIN_MM = 10
MM_TO_PX = 96 / 25.4  # 96 px CSS == 1 polegada

PAGE_W_MM, PAGE_H_MM = 297, 210  # A4 paisagem
CONTENT_W_PX = round((PAGE_W_MM - 2 * MARGIN_MM) * MM_TO_PX)
CONTENT_H_PX = round((PAGE_H_MM - 2 * MARGIN_MM) * MM_TO_PX)

DEFAULT_INPUT = Path(__file__).with_name("./cartilha_mapa_potencialidades_piaui_2026_v2.html")
DEFAULT_OUTPUT = Path(__file__).with_name("./cartilha_mapa_potencialidades_piaui_2026_v2.pdf")

# --------------------------------------------------------------------------
# JS injetado no navegador: reagrupa o HTML original nos 5 blocos de página,
# na mesma ordem em que aparecem no documento.
# --------------------------------------------------------------------------
REPAGINATE_JS = """
() => {
  const header = document.querySelector('header.hero');
  const sections = Array.from(document.querySelectorAll('section'));
  const footer = document.querySelector('footer');

  const groups = [
    [header, sections[0]],       // 1. capa + "O instrumento"
    [sections[1]],                // 2. "O critério"
    [sections[2]],                // 3. "Na prática" (exemplo)
    [sections[3]],                // 4. "Três janelas de tempo"
    [sections[4], footer],        // 5. "Mapa online" + rodapé
  ];

  const root = document.createElement('div');
  root.id = 'pdf-root';

  groups.forEach((nodes, idx) => {
    const frame = document.createElement('div');
    frame.className = 'pdf-page';
    if (idx < groups.length - 1) frame.classList.add('pdf-page-break');

    const inner = document.createElement('div');
    inner.className = 'pdf-page-inner';
    nodes.forEach(n => n && inner.appendChild(n));

    frame.appendChild(inner);
    root.appendChild(frame);
  });

  document.body.innerHTML = '';
  document.body.appendChild(root);
}
"""

# CSS de impressão: cada ".pdf-page" tem exatamente o tamanho da área útil
# da folha A4 paisagem (descontadas as margens), com quebra de página
# forçada entre um bloco e outro.
PRINT_CSS_TEMPLATE = """
  html, body { margin:0 !important; padding:0 !important; background:#fff; }
  #pdf-root { width:__CONTENT_W_PX__px; }
  .pdf-page {
    width:__CONTENT_W_PX__px;
    height:__CONTENT_H_PX__px;
    overflow:hidden;
    display:flex;
    align-items:center;
    justify-content:center;
    box-sizing:border-box;
  }
  .pdf-page-break { break-after: page; page-break-after: always; }
  .pdf-page-inner { width:100%; }
  /* o .wrap original tem max-width fixo (pensado p/ tela); em cada página
     do PDF a seção ocupa a folha inteira, então liberamos a largura */
  .wrap { max-width: 100% !important; }
  section { padding: 32px 0 !important; }
  header.hero { padding: 28px 0 40px !important; }
  footer { padding: 24px 0 !important; }
"""

# Reduz a escala (zoom) de cada bloco até caber inteiro na altura da
# página, sem cortar nenhum conteúdo.
FIT_TO_PAGE_JS_TEMPLATE = """
() => {
  document.querySelectorAll('.pdf-page').forEach(frame => {
    const inner = frame.querySelector('.pdf-page-inner');
    inner.style.zoom = 1;
    const targetH = __CONTENT_H_PX__;
    const naturalH = inner.scrollHeight;
    if (naturalH > targetH) {
      inner.style.zoom = targetH / naturalH;
    }
  });
}
"""


def _launch_kwargs() -> dict:
    kwargs: dict = {"headless": True}

    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy_url:
        kwargs["proxy"] = {"server": proxy_url}

    exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if exe:
        kwargs["executable_path"] = exe

    return kwargs


def convert(input_html: Path, output_pdf: Path) -> None:
    input_url = input_html.resolve().as_uri()

    print_css = PRINT_CSS_TEMPLATE.replace("__CONTENT_W_PX__", str(CONTENT_W_PX)).replace(
        "__CONTENT_H_PX__", str(CONTENT_H_PX)
    )
    fit_js = FIT_TO_PAGE_JS_TEMPLATE.replace("__CONTENT_H_PX__", str(CONTENT_H_PX))

    with sync_playwright() as p:
        browser = p.chromium.launch(**_launch_kwargs())
        try:
            page = browser.new_page(viewport={"width": CONTENT_W_PX, "height": 1600})
            page.goto(input_url, wait_until="load", timeout=45000)

            page.add_style_tag(content=print_css)
            page.evaluate(REPAGINATE_JS)
            page.evaluate(fit_js)

            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            page.pdf(
                path=str(output_pdf),
                format=PAGE_FORMAT,
                landscape=True,
                print_background=True,
                margin={
                    "top": f"{MARGIN_MM}mm",
                    "bottom": f"{MARGIN_MM}mm",
                    "left": f"{MARGIN_MM}mm",
                    "right": f"{MARGIN_MM}mm",
                },
            )
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        default=str(DEFAULT_INPUT),
        help="Caminho do HTML de entrada (cartilha)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(DEFAULT_OUTPUT),
        help="Caminho do PDF de saída",
    )
    args = parser.parse_args()

    input_html = Path(args.input)
    if not input_html.exists():
        sys.exit(f"Arquivo não encontrado: {input_html}")

    output_pdf = Path(args.output)
    convert(input_html, output_pdf)
    print(f"PDF gerado com sucesso: {output_pdf.resolve()}")


if __name__ == "__main__":
    main()
