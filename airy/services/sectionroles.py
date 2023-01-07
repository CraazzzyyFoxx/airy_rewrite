import asyncio
import typing
from enum import IntEnum

import hikari
from loguru import logger

from airy.models import HierarchyRoles, DatabaseSectionRole

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


class SectionRolesService:
    bot: "Airy" = None

    @classmethod
    async def on_role_delete(cls, event: hikari.RoleDeleteEvent):
        models = await DatabaseSectionRole.fetch_all(event.guild_id)

        for model in models:
            if model.role_id == event.role_id:
                await model.delete()

    @classmethod
    async def process_change_role(cls):
        pass

    @classmethod
    async def on_member_update(cls, event: hikari.MemberUpdateEvent):
        if event.member is None or event.old_member is None or len(event.member.role_ids) < 1:
            return

        changed_role = ChangedRole(event)
        if changed_role.id is None:
            return

        role_models = await DatabaseSectionRole.fetch_all(event.guild_id)

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

    @classmethod
    async def check_all_member(cls, model: DatabaseSectionRole):
        pass

    # API

    @classmethod
    async def get(cls,
                  guild_id: int,
                  role_id: int) -> typing.Optional[DatabaseSectionRole]:
        model = await DatabaseSectionRole.fetch(guild_id, role_id)
        if not model:
            return None
        logger.info(f"SectionRole get (id: {model.role_id} entries: {len(model.entries)}) in guild {model.guild_id}")

        return model

    @classmethod
    async def create(cls,
                     guild_id: int,
                     role_id: int,
                     entries_id: list[int],
                     hierarchy: HierarchyRoles
                     ) -> typing.Optional[DatabaseSectionRole]:
        """

        :param guild_id:
        :param role_id:
        :param entries_id:
        :param hierarchy:
        :return:
        """
        model = await DatabaseSectionRole.fetch(guild_id, role_id)

        if model:
            return None

        model = await DatabaseSectionRole.create(guild=guild_id, role=role_id, hierarchy=hierarchy, entries=entries_id)
        logger.info(f"SectionRole created (id: {model.role_id} entries: {len(model.entries)}) in guild {model.guild_id}")

        return model

    @classmethod
    async def update(cls,
                     guild_id: int,
                     role_id: int,
                     entries_id: list[int] = None,
                     hierarchy: HierarchyRoles = None,
                     delete_roles: bool = False
                     ) -> typing.Optional[DatabaseSectionRole]:
        """

        :param guild_id:
        :param role_id:
        :param entries_id:
        :param hierarchy:
        :param delete_roles:
        :return:
        """
        model = await DatabaseSectionRole.fetch(guild=guild_id, role=role_id)

        if not model:
            return None

        if hierarchy is not None and hierarchy != model.hierarchy:
            model.hierarchy = hierarchy
            await model.update()

        if entries_id:
            need_add = set(entries_id) - set([e.entry_id for e in model.entries])
            need_remove = set(entries_id) - need_add
            if delete_roles:
                async with asyncio.TaskGroup() as tg:
                    for entry_id in need_remove:
                        tg.create_task(cls.bot.rest.delete_role(guild_id, entry_id))

            await model.remove_entries(list(need_remove))
            await model.add_entries(list(need_add))
        logger.info(f"SectionRole updated (id: {model.role_id} entries: {len(model.entries)}) in guild {model.guild_id}")

        return model

    @classmethod
    async def delete(cls,
                     guild_id: int,
                     role_id: int,
                     delete_roles: bool = False
                     ) -> typing.Optional[DatabaseSectionRole]:
        """

        :param guild_id:
        :param role_id:
        :param delete_roles:
        :return:
        """
        model = await DatabaseSectionRole.fetch(guild=guild_id, role=role_id)

        if not model:
            return None
        await model.delete()

        if delete_roles:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(cls.bot.rest.delete_role(guild_id, model.role_id))
                for entry in model.entries:
                    tg.create_task(cls.bot.rest.delete_role(guild_id, entry.entry_id))

        logger.info(f"SectionRole deleted (id: {model.role_id} entries: {len(model.entries)}) in guild {model.guild_id}")
        return model

    @classmethod
    def on_startup(cls, bot: "Airy"):
        cls.bot = bot
        bot.subscribe(hikari.MemberUpdateEvent, cls.on_member_update)
        bot.subscribe(hikari.RoleDeleteEvent, cls.on_role_delete)

        logger.info(f"Service {cls.__name__} started")

    @classmethod
    def on_shutdown(cls, bot: "Airy"):
        bot.unsubscribe(hikari.MemberUpdateEvent, cls.on_member_update)
        bot.unsubscribe(hikari.RoleDeleteEvent, cls.on_role_delete)

    @classmethod
    def setup(cls, bot: "Airy"):
        cls.on_startup(bot)


def load(bot: "Airy"):
    SectionRolesService.setup(bot)


def unload(bot: "Airy"):
    SectionRolesService.on_shutdown(bot)
