from __future__ import annotations

import typing

import hikari
import attr

from airy.models.db.impl import DatabaseModel


@attr.define()
class DatabaseUser(DatabaseModel):
    """
    Represents user data stored inside the database.
    """
    id: hikari.Snowflake
    """The ID of this user."""

    tz: str
    """The timezone this user is bound to."""

    async def update(self) -> None:
        """Update or insert this user into the database."""

        await self.db.execute(
            """
            INSERT INTO users (id, tz) 
            VALUES ($1, $2)
            ON CONFLICT (id) DO
            UPDATE SET tz = $2""",
            self.id,
            self.tz
        )

    @classmethod
    async def fetch(
            cls,
            user: hikari.SnowflakeishOr[hikari.PartialUser]
    ) -> DatabaseUser:
        """Fetch a user from the database. If not present, returns a default DatabaseUser object.

        Parameters
        ----------
        user : hikari.SnowflakeishOr[hikari.PartialUser]
            The user to retrieve database information for.

        Returns
        -------
        DatabaseUser
            An object representing stored user data.
        """

        record = await cls.db.fetchrow(
            """SELECT * FROM users WHERE id = $1""",
            hikari.Snowflake(user),
        )

        if not record:
            return DatabaseUser(id=hikari.Snowflake(user), tz="UTC")

        return DatabaseUser(id=hikari.Snowflake(record.get("user_id")), tz=record.get("tz"))

    @classmethod
    async def fetch_all(cls) -> typing.List[DatabaseUser]:
        """Fetch all stored user data that belongs to the specified guild.

        Parameters
        ----------

        Returns
        -------
        List[DatabaseUser]
            A list of objects representing stored user data.
        """

        records = await cls.db.fetch("""SELECT * FROM users""")

        if not records:
            return []

        return [DatabaseUser(id=hikari.Snowflake(record.get("user_id")), tz=record.get("tz")) for record in records]


@attr.define()
class DatabaseGuildUser(DatabaseModel):
    """
    Represents user data stored inside the database.
    """
    id: hikari.Snowflake
    """The DB ID of this user."""

    guild_id: hikari.Snowflake
    """The guild this user is bound to."""

    user_id: hikari.Snowflake
    """The ID this user is bound to."""

    experience: int
    """The experience this user is bound to."""

    async def update(self) -> None:
        """Update or insert this user into the database."""

        await self.db.execute(
            """
            INSERT INTO guild_users (user_id, guild_id, experience) 
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, guild_id) DO
            UPDATE SET experience = $3""",
            self.user_id,
            self.guild_id,
            self.experience,
        )

    @classmethod
    async def fetch(
            cls, user: hikari.SnowflakeishOr[hikari.PartialUser], guild: hikari.SnowflakeishOr[hikari.PartialGuild]
    ) -> DatabaseGuildUser:
        """Fetch a user from the database. If not present, returns a default DatabaseUser object.

        Parameters
        ----------
        user : hikari.SnowflakeishOr[hikari.PartialUser]
            The user to retrieve database information for.
        guild : hikari.SnowflakeishOr[hikari.PartialGuild]
            The guild the user belongs to.

        Returns
        -------
        DatabaseUser
            An object representing stored user data.
        """

        record = await cls.db.fetchrow(
            """SELECT * FROM guild_users WHERE user_id = $1 AND guild_id = $2""",
            hikari.Snowflake(user),
            hikari.Snowflake(guild),
        )

        if not record:
            return DatabaseGuildUser(hikari.Snowflake(user), hikari.Snowflake(guild), experience=0)

        return DatabaseGuildUser(
            id=record.get("id"),
            user_id=hikari.Snowflake(record.get("user_id")),
            guild_id=hikari.Snowflake(record.get("guild_id")),
            experience=record.get("experience"),
        )

    @classmethod
    async def fetch_all(cls, guild: hikari.SnowflakeishOr[hikari.PartialGuild]) -> typing.List[DatabaseGuildUser]:
        """Fetch all stored user data that belongs to the specified guild.

        Parameters
        ----------
        guild : hikari.SnowflakeishOr[hikari.PartialGuild]
            The guild the users belongs to.

        Returns
        -------
        List[DatabaseUser]
            A list of objects representing stored user data.
        """

        records = await cls.db.fetch("""SELECT * FROM guild_users WHERE guild_id = $1""", hikari.Snowflake(guild))

        if not records:
            return []

        return [
            DatabaseGuildUser(
                id=record.get("id"),
                user_id=hikari.Snowflake(record.get("user_id")),
                guild_id=hikari.Snowflake(record.get("guild_id")),
                experience=record.get("experience"),
            )
            for record in records
        ]
