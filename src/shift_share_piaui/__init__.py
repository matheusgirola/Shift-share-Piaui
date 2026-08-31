"""Pipeline reprodutível de shift-share e potencialidades produtivas do Piauí.

O pacote reúne, em Python, as duas metades que antes viviam separadas:

* ``Economia-Regional-R/*.R`` -> :mod:`shift_share_piaui.pipeline_rais` e
  :mod:`shift_share_piaui.pipeline_sidra` (cálculo do shift-share);
* ``python/Potencialidades-*.ipynb`` -> :mod:`shift_share_piaui.tratamento` e
  :mod:`shift_share_piaui.potencialidades` (tratamento e categorização).
"""

from shift_share_piaui.config import DEFAULT_CONFIG, Config

__all__ = ["DEFAULT_CONFIG", "Config"]
__version__ = "0.1.0"
