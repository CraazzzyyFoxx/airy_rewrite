from __future__ import annotations

import typing

import hikari
import attr

from airy.models.db.impl import DatabaseModel


@attr.define()
class DatabaseGuild(DatabaseModel):
    """Defining a guild model to store settings of the guild"""

    guild_id: hikari.Snowflake
    re_assigns_roles: bool

    @classmethod
    async def create(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
            re_assigns_roles: bool = False
    ) -> DatabaseGuild:
        guild_id = hikari.Snowflake(guild)

        await cls.db.fetch("""insert into guild (guild_id, re_assigns_roles) values ($1, $2)""",
                           guild_id,
                           re_assigns_roles)

        return DatabaseGuild(guild_id=guild_id, re_assigns_roles=re_assigns_roles)

    async def update(self) -> None:
        await self.db.execute("""insert into guild (guild_id, re_assigns_roles) VALUES ($1, $2) 
                                ON CONFLICT (guild_id) do 
                                update set re_assigns_roles=$2""",
                              self.guild_id,
                              self.re_assigns_roles
                              )

    async def delete(self):
        await self.db.execute("""delete from guild where guild_id=$1""",
                              self.guild_id)

    @classmethod
    async def fetch(
            cls,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
    ) -> typing.Optional[DatabaseGuild]:
        guild_id = hikari.Snowflake(guild)

        record = await cls.db.fetchrow("""select * from guild where guild_id=$1""",
                                       guild_id)

        if not record:
            return None

        return DatabaseGuild(guild_id=guild_id,
                             re_assigns_roles=record.get("re_assigns_roles")
                             )
