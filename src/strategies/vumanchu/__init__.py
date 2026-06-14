"""VuManChu (VMC) strategy bucket — Cipher B / WaveTrend setups, the way crypto traders use them.

Importing this package registers the strategies with the global registry.
"""

from src.strategies.vumanchu.cipher_strategy import VmcCipher
from src.strategies.vumanchu.wolfpack_mtf import VmcWolfpack

__all__ = ["VmcCipher", "VmcWolfpack"]
