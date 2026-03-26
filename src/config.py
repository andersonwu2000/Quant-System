# Backward compat — re-export from new location
from src.core.config import *  # noqa: F401,F403
from src.core.config import get_config, override_config, TradingConfig  # noqa: F401
