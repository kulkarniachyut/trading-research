"""Strategy layer. Importing this package imports every bucket, so all strategies self-register
via ``@register_strategy`` and become discoverable through ``base.STRATEGY_REGISTRY``.

Buckets (folders): ``ict`` (ICT/SMC), then ``divergence`` (VuManChu), and later momentum /
mean-reversion / event. Add a strategy = drop a file in a bucket and decorate it.
"""

from src.strategies import ict  # noqa: F401

__all__ = ["ict"]
