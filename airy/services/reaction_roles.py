import typing

import hikari
import lightbulb

from asyncpg import Record
from loguru import logger

from airy.models import DatabaseReactionRole
from airy.utils import helpers

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


class ReactionRoleService:
    bot: typing.Optional["Airy"] = None
    _is_started: bool = False

    @classmethod
    def start(cls, bot: "Airy") -> None:
        """
        Start the ReactionRoleService.
        """
        cls.bot = bot
        cls.bot.subscribe(hikari.MessageDeleteEvent, cls.on_delete_message)
        cls.bot.subscribe(hikari.ReactionAddEvent, cls._on_reaction_add)
        cls.bot.subscribe(hikari.ReactionDeleteEvent, cls._on_reaction_remove)
        cls._is_started = True
        logger.info("ReactionRoleService startup complete.")

    @classmethod
    def stop(cls) -> None:
        """
        Stop the ReactionRoleService.
        """
        cls._is_started = False
        logger.info("ReactionRoleService shutdown complete.")

    @classmethod
    def _parse(cls, *args) -> list[hikari.Snowflake]:
        return [hikari.Snowflake(arg) for arg in args]

    @classmethod
    def _parse_record(cls, record: Record) -> DatabaseReactionRole:
        return DatabaseReactionRole(id=record.get("id"),
                                    guild_id=hikari.Snowflake(record.get("guild_id")),
                                    channel_id=hikari.Snowflake(record.get("channel_id")),
                                    message_id=hikari.Snowflake(record.get("message_id")),
                                    role_id=hikari.Snowflake(record.get("role_id")),
                                    emoji=hikari.Emoji.parse(record.get("emoji"))
                                    )

    @classmethod
    async def on_delete_message(cls, event: hikari.MessageDeleteEvent):
        await DatabaseReactionRole.db.execute("""delete from reactionrole 
                                                where channel_id=$1 and message_id=$2""",
                                              event.channel_id,
                                              event.message_id)

    @classmethod
    async def _process(cls, event: hikari.ReactionAddEvent | hikari.ReactionDeleteEvent):
        record = await DatabaseReactionRole.db.fetchrow("""select guild_id, role_id from reactionrole 
                                                                   where channel_id=$1 and message_id=$2 and emoji=$3""",
                                                        event.channel_id,
                                                        event.message_id,
                                                        event.emoji_name)
        if not record:
            return None

        guild_id, role_id = cls._parse(record.get("guild_id"), record.get("role_id"))

        me = cls.bot.cache.get_member(guild_id, cls.bot.user_id)
        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.MANAGE_ROLES):
            return None

        return guild_id, role_id, event.user_id

    @classmethod
    async def _on_reaction_add(cls, event: hikari.ReactionAddEvent):
        data = await cls._process(event)

        if not data:
            return

        guild_id, role_id, user_id = data

        await cls.bot.rest.add_role_to_member(guild=guild_id, user=event.user_id, role=role_id,
                                              reason="Reaction role")

        logger.info("Add Reaction role {} to user {} in guild {}", guild_id, user_id, guild_id)

    @classmethod
    async def _on_reaction_remove(cls, event: hikari.ReactionDeleteEvent):
        data = await cls._process(event)

        if not data:
            return

        guild_id, role_id, user_id = data

        await cls.bot.rest.remove_role_from_member(guild=guild_id, user=event.user_id, role=role_id,
                                                   reason="Reaction role")

        logger.info("Remove Reaction role {} from user {} in guild {}", guild_id, user_id, guild_id)

    @classmethod
    async def create(cls,
                     guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                     channel: hikari.SnowflakeishOr[hikari.PartialChannel],
                     message: hikari.SnowflakeishOr[hikari.PartialMessage],
                     role: hikari.SnowflakeishOr[hikari.PartialRole],
                     emoji: hikari.Emoji
                     ) -> typing.Optional[DatabaseReactionRole]:
        guild_id, channel_id, message_id, role_id = cls._parse(guild, channel, message, role)
        msg = await cls.bot.rest.fetch_message(channel_id, message_id)

        if not msg:
            raise ValueError("Message not found")

        record = await DatabaseReactionRole.db.fetchrow("""select id from reactionrole where 
                                                    guild_id=$1 and channel_id=$2 and message_id=$3 and role_id=$4""",
                                                        guild_id,
                                                        channel_id,
                                                        message_id,
                                                        role_id)

        if record:
            return None

        id = await DatabaseReactionRole.db.fetchval("""insert into reactionrole 
                                                    (guild_id, channel_id, message_id, role_id, emoji) 
                                                    VALUES ($1, $2, $3, $4, $5)""",
                                                    guild_id,
                                                    channel_id,
                                                    message_id,
                                                    role_id,
                                                    emoji.mention
                                                    )

        await msg.add_reaction(emoji)

        logger.info("Create Reaction role {} in guild {}", role_id, guild_id)

        return DatabaseReactionRole(id=id,
                                    guild_id=guild_id,
                                    channel_id=channel_id,
                                    message_id=message_id,
                                    role_id=role_id,
                                    emoji=emoji
                                    )

    @classmethod
    async def edit(cls,
                   guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                   channel: hikari.SnowflakeishOr[hikari.PartialChannel],
                   message: hikari.SnowflakeishOr[hikari.PartialMessage],
                   role: hikari.SnowflakeishOr[hikari.PartialRole],
                   emoji: hikari.Emoji
                   ) -> typing.Optional[DatabaseReactionRole]:
        guild_id, channel_id, message_id, role_id = cls._parse(guild, channel, message, role)
        msg = await cls.bot.rest.fetch_message(channel_id, message_id)

        if not msg:
            raise ValueError("Message not found")

        record = await DatabaseReactionRole.db.fetchrow("""select id from reactionrole where 
                                                            guild_id=$1 and channel_id=$2 
                                                            and message_id=$3 and role_id=$4""",
                                                        guild_id,
                                                        channel_id,
                                                        message_id,
                                                        role_id)

        if record:
            return None

        await DatabaseReactionRole.db.execute("""insert into reactionrole 
                                                            (guild_id, channel_id, message_id, role_id, emoji) 
                                                            VALUES ($1, $2, $3, $4, $5) 
                                                            ON CONFLICT (guild_id, channel_id, message_id, role_id) 
                                                            DO UPDATE SET emoji=$6""",
                                              guild_id,
                                              channel_id,
                                              message_id,
                                              role_id,
                                              emoji.mention
                                              )

        return DatabaseReactionRole(id=record.get("id"),
                                    guild_id=guild_id,
                                    channel_id=channel_id,
                                    message_id=message_id,
                                    role_id=role_id,
                                    emoji=emoji
                                    )

    @classmethod
    async def delete(cls,
                     guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                     channel: hikari.SnowflakeishOr[hikari.PartialChannel],
                     message: hikari.SnowflakeishOr[hikari.PartialMessage],
                     role: hikari.SnowflakeishOr[hikari.PartialRole],
                     ) -> typing.Optional[DatabaseReactionRole]:
        guild_id, channel_id, message_id, role_id = cls._parse(guild, channel, message, role)
        msg = await cls.bot.rest.fetch_message(channel_id, message_id)

        if not msg:
            raise ValueError("Message not found")

        record = await DatabaseReactionRole.db.fetchrow("""select * from reactionrole where 
                                                        guild_id=$1 and channel_id=$2 
                                                        and message_id=$3 and role_id=$4""",
                                                        guild_id,
                                                        channel_id,
                                                        message_id,
                                                        role_id)

        if not record:
            raise ValueError("The role does not exist ")

        model = cls._parse_record(record)
        await msg.remove_reaction(model.emoji)

        await DatabaseReactionRole.db.execute("""delete from reactionrole where 
                                                        guild_id=$1 and channel_id=$2 
                                                        and message_id=$3 and role_id=$4""",
                                              guild_id,
                                              channel_id,
                                              message_id,
                                              role_id)

        logger.info("Remove Reaction role {} in guild {}", role_id, guild_id)
        return model

    @classmethod
    async def get(cls,
                  guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                  channel: hikari.SnowflakeishOr[hikari.PartialChannel],
                  message: hikari.SnowflakeishOr[hikari.PartialMessage],
                  role: hikari.SnowflakeishOr[hikari.PartialRole],
                  ) -> typing.Optional[DatabaseReactionRole]:
        guild_id, channel_id, message_id, role_id = cls._parse(guild, channel, message, role)

        record = await DatabaseReactionRole.db.fetchrow("""select id from reactionrole where 
                                                                    guild_id=$1 and channel_id=$2 
                                                                    and message_id=$3 and role_id=$4""",
                                                        guild_id,
                                                        channel_id,
                                                        message_id,
                                                        role_id)

        if not record:
            return None

        return cls._parse_record(record)

    @classmethod
    async def get_all(cls,
                      guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                      channel: hikari.SnowflakeishOr[hikari.PartialChannel],
                      message: hikari.SnowflakeishOr[hikari.PartialMessage],
                      ) -> typing.List[DatabaseReactionRole]:
        guild_id, channel_id, message_id = cls._parse(guild, channel, message)

        records = await DatabaseReactionRole.db.fetch("""select * from reactionrole where 
                                                             guild_id=$1 and channel_id=$2 
                                                             and message_id=$3""",
                                                      guild_id,
                                                      channel_id,
                                                      message_id,
                                                      )

        if not records:
            return []

        return [cls._parse_record(record) for record in records]


def load(bot: "Airy"):
    ReactionRoleService.start(bot)


def unload(_: "Airy"):
    ReactionRoleService.stop()
