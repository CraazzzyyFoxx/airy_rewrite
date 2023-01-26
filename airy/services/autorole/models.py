from __future__ import annotations

import attr
import hikari

from asyncpg import Record  # type: ignore

from airy.models.db.impl import DatabaseModel
from airy.models import errors


@attr.define()
class DatabaseAutoRole(DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    role_id: hikari.Snowflake

    @classmethod
    def _parse_record(cls, record: Record):
        return DatabaseAutoRole(id=record.get("id"),
                                guild_id=hikari.Snowflake(record.get("guild_id")),
                                role_id=hikari.Snowflake(record.get("role_id"))
                                )

    @classmethod
    async def create(cls, guild: hikari.Snowflake, role: hikari.Snowflake) -> DatabaseAutoRole | None:
        record = await cls.db.fetchrow("""select * from autorole where guild_id=$1 and role_id=$2""",
                                       guild,
                                       role)

        if record:
            raise errors.RoleAlreadyExists()

        id = await cls.db.fetchval("""insert into autorole (guild_id, role_id) VALUES ($1, $2)""",
                                   guild,
                                   role)

        return DatabaseAutoRole(id=id, guild_id=guild, role_id=role)

    @classmethod
    async def delete(cls, guild: hikari.Snowflake, role: hikari.Snowflake):
        model = await cls.fetch(guild, role)
        await cls.db.execute("""delete from autorole where guild_id = $1 and role_id=$2""",
                             guild,
                             role)
        return model

    @classmethod
    async def fetch(cls, guild: hikari.Snowflake, role: hikari.Snowflake) -> DatabaseAutoRole | None:
        record = await cls.db.fetchrow("""select * from autorole where guild_id=$1 and role_id=$2""",
                                       guild,
                                       role)

        if not record:
            raise errors.RoleDoesNotExist()

        return cls._parse_record(record)

    @classmethod
    async def fetch_all(cls, guild: hikari.Snowflake) -> list[DatabaseAutoRole]:
        records = await cls.db.fetch("""select * from autorole where guild_id=$1""",
                                     guild)

        if not records:
            return []

        return [cls._parse_record(record) for record in records]


@attr.define()
class DatabaseAutoRoleForMember(DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    role_id: hikari.Snowflake
