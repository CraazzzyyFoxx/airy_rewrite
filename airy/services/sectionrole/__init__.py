import typing

from enum import IntEnum

import hikari
import lightbulb

from loguru import logger

from airy.services import BaseService
from airy.utils import helpers

from .models import HierarchyRoles, DatabaseSectionRole
from ...models import errors

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


class ChangedRoleStatus(IntEnum):
    ADDED = 0
    REMOVED = 1


class ChangedRole:
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


class SectionRolesServiceT(BaseService):
    async def on_startup(self, event: hikari.StartedEvent):
        self.bot.subscribe(hikari.MemberUpdateEvent, self.on_member_update)
        self.bot.subscribe(hikari.RoleDeleteEvent, self.on_role_delete)

    async def on_shutdown(self, event: hikari.StoppedEvent = None):
        self.bot.unsubscribe(hikari.MemberUpdateEvent, self.on_member_update)
        self.bot.unsubscribe(hikari.RoleDeleteEvent, self.on_role_delete)

    async def on_role_delete(self, event: hikari.RoleDeleteEvent):
        models: list[DatabaseSectionRole] = await DatabaseSectionRole.fetch_all(event.guild_id)

        for model in models:
            if model.role_id == event.role_id:
                await model.delete()
            else:
                logger.warning([entry.entry_id for entry in model.entries
                                            if event.role_id == entry.entry_id])
                await model.remove_entries([entry.entry_id for entry in model.entries
                                            if event.role_id == entry.entry_id])

    async def on_member_update(self, event: hikari.MemberUpdateEvent):
        me = self.bot.cache.get_member(event.guild_id, self.bot.user_id)

        if not me:
            return

        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.MANAGE_ROLES):
            return None
        if event.member is None or event.old_member is None or len(event.member.role_ids) < 1:
            return

        changed_role = ChangedRole(event)
        if changed_role.id is None:
            return

        role_models: list[DatabaseSectionRole] = await DatabaseSectionRole.fetch_all(event.guild_id)

        for role_model in role_models:
            entries = {entry.entry_id for entry in role_model.entries}
            diff = entries - set(event.member.role_ids)
            group_role = self.bot.cache.get_role(role_model.role_id)

            if not group_role:
                return

            # Если нет необходимой одной роли, то удаляем секционную роль
            if diff == entries:
                await self._remove_role(event.member, role_model.role_id)
            else:
                # Ветка TopDown. Если есть роль выше секционной, то добавляем
                if role_model.hierarchy == HierarchyRoles.TopDown:
                    if group_role.position < event.member.get_top_role().position:
                        await self._add_role(event.member, role_model.role_id)
                    else:
                        await self._remove_role(event.member, role_model.role_id)

                # Если роль, которая изменилась секционная, то добавляем
                elif role_model.hierarchy == HierarchyRoles.Missing:
                    await self._add_role(event.member, role_model.role_id)

                elif role_model.hierarchy == HierarchyRoles.BottomTop:
                    # Если секционная роль не самая низкая, то добавляем
                    min_role = sorted(event.member.get_roles(), key=lambda r: r.position)[1]
                    if group_role.position > min_role.position:
                        await self._add_role(event.member, role_model.role_id)
                    else:
                        await self._remove_role(event.member, role_model.role_id)

    async def _add_role(self, member: hikari.Member, role_id: hikari.Snowflake):
        if role_id not in member.role_ids:
            await member.add_role(role_id)

            logger.debug("SectionRole {} added from member {} in guild {}",
                         role_id,
                         member.id,
                         member.guild_id)

    async def _remove_role(self, member: hikari.Member, role_id: hikari.Snowflake):
        if role_id in member.role_ids:
            await member.remove_role(role_id)

            logger.debug("SectionRole {} removed from member {} in guild {}",
                         role_id,
                         member.id,
                         member.guild_id)

    # API

    async def get(
            self,
            guild_id: hikari.Snowflake,
            role_id: hikari.Snowflake
    ) -> typing.Optional[DatabaseSectionRole]:
        """

        :param guild_id:
        :param role_id:
        :return:

        :raise: RoleDoesNotExist
            If the role not found
        """

        model: DatabaseSectionRole = await DatabaseSectionRole.fetch(guild_id, role_id)
        logger.info(f"SectionRole get (id: {model.role_id} entries: {len(model.entries)}) in guild {model.guild_id}")

        return model

    async def create(
            self,
            guild_id: hikari.Snowflake,
            role_id: hikari.Snowflake,
            entries_id: list[hikari.Snowflake],
            hierarchy: HierarchyRoles
    ) -> DatabaseSectionRole:
        """

        :param guild_id:
        :param role_id:
        :param entries_id:
        :param hierarchy:
        :return:

        :raise: RoleAlreadyExists
            If the role not found
        """
        try:
            model: DatabaseSectionRole = await DatabaseSectionRole.fetch(guild_id, role_id)
        except errors.RoleDoesNotExist:
            model = await DatabaseSectionRole.create(guild_id, role_id, hierarchy, entries_id)
            logger.info("SectionRole created (id: {} entries: {}) in guild {}",
                        model.role_id,
                        len(model.entries),
                        model.guild_id
                        )

            return model

        raise errors.RoleAlreadyExists()

    async def update(
            self,
            guild_id: hikari.Snowflake,
            role_id: hikari.Snowflake,
            entries_id: list[hikari.Snowflake] = None,
            hierarchy: HierarchyRoles = None,
    ) -> typing.Optional[DatabaseSectionRole]:
        """

        :param guild_id:
        :param role_id:
        :param entries_id:
        :param hierarchy:
        :return:
        """

        model: DatabaseSectionRole = await DatabaseSectionRole.fetch(guild_id, role_id)

        if not model:
            return None

        if hierarchy is not None and hierarchy != model.hierarchy:
            model.hierarchy = hierarchy
            await model.update()

        if entries_id:
            need_add = set(entries_id) - set([e.entry_id for e in model.entries])
            need_remove = set(entries_id) - need_add

            await model.remove_entries(list(need_remove))
            await model.add_entries(list(need_add))
        logger.info("SectionRole updated (id: {} entries: {}) in guild {}",
                    model.role_id,
                    len(model.entries),
                    model.guild_id
                    )

        return model

    async def delete(
            self,
            guild_id: hikari.Snowflake,
            role_id: hikari.Snowflake,
    ) -> typing.Optional[DatabaseSectionRole]:
        """

        :param guild_id:
        :param role_id:
        :return:
        """

        model: DatabaseSectionRole = await DatabaseSectionRole.fetch(guild_id, role_id)

        if not model:
            return None
        await model.delete()

        logger.info("SectionRole deleted (id: {} entries: {}) in guild {}",
                    model.role_id,
                    len(model.entries),
                    model.guild_id
                    )
        return model


SectionRolesService = SectionRolesServiceT()


def load(bot: "Airy"):
    SectionRolesService.start(bot)


def unload(bot: "Airy"):
    SectionRolesService.shutdown(bot)
