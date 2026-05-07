from __future__ import annotations

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class GisquickQgisServerProcessingConfig:
    shared_secret: str


def load_config() -> GisquickQgisServerProcessingConfig:
    config = GisquickQgisServerProcessingConfig(
        shared_secret=os.getenv("GISQUICK_QGIS_SERVER_PROCESSING_SHARED_SECRET", "").strip(),
    )
    logger.info("config:", config)
    return config
