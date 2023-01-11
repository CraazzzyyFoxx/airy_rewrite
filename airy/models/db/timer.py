from __future__ import annotations

import datetime
import enum
import json
import typing

import attr
import hikari

from asyncpg import Record  # type: ignore

from airy.models.db.impl import DatabaseModel
from airy.utils.time import utcnow


class TimerEnum(enum.IntEnum):
    NONE = 0
    REMINDER = 1
    MUTE = 2


@attr.define(kw_only=True)
class DatabaseTimer(DatabaseModel):
    id: int
    """The ID of this timer."""

    guild_id: hikari.Snowflake
    """The guild this timer is bound to."""

    user_id: hikari.Snowflake
    """The user this timer is bound to."""

    channel_id: hikari.Snowflake
    """The channel this timer is bound to."""

    expires: datetime.datetime
    """The expiry date of this timer as a UNIX timestamp."""

    created: datetime.datetime

    event: TimerEnum
    """The event type of this timer."""

    extra: dict[str, typing.Any]
    """Optional data for this timer. May be a JSON-serialized string depending on the event type."""

    @classmethod
    def _parse_record(cls, record: Record):
        return DatabaseTimer(id=record.get("id"),
                             guild_id=hikari.Snowflake(record.get("guild_id")),
                             user_id=hikari.Snowflake(record.get("user_id")),
                             channel_id=hikari.Snowflake(record.get("channel_id"))
                             if record.get("channel_id") else None,
                             expires=record.get("expires"),
                             created=record.get("created"),
                             event=TimerEnum(record.get("event")),
                             extra=json.loads(record.get("extra")))

    @classmethod
    async def create(cls,
                     guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                     user: hikari.SnowflakeishOr[hikari.PartialUser],
                     expires: datetime.datetime,
                     created: datetime.datetime,
                     event: TimerEnum,
                     *,
                     channel: typing.Optional[hikari.SnowflakeishOr[hikari.PartialChannel]] = None,
                     extra: dict = None):
        channel_id = hikari.Snowflake(channel) if channel else None
        record = await cls.db.fetchval("""insert into timer (guild_id, user_id, channel_id, expires, 
                                                                created, event, extra) 
                                            values ($1, $2, $3, $4, $5, $6, $7)
                                            returning id""",
                                       hikari.Snowflake(guild),
                                       hikari.Snowflake(user),
                                       channel_id,
                                       expires,
                                       created,
                                       event,
                                       json.dumps(extra))

        return DatabaseTimer(id=int(record),
                             guild_id=hikari.Snowflake(guild),
                             user_id=hikari.Snowflake(user),
                             channel_id=channel_id,
                             expires=expires,
                             created=created,
                             event=event,
                             extra=extra
                             )

    async def update(self):
        await self.db.execute("""insert into timer (id, guild_id, user_id, channel_id, expires, created, event, extra) 
                                            values ($1, $2, $3, $4, $5, $6, $7, $8)
                                    on conflict (id, created) DO 
                                    UPDATE SET expires=$5, extra=$8""",
                              self.id,
                              self.guild_id,
                              self.user_id,
                              self.channel_id,
                              self.expires,
                              self.created,
                              self.event,
                              json.dumps(self.extra)
                              )

    async def delete(self):
        await self.db.execute("""delete from timer where id=$1 and created=$2""",
                              self.id,
                              self.created)

    @classmethod
    async def fetch(cls, timer_id: int):
        record = await cls.db.fetchrow("""select * from timer where id=$1""",
                                       timer_id)
        if not record:
            return None

        return cls._parse_record(record)

    @classmethod
    async def fetch_first(cls, days: int = 7):
        record = await cls.db.fetchrow("""select * from timer where expires <= $1""",
                                       utcnow() + datetime.timedelta(days=days))
        if not record:
            return None

        return cls._parse_record(record)

    @classmethod
    async def fetch_all(cls, user: hikari.SnowflakeishOr[hikari.PartialUser], limit: int = 10):
        records = await cls.db.fetch("""select * from timer where extra #> '{kwargs, user_id}' = $1 limit $2""",
                                     hikari.Snowflake(user),
                                     limit)

        return [cls._parse_record(record) for record in records]
