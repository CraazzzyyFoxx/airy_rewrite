from __future__ import annotations

import attr
import hikari

from airy.models.db.impl import DatabaseModel


@attr.define()
class DatabaseBlacklist(DatabaseModel):
    """Defining a blacklist model to blacklist"""

    id: int
    entry_id: hikari.Snowflake

    @classmethod
    async def create(cls, entry: hikari.SnowflakeishOr):
        pass

    @classmethod
    async def fetch_all(cls):
        pass

    @classmethod
    async def fetch(cls, entry_id: hikari.Snowflake):
        record = await cls.db.fetchrow("select * from blacklist where entry_id=$1", entry_id)
        if not record:
            return None
        return DatabaseBlacklist(id=record.get("id"), entry_id=entry_id)

    async def delete(self):
        await self.db.execute("delete from blacklist where id=$1 and entry_id=$2",
                               self.id,
                               self.entry_id)
