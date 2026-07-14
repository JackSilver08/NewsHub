"""Shared API dependencies.

For the single-user MVP the current user is the seeded local user. Authentication
is a later phase (plan section 17, phase 4).
"""

from __future__ import annotations

from app.db.init_db import DEFAULT_USER_ID


def get_current_user_id() -> str:
    return DEFAULT_USER_ID
