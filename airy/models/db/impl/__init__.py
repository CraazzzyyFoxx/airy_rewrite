from __future__ import annotations

import abc
import typing as t
from contextlib import asynccontextmanager

import asyncpg  # type: ignore
import hikari

from loguru import logger

from airy.config import db_config
from airy.models.errors import DatabaseStateConflictError

if t.TYPE_CHECKING:
    from airy.models.bot import Airy


class Database:
    """A database object that wraps an asyncpg pool and provides additional methods for convenience."""

    def __init__(self, app: Airy) -> None:
        self._app: Airy = app
        self._config = db_config
        self._pool: t.Optional[asyncpg.Pool] = None
        self._is_closed: bool = False

        DatabaseModel.db = self
        DatabaseModel.app = self.app

    @property
    def app(self) -> Airy:
        """The currently running application."""
        return self._app

    @property
    def user(self) -> str:
        """The currently authenticated database user."""
        return self._config.user

    @property
    def host(self) -> str:
        """The database hostname the database is connected to."""
        return self._config.host

    @property
    def db_name(self) -> str:
        """The name of the database this object is connected to."""
        return self._config.db

    @property
    def port(self) -> int:
        """The connection port to use when connecting to the database."""
        return self._config.port

    @property
    def password(self) -> str:
        """The database password to use when authenticating."""
        return self._config.password

    @property
    def version(self) -> t.Optional[str]:
        """The version of PostgreSQL used. May be None if not explicitly specified."""
        return self._config.version

    @property
    def dsn(self) -> str:
        """The connection URI used to connect to the database."""
        return f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"

    async def connect(self) -> None:
        """Start a new connection and create a connection pool."""
        if self._is_closed:
            raise DatabaseStateConflictError("The database is closed.")

        logger.info("Connecting to Database...")
        self._pool = await asyncpg.create_pool(dsn=self.dsn)
        logger.info("Connected to Database.")

    async def close(self) -> None:
        """Close the connection pool."""
        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")
        if self._is_closed:
            raise DatabaseStateConflictError("The database is closed.")

        await self._pool.close()
        self._is_closed = True
        logger.info("Closed database connection.")

    def terminate(self) -> None:
        """Terminate the connection pool."""
        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")
        if self._is_closed:
            raise DatabaseStateConflictError("The database is closed.")

        self._pool.terminate()
        self._is_closed = True

    @asynccontextmanager
    async def acquire(self) -> t.AsyncIterator[asyncpg.Connection]:
        """Acquire a database connection from the connection pool."""
        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")

        con = await self._pool.acquire()
        try:
            yield con
        finally:
            await self._pool.release(con)

    async def execute(self, query: str, *args, timeout: t.Optional[float] = None) -> str:
        """Execute an SQL command.

        Parameters
        ----------
        query : str
            The SQL query to run.
        timeout : Optional[float], optional
            The timeout in seconds, by default None

        Returns
        -------
        str
            The SQL return code.

        Raises
        ------
        DatabaseStateConflictError
            The application is not connected to the database server.
        """

        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")

        return await self._pool.execute(query, *args, timeout=timeout)  # type: ignore

    async def fetch(self, query: str, *args, timeout: t.Optional[float] = None) -> t.List[asyncpg.Record]:
        """Run a query and return the results as a list of `Record`.

        Parameters
        ----------
        query : str
            The SQL query to be ran.
        timeout : Optional[float], optional
            The timeout in seconds, by default None

        Returns
        -------
        List[asyncpg.Record]
            A list of records that matched the query parameters.

        Raises
        ------
        DatabaseStateConflictError
            The application is not connected to the database server.
        """
        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")

        return await self._pool.fetch(query, *args, timeout=timeout)

    async def executemany(self, command: str, args: t.Iterable[t.Any], *, timeout: t.Optional[float] = None) -> str:
        """Execute an SQL command for each sequence of arguments in `args`.

        Parameters
        ----------
        query : str
            The SQL query to run.
        args : Tuple[t.Any]
            Tuples of arguments to execute.
        timeout : Optional[float], optional
            The timeout in seconds, by default None

        Returns
        -------
        str
            The SQL return code.

        Raises
        ------
        DatabaseStateConflictError
            The application is not connected to the database server.
        """
        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")

        return await self._pool.executemany(command, args, timeout=timeout)  # type: ignore

    async def fetchrow(self, query: str, *args, timeout: t.Optional[float] = None) -> asyncpg.Record:
        """Run a query and return the first row that matched query parameters.

        Parameters
        ----------
        query : str
            The SQL query to be ran.
        timeout : t.Optional[float], optional
            The timeout in seconds, by default None

        Returns
        -------
        asyncpg.Record
            The record that matched query parameters.

        Raises
        ------
        DatabaseStateConflictError
            The application is not connected to the database server.
        """
        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")

        return await self._pool.fetchrow(query, *args, timeout=timeout)

    async def fetchval(self, query: str, *args, column: int = 0, timeout: t.Optional[float] = None) -> t.Any:
        """Run a query and return a value in the first row that matched query parameters.

        Parameters
        ----------
        query : str
            The SQL query to be ran.
        timeout : t.Optional[float], optional
            The timeout in seconds, by default None
        column : int

        Returns
        -------
        Any
            The value that matched the query parameters.

        Raises
        ------
        DatabaseStateConflictError
            The application is not connected to the database server.
        """
        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")

        return await self._pool.fetchval(query, *args, column=column, timeout=timeout)

    async def wipe_guild(self, guild: hikari.SnowflakeishOr[hikari.PartialGuild], *, keep_record: bool = True) -> None:
        if not self._pool:
            raise DatabaseStateConflictError("The database is not connected.")

        async with self.acquire() as con:
            await con.execute("""DELETE FROM guild WHERE guild_id = $1""", hikari.Snowflake(guild))
            if keep_record:
                await con.execute("""INSERT INTO guild (guild_id) VALUES ($1)""", hikari.Snowflake(guild))


class DatabaseModel(abc.ABC):
    """Common base-class for all database model objects."""

    db: Database
    app: Airy
