import typing

import hikari
import lightbulb

from loguru import logger

from airy.models import DatabaseReactionRole
from airy.services import BaseService
from airy.utils import helpers

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


class ReactionRoleService(BaseService):
    @classmethod
    async def on_startup(cls, event: hikari.StartedEvent):
        cls.bot.subscribe(hikari.MessageDeleteEvent, cls.on_delete_message)
        cls.bot.subscribe(hikari.ReactionAddEvent, cls._on_reaction_add)
        cls.bot.subscribe(hikari.ReactionDeleteEvent, cls._on_reaction_remove)

    @classmethod
    async def on_shutdown(cls, event: hikari.StoppedEvent = None):
        cls.bot.unsubscribe(hikari.MessageDeleteEvent, cls.on_delete_message)
        cls.bot.unsubscribe(hikari.ReactionAddEvent, cls._on_reaction_add)
        cls.bot.unsubscribe(hikari.ReactionDeleteEvent, cls._on_reaction_remove)

    @classmethod
    def _parse(cls, *args) -> list[hikari.Snowflake]:
        return [hikari.Snowflake(arg) for arg in args]

    @classmethod
    async def on_delete_message(cls, event: hikari.MessageDeleteEvent):
        await DatabaseReactionRole.delete_all(event.channel_id, event.message_id)

    @classmethod
    async def on_delete_role(cls, event: hikari.RoleDeleteEvent):
        await DatabaseReactionRole.delete_all_by_role(event.guild_id, event.role_id)

    @classmethod
    async def _process(cls, event: hikari.ReactionAddEvent | hikari.ReactionDeleteEvent):
        me = cls.bot.cache.get_member(event.guild_id, cls.bot.user_id)

        if not me:
            return

        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.MANAGE_ROLES):
            return None

        if event.emoji_id:
            emoji = hikari.Emoji.parse(f"<:{event.emoji_name}:{event.emoji_id}>")
        else:
            emoji = hikari.Emoji.parse(event.emoji_name)

        try:
            model: DatabaseReactionRole = await DatabaseReactionRole.fetch_by_emoji(event.channel_id,
                                                                                    event.message_id,
                                                                                    emoji)
        except ValueError:
            return None

        return model.guild_id, model.role_id, event.user_id

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

        model = await DatabaseReactionRole.create(guild_id, channel_id, message_id, role_id, emoji)
        await msg.add_reaction(emoji)

        logger.info("Create Reaction role {} in guild {}", role_id, guild_id)

        return model

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

        model = await DatabaseReactionRole.edit(channel, message, role, emoji)
        return model

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

        model = await DatabaseReactionRole.delete(channel_id, message_id, role_id)
        await msg.remove_reaction(model.emoji)

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

        return await DatabaseReactionRole.fetch(guild_id, channel_id, message_id, role_id)

    @classmethod
    async def get_all(cls,
                      guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                      channel: hikari.SnowflakeishOr[hikari.PartialChannel],
                      message: hikari.SnowflakeishOr[hikari.PartialMessage],
                      ) -> typing.List[DatabaseReactionRole]:
        guild_id, channel_id, message_id = cls._parse(guild, channel, message)

        return await DatabaseReactionRole.fetch_all(guild_id, channel_id, message_id)


def load(bot: "Airy"):
    ReactionRoleService.start(bot)


def unload(bot: "Airy"):
    ReactionRoleService.shutdown(bot)
