"""Schema compatibility helpers for incremental rollouts."""

from __future__ import annotations

import logging
from threading import Lock

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_projection_history_lock = Lock()
_projection_history_checked = False


def ensure_projection_history_schema(db: Session) -> None:
    """
    Ensure ``projection_history`` has columns expected by current ORM model.

    Uses PostgreSQL ``ADD COLUMN IF NOT EXISTS`` so this remains safe under
    parallel requests and mixed rollout environments.
    """
    global _projection_history_checked

    if _projection_history_checked:
        return

    with _projection_history_lock:
        if _projection_history_checked:
            return

        db.execute(
            text(
                "ALTER TABLE projection_history "
                "ADD COLUMN IF NOT EXISTS injury_factor DOUBLE PRECISION"
            )
        )
        db.commit()
        _projection_history_checked = True
        logger.info("Schema compatibility check complete for projection_history")
