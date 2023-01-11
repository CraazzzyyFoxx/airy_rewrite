from __future__ import annotations

import attr
import hikari
from asyncpg import Record  # type:  ignore

from airy.models.db.impl import DatabaseModel
from airy.utils import cache

__all__ = ("DatabaseReactionRole",)


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
    ) -> DatabaseReactionRole | None:

        model: DatabaseReactionRole = await cls.fetch(guild, channel, message, role)

        if model:
            raise ValueError("This role already exists. ")

        model_id = await DatabaseReactionRole.db.fetchval("""insert into reactionrole 
                                                            (guild_id, channel_id, message_id, role_id, emoji) 
                                                            VALUES ($1, $2, $3, $4, $5)""",
                                                          guild,
                                                          channel,
                                                          message,
                                                          role,
                                                          emoji.mention
                                                          )

        cls.fetch_all.invalidate(channel, message)
        cls.fetch.invalidate(channel, message, role)
        cls.fetch_by_emoji.invalidate(channel, message, emoji)
        return DatabaseReactionRole(id=model_id,
                                    guild_id=guild,
                                    channel_id=channel,
                                    message_id=message,
                                    role_id=role,
                                    emoji=emoji
                                    )

    @classmethod
    async def edit(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
            emoji: hikari.Emoji
    ) -> DatabaseReactionRole:
        model: DatabaseReactionRole = await cls.fetch(channel, message, role)

        if not model:
            raise ValueError("The role does not exist ")

        await DatabaseReactionRole.db.execute("""insert into reactionrole 
                                                                (guild_id, channel_id, message_id, role_id, emoji) 
                                                                VALUES ($1, $2, $3, $4, $5) 
                                                                ON CONFLICT (guild_id, channel_id, message_id, role_id) 
                                                                DO UPDATE SET emoji=$6""",
                                              model.guild_id,
                                              channel,
                                              message,
                                              role,
                                              emoji.mention
                                              )

        model.emoji = emoji

        cls.fetch_all.invalidate(channel, message)
        cls.fetch.invalidate(channel, message, role)
        cls.fetch_by_emoji.invalidate(model.channel_id, model.message_id, model.emoji)

        return model

    @classmethod
    async def delete(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> DatabaseReactionRole:
        model: DatabaseReactionRole = await cls.fetch(channel, message, role)

        if not model:
            raise ValueError("The role does not exist ")

        await DatabaseReactionRole.db.execute("""delete from reactionrole where 
                                                                channel_id=$1 
                                                                and message_id=$2 and role_id=$3""",
                                              channel,
                                              message,
                                              role)

        cls.fetch_all.invalidate(channel, message)
        cls.fetch.invalidate(channel, message, role)
        cls.fetch_by_emoji.invalidate(model.channel_id, model.message_id, model.emoji)
        return model

    @classmethod
    async def delete_all(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
    ) -> list[DatabaseReactionRole]:
        models: list[DatabaseReactionRole] = await cls.fetch_all(channel, message)

        if not models:
            raise ValueError("The roles does not exist ")

        await DatabaseReactionRole.db.execute("""delete from reactionrole where 
                                                                    channel_id=$1 
                                                                    and message_id=$2""",
                                              channel,
                                              message)

        for model in models:
            cls.fetch_all.invalidate(channel, message)
            cls.fetch.invalidate(channel, message, model.role_id)
            cls.fetch_by_emoji.invalidate(model.channel_id, model.message_id, model.emoji)

        return models

    @classmethod
    async def delete_all_by_role(
            cls,
            guild: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> list[DatabaseReactionRole]:
        records = await DatabaseReactionRole.db.fetch("""select * from reactionrole where guild_id=$1 and role_id=$2""",
                                                      guild,
                                                      role,
                                                      )
        if not records:
            raise ValueError("The roles does not exist ")

        models = [cls._parse_record(record) for record in records]

        await DatabaseReactionRole.db.execute("""delete from reactionrole where guild_id=$1 and role_id=$2""",
                                              guild,
                                              role,
                                              )
        for model in models:
            cls.fetch_all.invalidate(model.channel_id, model.message_id)
            cls.fetch.invalidate(model.channel_id, model.message_id, model.role_id)
            cls.fetch_by_emoji.invalidate(model.channel_id, model.message_id, model.emoji)

        return models

    @classmethod
    @cache.cache(ignore_kwargs=True)
    async def fetch(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> DatabaseReactionRole | None:
        record = await DatabaseReactionRole.db.fetchrow("""select * from reactionrole where 
                                                                        channel_id=$1 
                                                                        and message_id=$2 and role_id=$3""",
                                                        channel,
                                                        message,
                                                        role)

        if not record:
            raise ValueError("The role does not exist ")

        return cls._parse_record(record)

    @classmethod
    @cache.cache(ignore_kwargs=True)
    async def fetch_by_emoji(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            emoji: hikari.Emoji,
    ) -> DatabaseReactionRole | None:
        record = await DatabaseReactionRole.db.fetchrow("""select * from reactionrole 
                                                            where channel_id=$1 and message_id=$2 and emoji=$3""",
                                                        channel,
                                                        message,
                                                        emoji.mention)

        if not record:
            raise ValueError("The role does not exist ")

        return cls._parse_record(record)

    @classmethod
    @cache.cache(ignore_kwargs=True)
    async def fetch_all(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake
    ) -> list[DatabaseReactionRole]:
        records = await DatabaseReactionRole.db.fetch("""select * from reactionrole where 
                                                                     channel_id=$1 
                                                                     and message_id=$2""",
                                                      channel,
                                                      message,
                                                      )

        if not records:
            return []

        return [cls._parse_record(record) for record in records]
