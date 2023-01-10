from __future__ import annotations

import typing
import typing as t
from enum import IntEnum

import attr
import hikari

from airy.models.db.impl import DatabaseModel

__all__ = ("DatabaseReactionRole", )


@attr.define()
class DatabaseReactionRole(DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    channel_id: hikari.Snowflake
    message_id: hikari.Snowflake
    role_id: hikari.Snowflake
    emoji: hikari.Emoji
