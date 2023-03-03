from __future__ import annotations

import typing

import hikari
import lightbulb

from loguru import logger

from airy.services import BaseService
from airy.utils import helpers

from .models import DatabaseReactionRole, ReactionRoleType, DatabaseReactionRoleEntry

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


class ReactionRolesServiceT(BaseService):
    async def on_startup(self, event: hikari.StartedEvent):
        self.bot.subscribe(hikari.MessageDeleteEvent, self.on_delete_message)
        self.bot.subscribe(hikari.ReactionAddEvent, self._on_reaction_add)
        self.bot.subscribe(hikari.ReactionDeleteEvent, self._on_reaction_remove)
        self.bot.subscribe(hikari.RoleDeleteEvent, self.on_delete_role)

    async def on_shutdown(self, event: hikari.StoppedEvent | None = None):
        self.bot.unsubscribe(hikari.MessageDeleteEvent, self.on_delete_message)
        self.bot.unsubscribe(hikari.ReactionAddEvent, self._on_reaction_add)
        self.bot.unsubscribe(hikari.ReactionDeleteEvent, self._on_reaction_remove)
        self.bot.unsubscribe(hikari.RoleDeleteEvent, self.on_delete_role)

    @staticmethod
    async def on_delete_message(event: hikari.MessageDeleteEvent):
        model = await DatabaseReactionRole.fetch(event.channel_id, event.message_id)
        if model:
            await model.delete()

    @staticmethod
    async def on_delete_role(event: hikari.RoleDeleteEvent):
        await DatabaseReactionRole.delete_all_by_role(event.guild_id, event.role_id)

    async def _process(
            self,
            event: hikari.ReactionAddEvent | hikari.ReactionDeleteEvent,
            added: bool = True
    ) -> None:

        channel = self.bot.cache.get_guild_channel(event.channel_id)
        me = self.bot.cache.get_member(channel.guild_id, self.bot.user_id)  # type: ignore

        if not me or self.bot.user_id == event.user_id:
            return None

        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.MANAGE_ROLES):
            return None

        if event.emoji_id:
            emoji = hikari.Emoji.parse(f"<:{event.emoji_name}:{event.emoji_id}>")
        else:
            emoji = hikari.Emoji.parse(event.emoji_name)  # type: ignore

        action: bool | None = None  # None - do nothing, False - remove, True - add

        model: DatabaseReactionRole = await DatabaseReactionRole.fetch(event.channel_id, event.message_id)

        if not model:
            return

        member = self.bot.cache.get_member(channel.guild_id, event.user_id)
        role_id = model.get_role_by_emoji(emoji)
        roles_id = [entry.role_id for entry in model.entries]

        if model.type == ReactionRoleType.NORMAL:
            action = added
        elif model.type == ReactionRoleType.UNIQUE:
            for check_role_id in roles_id:
                if check_role_id in member.role_ids:
                    action = False
                    break
            else:
                action = added
        elif model.type == ReactionRoleType.VERIFY:
            action = added and True
        elif model.type == ReactionRoleType.DROP:
            action = added and False
        elif model.type == ReactionRoleType.REVERSED:
            action = not added
        d = role_id in member.role_ids
        if d == action:
            return

        try:
            if action:
                await self.bot.rest.add_role_to_member(guild=model.guild_id, user=event.user_id, role=role_id,
                                                       reason="Reaction role")
                logger.info("Add Reaction role {} to user {} in guild {}", role_id, member.id, model.guild_id)
            else:
                await self.bot.rest.remove_role_from_member(guild=model.guild_id, user=event.user_id, role=role_id,
                                                            reason="Reaction role")
                logger.info("Remove Reaction role {} from user {} in guild {}", role_id, member.id, model.guild_id)
        except (hikari.ForbiddenError, hikari.NotFoundError):
            pass

    async def _on_reaction_add(self, event: hikari.ReactionAddEvent):
        await self._process(event, added=True)

    async def _on_reaction_remove(self, event: hikari.ReactionDeleteEvent):
        await self._process(event, added=False)

    async def create(
            self,
            guild: hikari.Snowflake,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role_type: ReactionRoleType,
            max_roles: int,
            roles: list[hikari.Snowflake],
            emojis: list[hikari.Emoji]
    ) -> DatabaseReactionRole:

        model: DatabaseReactionRole = await DatabaseReactionRole.fetch(channel, message)

        if model:
            await model.add_entries([DatabaseReactionRoleEntry(id=model.id, role_id=role, emoji=emoji)
                                     for role, emoji in zip(roles, emojis)])
        else:
            model = await DatabaseReactionRole.create(guild, channel, message, role_type, max_roles, roles, emojis)

        for role, emoji in zip(roles, emojis):
            await self.bot.rest.add_reaction(channel, message, emoji)
            logger.info("Create Reaction role pair `{} : {}` in guild {}", emoji, role, guild)
        return model

    async def delete(
            self,
            guild: hikari.Snowflake,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> DatabaseReactionRoleEntry | None:
        try:
            msg = await self.bot.rest.fetch_message(channel, message)
        except (hikari.NotFoundError, hikari.ForbiddenError):
            return None

        model: DatabaseReactionRole = await DatabaseReactionRole.fetch(channel, message)
        for entry in model.entries:
            if entry.role_id == role:
                await model.remove_entries([DatabaseReactionRoleEntry(id=model.id,
                                                                      role_id=entry.role_id,
                                                                      emoji=entry.emoji)
                                            ])
                await msg.remove_reaction(entry.emoji)

                logger.info("Remove Reaction role {} in guild {}", role, guild)
                return entry

    @staticmethod
    async def get(
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
    ) -> DatabaseReactionRole | None:
        return await DatabaseReactionRole.fetch(channel, message)


ReactionRolesService = ReactionRolesServiceT()


def load(bot: "Airy"):
    ReactionRolesService.start(bot)


def unload(bot: "Airy"):
    ReactionRolesService.shutdown(bot)
