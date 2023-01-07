from __future__ import annotations

import typing
import typing as t
from enum import IntEnum

import attr
import hikari

from airy.models.db.impl import DatabaseModel

__all__ = ("DatabaseSectionRole", "DatabaseEntrySectionRole", "HierarchyRoles")


class HierarchyRoles(IntEnum):
    Missing = 0
    TopDown = 1
    BottomTop = 2

    @classmethod
    def try_value(cls, value):
        for name, value_ in cls._member_map_.items():
            if value_.value == int(value):
                return cls._member_map_[name]
        return value

    @classmethod
    def try_name(cls, value):
        for name, value_ in cls._member_map_.items():
            if name == value:
                return cls._member_map_[name]
        return value

    @classmethod
    def to_choices(cls) -> t.List[hikari.CommandChoice]:
        return [hikari.CommandChoice(name=name, value=str(value.value)) for name, value in cls._member_map_.items()]


@attr.define()
class DatabaseSectionRole(DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    role_id: hikari.Snowflake
    hierarchy: HierarchyRoles

    entries: typing.List[DatabaseEntrySectionRole] = attr.Factory(list)

    @classmethod
    async def create(cls,
                     guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                     role: hikari.SnowflakeishOr[hikari.PartialRole],
                     hierarchy: HierarchyRoles,
                     entries: list[hikari.SnowflakeishOr[hikari.PartialRole]]
                     ):
        id_ = await cls.db.fetch("""INSERT INTO sectionrole (guild_id, role_id, hierarchy) 
                                VALUES ($1, $2, $3) RETURNING id""",
                                 hikari.Snowflake(guild),
                                 hikari.Snowflake(role),
                                 hierarchy
                                 )

        await cls.db.executemany("""INSERT INTO sectionrole_entry (role_id, entry_id)
                                    VALUES ($1, $2) returning id""",
                                 [(hikari.Snowflake(role), hikari.Snowflake(entry)) for entry in entries])

        entries = await DatabaseEntrySectionRole.fetch(role)

        return DatabaseSectionRole(id=id_[0],
                                   guild_id=hikari.Snowflake(guild),
                                   role_id=hikari.Snowflake(role),
                                   hierarchy=hierarchy,
                                   entries=entries
                                   )

    @classmethod
    async def fetch(cls,
                    guild: hikari.SnowflakeishOr[hikari.PartialGuild],
                    role: hikari.SnowflakeishOr[hikari.PartialRole]) -> DatabaseSectionRole | None:
        record = await cls.db.fetchrow("""select * from sectionrole where guild_id = $1 and role_id = $2 """,
                                       hikari.Snowflake(guild),
                                       hikari.Snowflake(role))
        if not record:
            return None

        entries = await DatabaseEntrySectionRole.fetch(role)

        return DatabaseSectionRole(id=record.get("id"),
                                   guild_id=hikari.Snowflake(record.get("guild_id")),
                                   role_id=hikari.Snowflake(record.get("role_id")),
                                   hierarchy=HierarchyRoles(record.get("hierarchy")),
                                   entries=entries
                                   )

    async def update(self):
        await self.db.execute("""INSERT INTO sectionrole (guild_id, role_id, hierarchy)
                                    VALUES ($1, $2, $3)
                                    ON CONFLICT (guild_id, role_id) DO
                                    UPDATE SET hierarchy = $3""",
                               self.guild_id,
                               self.role_id,
                               self.hierarchy)

    async def delete(self):
        await self.db.execute("""DELETE FROM sectionrole where guild_id= $1 and role_id = $2""",
                               self.guild_id,
                               self.role_id)

    @classmethod
    async def fetch_all(cls, guild: hikari.SnowflakeishOr[hikari.PartialGuild]) -> list[DatabaseSectionRole]:
        records = await cls.db.fetch("""select * from sectionrole where guild_id = $1""",
                                     hikari.Snowflake(guild),
                                     )
        if not records:
            return []

        return [DatabaseSectionRole(id=record.get("id"),
                                    guild_id=hikari.Snowflake(record.get("guild_id")),
                                    role_id=hikari.Snowflake(record.get("role_id")),
                                    hierarchy=HierarchyRoles(record.get("hierarchy")),
                                    entries=await DatabaseEntrySectionRole.fetch(record.get("role_id"))
                                    )
                for record in records]

    async def add_entries(self, entries: list[hikari.SnowflakeishOr[hikari.PartialRole]]):
        if not entries:
            return
        await self.db.executemany("""INSERT INTO sectionrole_entry (role_id, entry_id)
                                            VALUES ($1, $2)""",
                                   [(hikari.Snowflake(self.role_id), hikari.Snowflake(entry)) for entry in entries])
        data = await DatabaseEntrySectionRole.fetch(self.role_id)
        self.entries = data

    async def remove_entries(self, entries: list[hikari.SnowflakeishOr[hikari.PartialRole]]):
        if not entries:
            return
        await self.db.execute("""DELETE FROM sectionrole_entry where entry_id = ANY($1::bigint[])""",
                              [int(entry) for entry in entries])
        data = await DatabaseEntrySectionRole.fetch(self.role_id)
        self.entries = data


@attr.define()
class DatabaseEntrySectionRole(DatabaseModel):
    id: int
    role_id: hikari.Snowflake
    entry_id: hikari.Snowflake

    @classmethod
    async def fetch(cls, role: hikari.SnowflakeishOr[hikari.PartialRole]) -> list[DatabaseEntrySectionRole]:
        records = await cls.db.fetch("""select * from sectionrole_entry where role_id = $1""",
                                     hikari.Snowflake(role))

        return [DatabaseEntrySectionRole(id=record.get("id"),
                                         entry_id=hikari.Snowflake(record.get("entry_id")),
                                         role_id=hikari.Snowflake(record.get("role_id")))
                for record in records]

    async def delete(self):
        await self.db.fetch("""DELETE FROM sectionrole_entry where role_id = $1 and entry_id=$2""",
                            self.role_id,
                            self.entry_id)
