from __future__ import annotations

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class GisquickProjectFromFileConfig:
    shared_secret: str


def load_config() -> GisquickProjectFromFileConfig:
    config = GisquickProjectFromFileConfig(
        shared_secret=os.getenv("GISQUICK_PROJECT_FROM_FILE_SHARED_SECRET", "").strip(),
    )
    logger.info("config:", config)
    return config
