from __future__ import annotations

import typing

import attr
import hikari
import miru

from asyncpg import Record  # type: ignore

from airy.models.db.impl import DatabaseModel
from airy.utils import cache


@attr.define()
class DatabaseAutoRoom(DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    channel_id: typing.Optional[hikari.Snowflake]

    max_members: int
    default_permissions: hikari.Permissions

    buttons: typing.List[DatabaseAutoRoomButton] = attr.Factory(list)


@attr.define()
class DatabaseAutoRoomButton(DatabaseModel):
    id: int
    style: int
    label: str
    url: str
    row: int
    emoji: hikari.Emoji

    action: DataBaseAutoRoomButtonAction


@attr.define()
class DataBaseAutoRoomButtonAction(DatabaseModel):
    id: int



