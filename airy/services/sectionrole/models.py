from __future__ import annotations

from enum import IntEnum

from pydantic import fields

import hikari

from tortoise import Model, fields

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
    def to_choices(cls) -> list[hikari.CommandChoice]:
        return [hikari.CommandChoice(name=name, value=str(value.value)) for name, value in cls._member_map_.items()]


class DatabaseSectionRole(Model):
    id: int = fields.IntField(pk=True)
    guild_id: int = fields.BigIntField()
    role_id: int = fields.BigIntField(unique=True)
    hierarchy: HierarchyRoles = fields.IntEnumField(HierarchyRoles)

    entries: fields.ReverseRelation["DatabaseEntrySectionRole"]

    class Meta:
        """Metaclass to set table name and description"""

        table = "sectionrole"


class DatabaseEntrySectionRole(Model):
    id: int = fields.IntField(pk=True)
    entry_id: int = fields.BigIntField()
    role: int = fields.ForeignKeyField("main.DatabaseSectionRole", related_name="entries", to_field="role_id")

    class Meta:
        """Metaclass to set table name and description"""

        table = "sectionrole_entry"
