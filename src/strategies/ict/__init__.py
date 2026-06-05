"""ICT / Smart-Money-Concepts strategy bucket. Importing it registers its strategies."""

from src.strategies.ict import ict_2022  # noqa: F401  (triggers @register_strategy)
from src.strategies.ict import ict_fvg  # noqa: F401  (triggers @register_strategy)
