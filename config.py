from __future__ import annotations

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class CreateProjectConfig:
    shared_secret: str


def load_config() -> CreateProjectConfig:
    config = CreateProjectConfig(
        shared_secret=os.getenv("CREATE_PROJECT_SHARED_SECRET", "").strip(),
    )
    logger.info("config:", config)
    return config
