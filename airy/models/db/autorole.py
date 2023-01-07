from __future__ import annotations

import attr
import hikari

from airy.models.db.impl import DatabaseModel


@attr.define()
class DatabaseAutoRole(DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    role_id: hikari.Snowflake


@attr.define()
class DatabaseAutoRoleForMember(DatabaseModel):
    id: int
    guild_id: hikari.Snowflake
    role_id: hikari.Snowflake
