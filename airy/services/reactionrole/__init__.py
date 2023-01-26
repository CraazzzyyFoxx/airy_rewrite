from __future__ import annotations

import typing

import hikari
import lightbulb

from loguru import logger

from airy.services import BaseService
from airy.utils import helpers
from airy.models import errors

from .models import DatabaseReactionRole

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


class ReactionRolesServiceT(BaseService):
    async def on_startup(self, event: hikari.StartedEvent):
        self.bot.subscribe(hikari.MessageDeleteEvent, self.on_delete_message)
        self.bot.subscribe(hikari.ReactionAddEvent, self._on_reaction_add)
        self.bot.subscribe(hikari.ReactionDeleteEvent, self._on_reaction_remove)
        self.bot.subscribe(hikari.RoleDeleteEvent, self.on_delete_role)

    async def on_shutdown(self, event: hikari.StoppedEvent = None):
        self.bot.unsubscribe(hikari.MessageDeleteEvent, self.on_delete_message)
        self.bot.unsubscribe(hikari.ReactionAddEvent, self._on_reaction_add)
        self.bot.unsubscribe(hikari.ReactionDeleteEvent, self._on_reaction_remove)
        self.bot.unsubscribe(hikari.RoleDeleteEvent, self.on_delete_role)

    def _parse(self, *args) -> list[hikari.Snowflake]:
        return [hikari.Snowflake(arg) for arg in args]

    async def on_delete_message(self, event: hikari.MessageDeleteEvent):
        try:
            await DatabaseReactionRole.delete_all(event.channel_id, event.message_id)
        except errors.RoleDoesNotExist:
            pass

    async def on_delete_role(self, event: hikari.RoleDeleteEvent):
        try:
            await DatabaseReactionRole.delete_all_by_role(event.guild_id, event.role_id)
        except errors.RoleDoesNotExist:
            pass

    async def _process(self, event: hikari.ReactionAddEvent | hikari.ReactionDeleteEvent):
        me = self.bot.cache.get_member(event.guild_id, self.bot.user_id)

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
        except errors.RoleDoesNotExist:
            return None

        return model.guild_id, model.role_id, event.user_id

    async def _on_reaction_add(self, event: hikari.ReactionAddEvent):
        data = await self._process(event)

        if not data:
            return

        guild_id, role_id, user_id = data

        await self.bot.rest.add_role_to_member(guild=guild_id, user=event.user_id, role=role_id,
                                              reason="Reaction role")

        logger.info("Add Reaction role {} to user {} in guild {}", guild_id, user_id, guild_id)

    async def _on_reaction_remove(self, event: hikari.ReactionDeleteEvent):
        data = await self._process(event)

        if not data:
            return

        guild_id, role_id, user_id = data

        await self.bot.rest.remove_role_from_member(guild=guild_id, user=event.user_id, role=role_id,
                                                   reason="Reaction role")

        logger.info("Remove Reaction role {} from user {} in guild {}", guild_id, user_id, guild_id)

    async def create(
            self,
            guild: hikari.Snowflake,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
            emoji: hikari.Emoji
    ) -> DatabaseReactionRole:
        """

        :param guild:
        :param channel:
        :param message:
        :param role:
        :param emoji:

        :return: DatabaseReactionRole

        :raise: hikari.errors.ForbiddenError
            If you are missing the `ADD_REACTIONS` (this is only necessary if you
            are the first person to add the reaction).
        :raise: hikari.errors.NotFoundError
            If the channel or message is not found.
        :raise: RoleAlreadyExists
            If the role already exists
        """
        await self.bot.rest.add_reaction(channel, message, emoji)
        model = await DatabaseReactionRole.create(guild, channel, message, role, emoji)

        logger.info("Create Reaction role {} in guild {}", role, guild)
        return model

    async def edit(
            self,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
            emoji: hikari.Emoji
    ) -> DatabaseReactionRole:
        """

        :param channel:
        :param message:
        :param role:
        :param emoji:
        :return: DatabaseReactionRole

        :raise: hikari.errors.ForbiddenError
            If you are missing the `ADD_REACTIONS` (this is only necessary if you
            are the first person to add the reaction).
        :raise: hikari.errors.NotFoundError
            If the channel or message is not found.
        :raise: RoleDoesNotExist
            If the role not found
        """

        model = await DatabaseReactionRole.fetch(channel, message, role)
        await model.edit(emoji)
        return model

    async def delete(
            self,
            guild: hikari.Snowflake,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> typing.Optional[DatabaseReactionRole]:
        """

        :param guild:
        :param channel:
        :param message:
        :param role:
        :return: DatabaseReactionRole

        :raise: hikari.errors.ForbiddenError
            If you are missing the `ADD_REACTIONS` (this is only necessary if you
            are the first person to add the reaction).
        :raise: hikari.errors.NotFoundError
            If the channel or message is not found.
        :raise: RoleDoesNotExist
            If the role not found
        """

        msg = await self.bot.rest.fetch_message(channel, message)

        model = await DatabaseReactionRole.fetch(channel, message, role)
        await model.delete()

        await msg.remove_reaction(model.emoji)

        logger.info("Remove Reaction role {} in guild {}", role, guild)
        return model

    async def get(
            self,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> typing.Optional[DatabaseReactionRole]:
        """

        :param channel:
        :param message:
        :param role:
        :return: DatabaseReactionRole

        :raise: RoleDoesNotExist
            If the role not found
        """
        return await DatabaseReactionRole.fetch(channel, message, role)

    async def get_all(
            self,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
    ) -> typing.List[DatabaseReactionRole]:
        """

        :param channel:
        :param message:
        :return: DatabaseReactionRole

        :raise: RoleDoesNotExist
            If the role not found
        """

        return await DatabaseReactionRole.fetch_all(channel, message)


ReactionRolesService = ReactionRolesServiceT()


def load(bot: "Airy"):
    ReactionRolesService.start(bot)


def unload(bot: "Airy"):
    ReactionRolesService.shutdown(bot)
