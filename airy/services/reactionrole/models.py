from __future__ import annotations

import attr
import hikari
from asyncpg import Record  # type:  ignore

from airy.models import RoleDoesNotExist, RoleAlreadyExists
from airy.models.db.impl import DatabaseModel

__all__ = ("DatabaseReactionRole",)


_insert_base_sql = """insert into reactionrole 
                       (guild_id, channel_id, message_id, role_id, emoji) 
                       VALUES ($1, $2, $3, $4, $5)"""


@attr.define()
class DatabaseReactionRole(DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    channel_id: hikari.Snowflake
    message_id: hikari.Snowflake
    role_id: hikari.Snowflake
    emoji: hikari.Emoji

    @classmethod
    def _parse_record(cls, record: Record):
        return DatabaseReactionRole(id=record.get("id"),
                                    guild_id=hikari.Snowflake(record.get("guild_id")),
                                    channel_id=hikari.Snowflake(record.get("channel_id")),
                                    message_id=hikari.Snowflake(record.get("message_id")),
                                    role_id=hikari.Snowflake(record.get("role_id")),
                                    emoji=hikari.Emoji.parse(record.get("emoji"))
                                    )

    @classmethod
    async def create(
            cls,
            guild: hikari.Snowflake,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
            emoji: hikari.Emoji
    ) -> DatabaseReactionRole:

        sql = """select * from reactionrole where channel_id=$1 and message_id=$2 and role_id=$3"""
        record = await DatabaseReactionRole.db.fetchrow(sql, channel, message, role)

        if record:
            raise RoleAlreadyExists()

        model_id = await DatabaseReactionRole.db.fetchval(_insert_base_sql, guild, channel, message, role,
                                                          emoji.mention)

        return DatabaseReactionRole(id=model_id,
                                    guild_id=guild,
                                    channel_id=channel,
                                    message_id=message,
                                    role_id=role,
                                    emoji=emoji
                                    )

    async def edit(self, emoji: hikari.Emoji):
        """

        :param emoji:
        """

        sql = (_insert_base_sql +
               """ON CONFLICT (guild_id, channel_id, message_id, role_id) DO UPDATE SET emoji=$6""")

        await DatabaseReactionRole.db.execute(sql, self.guild_id, self.channel_id, self.message_id, self.role_id,
                                              emoji.mention)
        self.emoji = emoji

    async def delete(self) -> DatabaseReactionRole:

        sql = """select * from reactionrole where channel_id=$1 and message_id=$2 and role_id=$3"""
        record = await DatabaseReactionRole.db.fetchrow(sql, self.channel_id, self.message_id, self.role_id)

        if not record:
            raise RoleDoesNotExist()

        sql = """delete from reactionrole where channel_id=$1 and message_id=$2 and role_id=$3"""
        await DatabaseReactionRole.db.execute(sql, self.channel_id, self.message_id, self.role_id)

        return self._parse_record(record)

    @classmethod
    async def delete_all(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
    ) -> list[DatabaseReactionRole]:
        models = await cls.fetch_all(channel, message)

        if not models:
            raise RoleDoesNotExist()

        sql = """delete from reactionrole where channel_id=$1 and message_id=$2"""

        await DatabaseReactionRole.db.execute(sql, channel, message)

        return models

    @classmethod
    async def delete_all_by_role(
            cls,
            guild: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> list[DatabaseReactionRole]:
        select_sql = """select * from reactionrole where guild_id=$1 and role_id=$2"""
        records = await DatabaseReactionRole.db.fetch(select_sql, guild, role)

        if not records:
            raise RoleDoesNotExist()

        delete_sql = """delete from reactionrole where guild_id=$1 and role_id=$2"""
        await DatabaseReactionRole.db.execute(delete_sql, guild, role)

        return [cls._parse_record(record) for record in records]

    @classmethod
    async def fetch(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> DatabaseReactionRole:
        sql = """select * from reactionrole where channel_id=$1 and message_id=$2 and role_id=$3"""
        record = await DatabaseReactionRole.db.fetchrow(sql, channel, message, role)

        if not record:
            raise RoleDoesNotExist()

        return cls._parse_record(record)

    @classmethod
    async def fetch_by_emoji(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            emoji: hikari.Emoji,
    ) -> DatabaseReactionRole | None:
        sql = """select * from reactionrole where channel_id=$1 and message_id=$2 and emoji=$3"""
        record = await DatabaseReactionRole.db.fetchrow(sql, channel, message, emoji.mention)

        if not record:
            raise RoleDoesNotExist()

        return cls._parse_record(record)

    @classmethod
    async def fetch_all(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake
    ) -> list[DatabaseReactionRole]:
        sql = """select * from reactionrole where channel_id=$1 and message_id=$2"""
        records = await DatabaseReactionRole.db.fetch(sql, channel, message)

        return [cls._parse_record(record) for record in records]
