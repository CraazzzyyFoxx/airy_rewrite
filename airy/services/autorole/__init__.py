import asyncio
import typing

import hikari
import lightbulb

from loguru import logger

from airy.models.bot import Airy
from airy.models import DatabaseGuild
from airy.services import BaseService
from airy.utils import helpers

from .models import DatabaseAutoRole


class AutoRolesServiceT(BaseService):
    async def on_startup(self, event: hikari.StartedEvent):
        self.bot.subscribe(hikari.MemberCreateEvent, self.on_member_join)
        self.bot.subscribe(hikari.RoleDeleteEvent, self.on_role_delete)

    async def on_shutdown(self, event: hikari.StoppedEvent = None):
        self.bot.unsubscribe(hikari.MemberCreateEvent, self.on_member_join)
        self.bot.unsubscribe(hikari.RoleDeleteEvent, self.on_role_delete)

    async def on_role_delete(self, event: hikari.RoleDeleteEvent):
        await DatabaseAutoRole.db.execute("""delete from autorole where guild_id=$1 and role_id=$2""",
                                          event.guild_id, event.role_id)

    async def on_member_join(self, event: hikari.MemberCreateEvent):
        me = self.bot.cache.get_member(event.guild_id, self.bot.user_id)
        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.MANAGE_ROLES):
            return
        models = await self.get_all_for_guild(event.guild_id)

        if not models:
            return

        async with asyncio.TaskGroup() as tg:
            for model in models:
                tg.create_task(self.bot.rest.add_role_to_member(model.guild_id,
                                                                event.user_id,
                                                                model.role_id,
                                                                reason=f"AutoRole for the joined member")
                               )
                logger.info("Added AutoRole {} to member {} in guild {}",
                            model.role_id,
                            event.user_id,
                            model.role_id)

    async def on_member_leave(self, event: hikari.MemberDeleteEvent):
        pass

    async def create(
            self,
            guild: hikari.Snowflake,
            role: hikari.Snowflake
    ) -> DatabaseAutoRole:
        """

        :param guild:
        :param role:
        :return: DatabaseAutoRole

        :raise: RoleAlreadyExists
            If the role already exists

        """
        if not self._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        return await DatabaseAutoRole.create(guild, role)

    async def delete(
            self,
            guild: hikari.Snowflake,
            role: hikari.Snowflake
    ) -> DatabaseAutoRole:
        """

        :param guild:
        :param role:
        :return: DatabaseAutoRole

        :raise: RoleDoesNotExist
            If the role not found
        """
        if not self._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        return await DatabaseAutoRole.delete(guild, role)

    async def get(
            self,
            guild: hikari.Snowflake,
            role: hikari.Snowflake
    ) -> typing.Optional[DatabaseAutoRole]:
        """

        :param guild:
        :param role:
        :return: DatabaseAutoRole

        :raise: RoleDoesNotExist
            If the role not found
        """
        if not self._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        return await DatabaseAutoRole.fetch(guild, role)

    async def get_all_for_guild(
            self,
            guild: hikari.Snowflake
    ) -> list[DatabaseAutoRole]:
        """

        :param guild:
        :return: list[DatabaseAutoRole]
        """
        if not self._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        return await DatabaseAutoRole.fetch_all(guild)

    async def update_re_assigns_roles(
            self,
            guild: hikari.Snowflake,
            value: bool
    ) -> None:
        model = await DatabaseGuild.fetch(guild)

        if model:
            model.re_assigns_roles = value
            await model.update()


AutoRolesService = AutoRolesServiceT()


def load(bot: "Airy"):
    AutoRolesService.start(bot)


def unload(bot: "Airy"):
    AutoRolesService.shutdown(bot)
