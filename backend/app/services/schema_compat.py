"""Schema compatibility helpers for incremental rollouts."""

from __future__ import annotations

import logging
from threading import Lock

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_projection_history_lock = Lock()
_projection_history_checked = False


def ensure_projection_history_schema(db: Session) -> None:
    """
    Ensure ``projection_history`` has columns expected by current ORM model.

    This keeps older local DBs working even if an Alembic migration wasn't run yet,
    while remaining safe under parallel request load.
    """
    global _projection_history_checked

    if _projection_history_checked:
        return

    with _projection_history_lock:
        if _projection_history_checked:
            return

        inspector = inspect(db.bind)
        table_names = set(inspector.get_table_names())
        if "projection_history" not in table_names:
            _projection_history_checked = True
            return

        columns = {col["name"] for col in inspector.get_columns("projection_history")}
        if "injury_factor" not in columns:
            db.execute(
                text(
                    "ALTER TABLE projection_history "
                    "ADD COLUMN IF NOT EXISTS injury_factor DOUBLE PRECISION"
                )
            )
            db.commit()
            logger.warning(
                "Added missing projection_history.injury_factor column for schema compatibility"
            )

        _projection_history_checked = True
