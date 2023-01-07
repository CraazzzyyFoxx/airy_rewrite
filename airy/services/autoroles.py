import asyncio
import typing

import hikari
from loguru import logger

from airy.models.bot import Airy
from airy.models import DatabaseAutoRoleForMember, DatabaseAutoRole, DatabaseGuild


class AutoRolesService:
    bot: typing.Optional[Airy] = None
    _is_started: bool = False

    @classmethod
    def start(cls, bot: "Airy") -> None:
        """
        Start the AutoRolesService.
        """
        cls.bot = bot
        cls.bot.subscribe(hikari.MemberCreateEvent, cls.on_member_join)
        cls._is_started = True
        logger.info("AutoRolesService startup complete.")

    @classmethod
    def stop(cls) -> None:
        """
        Stop the AutoRolesService.
        """
        cls._is_started = False
        logger.info("AutoRolesService shutdown complete.")

    @classmethod
    async def on_member_join(cls, event: hikari.MemberCreateEvent):
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

        # guild_model = await DatabaseGuild.fetch(event.guild_id)
        #
        # if guild_model and not guild_model.re_assigns_roles:
        #     return
        #
        # records = await DatabaseAutoRoleForMember.db.fetch("""select role_id from autorole_for_member
        #                                                     where guild_id=$1 and user_id=$2""",
        #                                                    event.guild_id,
        #                                                    event.user_id)
        #
        # if not records:
        #     return
        #
        # async with asyncio.TaskGroup() as tg:
        #     for record in records:
        #         await cls.bot.rest.add_role_to_member(event.guild_id,
        #                                               event.user_id,
        #                                               record.get("role_id"),
        #                                               reason=f"AutoRole re-assigns for the joined member")

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

        id = await DatabaseAutoRole.db.fetchval("""insert into autorole (guild_id, role_id) VALUES ($1, $2) 
                                                    returning id""",
                                                guild_id,
                                                role_id,
                                                )

        return DatabaseAutoRole(id=id, guild_id=guild_id, role_id=role_id)

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

        await DatabaseAutoRole.db.execute("""delete from autorole where guild_id=$1 and role_id=$2""",
                                          guild_id,
                                          role_id,
                                          )

    @classmethod
    async def get(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
            role: hikari.SnowflakeishOr[hikari.PartialRole]
    ) -> DatabaseAutoRole:
        if not cls._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        guild_id = hikari.Snowflake(guild)
        role_id = hikari.Snowflake(role)

        record = await DatabaseAutoRole.db.fetchrow("""select * from autorole where guild_id=$1 and role_id=$2""",
                                                    guild_id,
                                                    role_id)

        if record:
            return DatabaseAutoRole(id=record.get("id"),
                                    guild_id=hikari.Snowflake(record.get("guild_id")),
                                    role_id=hikari.Snowflake(record.get("role_id"))
                                    )

    @classmethod
    async def get_all_for_guild(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild]
    ) -> list[DatabaseAutoRole]:
        if not cls._is_started:
            raise hikari.ComponentStateConflictError("The AutoRolesService is not running.")

        guild_id = hikari.Snowflake(guild)

        records = await DatabaseAutoRole.db.fetch("""select * from autorole where guild_id=$1""",
                                                  guild_id)

        if not records:
            return []

        return [DatabaseAutoRole(id=id,
                                 guild_id=hikari.Snowflake(record.get("guild_id")),
                                 role_id=hikari.Snowflake(record.get("role_id")))
                for record in records]

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


def unload(_: "Airy"):
    AutoRolesService.stop()
