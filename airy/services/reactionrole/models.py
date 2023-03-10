from __future__ import annotations

import enum
import typing

import hikari

from pydantic import BaseModel, validator
from asyncpg import Record  # type:  ignore
from cashews import Cache  # type:  ignore

from airy.models.db.impl import DatabaseModel

__all__ = ("DatabaseReactionRole", "DatabaseReactionRoleEntry", "ReactionRoleType")

cache = Cache()
cache.setup("mem://?size=1000", prefix="reaction_role")

_insert_base_sql = """insert into reactionrole 
                       (guild_id, channel_id, message_id, type, max) 
                       VALUES ($1, $2, $3, $4, $5) returning id"""

_insert_entry_base_sql = """insert into reactionrole_entry (id, role_id, emoji) VALUES ($1, $2, $3)"""


class ReactionRoleType(enum.IntEnum):
    NORMAL = 0
    """Hands out roles when you click on them, does what you'd expect"""
    UNIQUE = 1
    """Only lets one role from the message be picked up at once"""
    VERIFY = 2
    """Roles can only be picked up, not removed"""
    DROP = 3
    """Roles can only be removed, not picked up"""
    REVERSED = 4
    """Adding a reaction removes the role, removing the reaction adds a role"""
    # BINDING = 5
    # """You can only choose one role and you can not swap between roles"""


class DatabaseReactionRoleEntry(BaseModel, DatabaseModel):
    id: int
    role_id: hikari.Snowflake
    emoji: hikari.Emoji

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def serialize(cls, record: Record):
        return DatabaseReactionRoleEntry(id=record.get("entry_id"),
                                         role_id=hikari.Snowflake(record.get("role_id")),
                                         emoji=hikari.Emoji.parse(record.get("emoji"))
                                         )


class DatabaseReactionRole(BaseModel, DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    channel_id: hikari.Snowflake
    message_id: hikari.Snowflake
    type: ReactionRoleType
    max: int

    entries: list[DatabaseReactionRoleEntry] = []

    @classmethod
    def serialize(cls, record: Record, entries: typing.Optional[list[DatabaseReactionRoleEntry]] = None):
        return DatabaseReactionRole(**record, entries=entries if entries else [])

    def get_role_by_emoji(self, emoji: hikari.Emoji) -> hikari.Snowflake | None:
        for entry in self.entries:
            if entry.emoji == emoji:
                return entry.role_id

        return None

    @classmethod
    async def create(
            cls,
            guild: hikari.Snowflake,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role_type: ReactionRoleType,
            max_roles: int,
            roles: list[hikari.Snowflake],
            emojis: list[hikari.Emoji],
    ) -> DatabaseReactionRole:
        model_id = await DatabaseReactionRole.db.fetchval(_insert_base_sql, guild, channel, message, role_type, max_roles)

        entries = []

        for role, emoji in zip(roles, emojis):
            await DatabaseReactionRole.db.execute(_insert_entry_base_sql, model_id, role, emoji.mention)
            entries.append(DatabaseReactionRoleEntry(id=model_id, role_id=role, emoji=emoji))

        await cache.delete(key=f"reaction_role:{channel}:{message}")

        return DatabaseReactionRole(id=model_id,
                                    guild_id=guild,
                                    channel_id=channel,
                                    message_id=message,
                                    type=role_type,
                                    max=max_roles,
                                    entries=entries
                                    )

    async def save(
            self
    ) -> None:

        sql = """insert into reactionrole 
                       (guild_id, channel_id, message_id, type, max) 
                       VALUES ($1, $2, $3, $4, $5) ON CONFLICT 
                       (guild_id, channel_id, message_id) DO UPDATE SET type=$4, max=$5"""

        await DatabaseReactionRole.db.execute(sql,
                                              self.guild_id, self.channel_id, self.message_id, self.type, self.max)

        await cache.delete(key=f"reaction_role:{self.channel_id}:{self.message_id}")

    async def delete(
            self
    ) -> None:

        sql = """delete from reactionrole where channel_id=$1 and message_id=$2"""
        await DatabaseReactionRole.db.execute(sql, self.channel_id, self.message_id)

        await cache.delete(key=f"reaction_role:{self.channel_id}:{self.message_id}")

    async def add_entries(
            self,
            entries: list[DatabaseReactionRoleEntry]
    ) -> None:

        sql = """insert into reactionrole_entry (id, role_id, emoji) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING"""
        await self.db.executemany(sql, [(entry.id, entry.role_id, entry.emoji.mention) for entry in entries])
        self.entries.extend(entries)
        await cache.delete(key=f"reaction_role:{self.channel_id}:{self.message_id}")

    async def remove_entries(
            self,
            entries: list[DatabaseReactionRoleEntry]
    ) -> None:

        sql = """delete from reactionrole_entry where id=$1 and role_id=$2 and emoji=$3"""
        await self.db.executemany(sql, [(entry.id, entry.role_id, entry.emoji.mention) for entry in entries])

        self.entries = list(set(self.entries.copy()) - set(entries))

        if not self.entries:
            await self.delete()

        await cache.delete(key=f"reaction_role:{self.channel_id}:{self.message_id}")

    @classmethod
    async def delete_all_by_role(
            cls,
            guild: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> None:

        models = await cls.fetch_by_role(guild, role)

        for model in models:
            await model.remove_entries([entry for entry in model.entries if entry.role_id == role])

    @classmethod
    @cache(ttl="24h", key="reaction_role:{channel}:{message}")
    async def fetch(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
    ) -> DatabaseReactionRole | None:

        sql = """select rr.*, re.id as entry_id, re.role_id, re.emoji from reactionrole rr 
                                left join reactionrole_entry re on rr.id = re.id 
                                where rr.channel_id=$1 and message_id=$2"""

        records = await DatabaseReactionRole.db.fetch(sql, channel, message)
        if not records:
            return None
        entries = [DatabaseReactionRoleEntry.serialize(record) for record in records]
        model = cls.serialize(records[0], entries)

        return model

    @classmethod
    async def fetch_by_role(
            cls,
            guild: hikari.Snowflake,
            role: hikari.Snowflake
    ) -> list[DatabaseReactionRole]:

        select_sql = """select rr.*, re.id as entry_id, re.role_id, re.emoji from reactionrole as rr 
                                    left join reactionrole_entry as  re on rr.id = re.id 
                                    where rr.guild_id=$1 and re.role_id=$2"""

        records = await DatabaseReactionRole.db.fetch(select_sql, guild, role)

        parsed_records: dict[hikari.Snowflake, list[Record]] = {}

        for record in records:
            message_id = record.get("message_id")
            if not parsed_records.get(message_id):
                parsed_records[message_id] = [record]
            else:
                parsed_records[message_id].append(record)

        models: list[DatabaseReactionRole] = []

        for records in parsed_records.values():
            entries: list[DatabaseReactionRoleEntry] = []
            for record in records:
                entries.append(DatabaseReactionRoleEntry.serialize(record))

            model = DatabaseReactionRole.serialize(records[0], entries)

            models.append(model)

        return models

    @classmethod
    @cache(ttl="24h", key="reaction_role:{guild}")
    async def fetch_all(
            cls,
            guild: hikari.Snowflake
    ) -> list[DatabaseReactionRole]:

        sql = """select channel_id, message_id from reactionrole where guild_id=$1"""

        records = await DatabaseReactionRole.db.fetch(sql, guild)
        if not records:
            return []

        models = [await cls.fetch(record.get("channel_id"), record.get("message_id")) for record in records]
        return models
