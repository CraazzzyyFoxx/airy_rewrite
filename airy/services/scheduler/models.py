from __future__ import annotations

import datetime
import enum
import typing

import hikari

from tortoise import Model, fields


class TimerEnum(enum.IntEnum):
    NONE = 0
    REMINDER = 1
    MUTE = 2


class DatabaseTimer(Model):
    id: int = fields.IntField(pk=True)
    """The ID of this timer."""

    guild_id: hikari.Snowflake = fields.BigIntField()
    """The guild this timer is bound to."""

    user_id: hikari.Snowflake | None = fields.BigIntField(default=None)
    """The user this timer is bound to."""

    channel_id: hikari.Snowflake | None = fields.BigIntField(default=None)
    """The channel this timer is bound to."""

    expires: datetime.datetime = fields.DatetimeField()
    """The expiry date of this timer as a UNIX timestamp."""

    created: datetime.datetime = fields.DatetimeField()

    event: TimerEnum = fields.IntEnumField(TimerEnum)
    """The event type of this timer."""

    extra: dict[str, typing.Any] = fields.JSONField()
    """Optional data for this timer. May be a JSON-serialized string depending on the event type."""

    class Meta:
        """Metaclass to set table name and description"""

        table = "timer"