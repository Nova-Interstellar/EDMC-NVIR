"""Logger wired into EDMC's logging tree, with a standalone fallback."""

import logging
import os

_plugin_dir = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import appname  # type: ignore

    logger = logging.getLogger(f"{appname}.{_plugin_dir}")

except ImportError:  # running outside EDMC, e.g. a unit test
    logger = logging.getLogger(_plugin_dir)

if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)
