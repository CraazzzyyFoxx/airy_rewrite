import typing

from enum import IntEnum

import hikari
import lightbulb

from loguru import logger
from starlette import status

from airy.services import BaseService
from airy.utils import helpers

from .models import HierarchyRoles, DatabaseSectionRole, DatabaseEntrySectionRole

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


class ChangedRoleStatus(IntEnum):
    ADDED = 0
    REMOVED = 1


class ChangedRole(BaseService):
    def __init__(self, event: hikari.MemberUpdateEvent):
        raw = set(event.member.role_ids) - set(event.old_member.role_ids)
        if len(raw) == 1:
            self.id = int(raw.pop())
            self.status = ChangedRoleStatus.ADDED
        else:
            raw = set(event.old_member.role_ids) - set(event.member.role_ids)
            if len(raw) == 1:
                self.status = ChangedRoleStatus.REMOVED
                self.id = int(raw.pop())
            else:
                self.id = None
                self.status = None


class SectionRolesService(BaseService):
    @classmethod
    async def on_startup(cls, event: hikari.StartedEvent):
        cls.bot.subscribe(hikari.MemberUpdateEvent, cls.on_member_update)
        cls.bot.subscribe(hikari.RoleDeleteEvent, cls.on_role_delete)

    @classmethod
    async def on_shutdown(cls, event: hikari.StoppedEvent = None):
        cls.bot.unsubscribe(hikari.MemberUpdateEvent, cls.on_member_update)
        cls.bot.unsubscribe(hikari.RoleDeleteEvent, cls.on_role_delete)

    @classmethod
    async def on_role_delete(cls, event: hikari.RoleDeleteEvent):
        sc_roles: list[DatabaseSectionRole] = (await DatabaseSectionRole
                                               .filter(guild_id=event.guild_id)
                                               .prefetch_related("entries"))

        for sc_role in sc_roles:
            if sc_role.role_id == event.role_id:
                await sc_role.delete()
            else:
                for entry in sc_role.entries:
                    if event.role_id == entry.entry_id:
                        await entry.delete()

    @classmethod
    async def on_member_update(cls, event: hikari.MemberUpdateEvent):
        me = cls.bot.cache.get_member(event.guild_id, cls.bot.user_id)

        if not me:
            return

        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.MANAGE_ROLES):
            return None
        if event.member is None or event.old_member is None or len(event.member.role_ids) < 1:
            return

        changed_role = ChangedRole(event)
        if changed_role.id is None:
            return

        role_models: list[DatabaseSectionRole] = (await DatabaseSectionRole
                                                  .filter(guild_id=event.guild_id)
                                                  .prefetch_related("entries"))

        for role_model in role_models:
            entries = {entry.entry_id for entry in role_model.entries}
            diff = entries - set(event.member.role_ids)
            group_role = cls.bot.cache.get_role(role_model.role_id)

            if not group_role:
                return

            # Если нет необходимой одной роли, то удаляем секционную роль
            if diff == entries:
                await cls._remove_role(event.member, role_model.role_id)
            else:
                # Ветка TopDown. Если есть роль выше секционной, то добавляем
                if role_model.hierarchy == HierarchyRoles.TopDown:
                    if group_role.position < event.member.get_top_role().position:
                        await cls._add_role(event.member, role_model.role_id)
                    else:
                        await cls._remove_role(event.member, role_model.role_id)

                # Если роль, которая изменилась секционная, то добавляем
                elif role_model.hierarchy == HierarchyRoles.Missing:
                    await cls._add_role(event.member, role_model.role_id)

                elif role_model.hierarchy == HierarchyRoles.BottomTop:
                    # Если секционная роль не самая низкая, то добавляем
                    min_role = sorted(event.member.get_roles(), key=lambda r: r.position)[1]
                    if group_role.position > min_role.position:
                        await cls._add_role(event.member, role_model.role_id)
                    else:
                        await cls._remove_role(event.member, role_model.role_id)

    @classmethod
    async def _add_role(cls, member: hikari.Member, role_id: hikari.Snowflake):
        if role_id not in member.role_ids:
            await member.add_role(role_id)

            logger.debug("SectionRole {} added from member {} in guild {}",
                         role_id,
                         member.id,
                         member.guild_id)

    @classmethod
    async def _remove_role(cls, member: hikari.Member, role_id: hikari.Snowflake):
        if role_id in member.role_ids:
            await member.remove_role(role_id)

            logger.debug("SectionRole {} removed from member {} in guild {}",
                         role_id,
                         member.id,
                         member.guild_id)

    # API
    @classmethod
    async def get(
            cls,
            guild_id: hikari.Snowflake,
            role_id: hikari.Snowflake
    ) -> tuple[int, DatabaseSectionRole | None]:
        model: DatabaseSectionRole = (await DatabaseSectionRole
                                      .filter(guild_id=guild_id, role_id=role_id)
                                      .first()
                                      .prefetch_related("entries"))

        if model:
            return status.HTTP_200_OK, model
        return status.HTTP_404_NOT_FOUND, None

    @classmethod
    async def get_all(
            cls,
            guild_id: hikari.Snowflake,
    ) -> tuple[int, list[DatabaseSectionRole]]:
        models = (await DatabaseSectionRole
                  .filter(guild_id=guild_id)
                  .prefetch_related("entries").all()
                  )
        if models:
            return status.HTTP_200_OK, models
        return status.HTTP_404_NOT_FOUND, []

    @classmethod
    async def create(
            cls,
            guild_id: hikari.Snowflake,
            role_id: hikari.Snowflake,
            entries_id: list[hikari.Snowflake],
            hierarchy: HierarchyRoles
    ) -> tuple[int, DatabaseSectionRole | None]:
        model: DatabaseSectionRole = (await DatabaseSectionRole
                                      .filter(guild_id=guild_id, role_id=role_id)
                                      .prefetch_related("entries").first())
        if model:
            return status.HTTP_400_BAD_REQUEST, None
        model = await DatabaseSectionRole.create(guild_id=guild_id, role_id=role_id, hierarchy=hierarchy)

        await DatabaseEntrySectionRole.bulk_create([DatabaseEntrySectionRole(role_id=role_id,
                                                                             entry_id=entry_id)
                                                    for entry_id in entries_id])

        logger.info("SectionRole created (id: {} entries: {}) in guild {}",
                    model.role_id,
                    len(model.entries),
                    model.guild_id
                    )

        return status.HTTP_201_CREATED, model

    @classmethod
    async def update(
            cls,
            guild_id: hikari.Snowflake,
            role_id: hikari.Snowflake,
            entries_id: list[hikari.Snowflake] = None,
            hierarchy: HierarchyRoles = None,
    ) -> tuple[int, DatabaseSectionRole | None]:
        model: DatabaseSectionRole = (await DatabaseSectionRole
                                      .filter(guild_id=guild_id, role_id=role_id)
                                      .first()
                                      .prefetch_related("entries"))

        if not model:
            return status.HTTP_400_BAD_REQUEST, None

        if hierarchy is not None and hierarchy != model.hierarchy:
            model.hierarchy = hierarchy
            await model.save()

        if entries_id:
            need_add = set(entries_id) - set([e.entry_id for e in model.entries])
            need_remove = set(entries_id) - need_add

            for entry in model.entries:
                if entry.entry_id in need_remove:
                    await entry.delete()
            await DatabaseEntrySectionRole.bulk_create([DatabaseEntrySectionRole(role_id=role_id,
                                                                                 entry_id=entry_id)
                                                        for entry_id in need_add])
        logger.info("SectionRole updated (id: {} entries: {}) in guild {}",
                    model.role_id,
                    len(model.entries),
                    model.guild_id
                    )

        s, model = await cls.get(guild_id, role_id)
        return status.HTTP_200_OK, model

    @classmethod
    async def delete(
            cls,
            guild_id: hikari.Snowflake,
            role_id: hikari.Snowflake,
    ) -> tuple[int, DatabaseSectionRole | None]:
        """

        :param guild_id:
        :param role_id:
        :return:
        """

        model: DatabaseSectionRole = (await DatabaseSectionRole
                                      .filter(guild_id=guild_id, role_id=role_id)
                                      .first()
                                      .prefetch_related("entries"))

        if not model:
            return status.HTTP_400_BAD_REQUEST, None
        await model.delete()

        logger.info("SectionRole deleted (id: {} entries: {}) in guild {}",
                    model.role_id,
                    len(model.entries),
                    model.guild_id
                    )

        return status.HTTP_200_OK, model


def load(bot: "Airy"):
    SectionRolesService.start(bot)


def unload(bot: "Airy"):
    SectionRolesService.shutdown(bot)
