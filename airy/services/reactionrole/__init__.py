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
    @classmethod
    async def on_startup(cls, event: hikari.StartedEvent):
        cls.bot.subscribe(hikari.MessageDeleteEvent, cls.on_delete_message)
        cls.bot.subscribe(hikari.ReactionAddEvent, cls._on_reaction_add)
        cls.bot.subscribe(hikari.ReactionDeleteEvent, cls._on_reaction_remove)
        cls.bot.subscribe(hikari.RoleDeleteEvent, cls.on_delete_role)

    @classmethod
    async def on_shutdown(cls, event: hikari.StoppedEvent | None = None):
        cls.bot.unsubscribe(hikari.MessageDeleteEvent, cls.on_delete_message)
        cls.bot.unsubscribe(hikari.ReactionAddEvent, cls._on_reaction_add)
        cls.bot.unsubscribe(hikari.ReactionDeleteEvent, cls._on_reaction_remove)
        cls.bot.unsubscribe(hikari.RoleDeleteEvent, cls.on_delete_role)

    @classmethod
    async def on_delete_message(cls, event: hikari.MessageDeleteEvent):
        model = await DatabaseReactionRole.fetch(event.channel_id, event.message_id)
        if model:
            await model.delete()

    @classmethod
    async def on_delete_role(cls, event: hikari.RoleDeleteEvent):
        await DatabaseReactionRole.delete_all_by_role(event.guild_id, event.role_id)

    @classmethod
    async def _process(
            cls,
            event: hikari.ReactionAddEvent | hikari.ReactionDeleteEvent,
            added: bool = True
    ) -> None:

        channel = cls.bot.cache.get_guild_channel(event.channel_id)
        me = cls.bot.cache.get_member(channel.guild_id, cls.bot.user_id)  # type: ignore

        if not me or cls.bot.user_id == event.user_id:
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

        member = cls.bot.cache.get_member(channel.guild_id, event.user_id)
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
                await cls.bot.rest.add_role_to_member(guild=model.guild_id, user=event.user_id, role=role_id,
                                                      reason="Reaction role")
                logger.info("Add Reaction role {} to user {} in guild {}", role_id, member.id, model.guild_id)
            else:
                await cls.bot.rest.remove_role_from_member(guild=model.guild_id, user=event.user_id, role=role_id,
                                                           reason="Reaction role")
                logger.info("Remove Reaction role {} from user {} in guild {}", role_id, member.id, model.guild_id)
        except (hikari.ForbiddenError, hikari.NotFoundError):
            pass

    @classmethod
    async def _on_reaction_add(cls, event: hikari.ReactionAddEvent):
        await cls._process(event, added=True)

    @classmethod
    async def _on_reaction_remove(cls, event: hikari.ReactionDeleteEvent):
        await cls._process(event, added=False)

    @classmethod
    async def create(
            cls,
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
            await cls.bot.rest.add_reaction(channel, message, emoji)
            logger.info("Create Reaction role pair `{} : {}` in guild {}", emoji, role, guild)
        return model

    @classmethod
    async def delete(
            cls,
            guild: hikari.Snowflake,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
            role: hikari.Snowflake,
    ) -> DatabaseReactionRoleEntry | None:
        try:
            msg = await cls.bot.rest.fetch_message(channel, message)
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

    @classmethod
    async def get(
            cls,
            channel: hikari.Snowflake,
            message: hikari.Snowflake,
    ) -> DatabaseReactionRole | None:
        return await DatabaseReactionRole.fetch(channel, message)


ReactionRolesService = ReactionRolesServiceT()


def load(bot: "Airy"):
    ReactionRolesService.start(bot)


def unload(bot: "Airy"):
    ReactionRolesService.shutdown(bot)
