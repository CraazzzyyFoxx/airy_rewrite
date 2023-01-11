import asyncio
import typing

import hikari
import lightbulb

from loguru import logger

from airy.models.bot import Airy
from airy.models import DatabaseAutoRole, DatabaseGuild
from airy.services import BaseService
from airy.utils import helpers


class AutoRolesService(BaseService):
    @classmethod
    async def on_startup(cls, event: hikari.StartedEvent):
        cls.bot.subscribe(hikari.MemberCreateEvent, cls.on_member_join)
        cls.bot.subscribe(hikari.RoleDeleteEvent, cls.on_role_delete)

    @classmethod
    async def on_shutdown(cls, event: hikari.StoppedEvent = None):
        cls.bot.unsubscribe(hikari.MemberCreateEvent, cls.on_member_join)
        cls.bot.unsubscribe(hikari.RoleDeleteEvent, cls.on_role_delete)

    @classmethod
    async def on_role_delete(cls, event: hikari.RoleDeleteEvent):
        await DatabaseAutoRole.db.execute("""delete from autorole where guild_id=$1 and role_id=$2""",
                                          event.guild_id, event.role_id)

    @classmethod
    async def on_member_join(cls, event: hikari.MemberCreateEvent):
        me = cls.bot.cache.get_member(event.guild_id, cls.bot.user_id)
        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.MANAGE_ROLES):
            return
        if not helpers.is_above(me, event.member):
            return
        models = await cls.get_all_for_guild(event.guild_id)

        if not models:
            return

        async with asyncio.TaskGroup() as tg:
            for model in models:
                tg.create_task(cls.bot.rest.add_role_to_member(model.guild_id,
                                                               event.user_id,
                                                               model.role_id,
                                                               reason=f"AutoRole for the joined member")
                               )
                logger.info("Added AutoRole {} to member {} in guild {}",
                            model.role_id,
                            event.user_id,
                            model.role_id)

    @classmethod
    async def on_member_leave(cls, event: hikari.MemberDeleteEvent):
        pass

    @classmethod
    async def create(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
            role: hikari.SnowflakeishOr[hikari.PartialRole]
    ) -> DatabaseAutoRole:
        if not cls._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        guild_id = hikari.Snowflake(guild)
        role_id = hikari.Snowflake(role)

        return await DatabaseAutoRole.create(guild_id, role_id)

    @classmethod
    async def delete(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
            role: hikari.SnowflakeishOr[hikari.PartialRole]
    ) -> None:
        if not cls._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        guild_id = hikari.Snowflake(guild)
        role_id = hikari.Snowflake(role)

        await DatabaseAutoRole.delete(guild_id, role_id)

    @classmethod
    async def get(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
            role: hikari.SnowflakeishOr[hikari.PartialRole]
    ) -> typing.Optional[DatabaseAutoRole]:
        if not cls._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        guild_id = hikari.Snowflake(guild)
        role_id = hikari.Snowflake(role)

        return await DatabaseAutoRole.fetch(guild_id, role_id)

    @classmethod
    async def get_all_for_guild(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild]
    ) -> list[DatabaseAutoRole]:
        if not cls._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        guild_id = hikari.Snowflake(guild)

        return await DatabaseAutoRole.fetch_all(guild_id)

    @classmethod
    async def update_re_assigns_roles(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
            value: bool
    ) -> None:
        model = await DatabaseGuild.fetch(guild)

        if model:
            model.re_assigns_roles = value
            await model.update()


def load(bot: "Airy"):
    AutoRolesService.start(bot)


def unload(bot: "Airy"):
    AutoRolesService.shutdown(bot)
