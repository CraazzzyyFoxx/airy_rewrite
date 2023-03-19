from __future__ import annotations

import asyncio
import typing

import hikari
import miru

from fuzzywuzzy import process

from airy.models.context import AirySlashContext
from airy.models.views import MenuViewAuthorOnly
from airy.services.sectionrole import SectionRolesService, DatabaseSectionRole, HierarchyRoles
from airy.etc import ColorEnum, MenuEmojiEnum
from airy.utils import utcnow, helpers, RespondEmbed


class RoleModal(miru.Modal):
    def __init__(self, ) -> None:
        super().__init__("Enter Role")
        self.data: str | None = None
        self.item = miru.TextInput(label="Role (name or id)",
                                   placeholder="For example: Airy or 947964654230052876")
        self.add_item(self.item)

    async def callback(self, ctx: miru.ModalContext) -> None:
        self.data = ctx.values[self.item]


class HierarchyModal(miru.Modal):
    def __init__(self):
        super().__init__("Hierarchy role")
        self.data: str | None = None
        self.item = miru.TextInput(label="Hierarchy (Missing, TopDown, BottomTop)",
                                   placeholder="For example: TopDown")
        self.add_item(self.item)

    async def callback(self, ctx: miru.ModalContext) -> None:
        self.data = ctx.values[self.item]


class MenuView(MenuViewAuthorOnly):
    def __init__(self, ctx: AirySlashContext, model: DatabaseSectionRole):
        super().__init__(ctx)
        self.model = model
        self.role = ctx.bot.cache.get_role(model.role_id)
        for item in self.default_buttons:
            self.add_item(item)

    @property
    def default_buttons(self):
        return [
            AddRemoveRoleButton(style=hikari.ButtonStyle.SECONDARY, emoji=MenuEmojiEnum.ADD),
            AddRemoveRoleButton(style=hikari.ButtonStyle.SECONDARY, emoji=MenuEmojiEnum.REMOVE),
            ChangeHierarchyButton(),
            DeleteButton(),
            QuitButton()
        ]

    def get_kwargs(self, model: DatabaseSectionRole):
        embed = hikari.Embed(title=f"{self.role.name}",
                             color=ColorEnum.teal,
                             timestamp=utcnow())
        entries_description = [f"**Hierarchy**: `{model.hierarchy.name}` \n"]

        for index, entry in enumerate(model.entries, 1):
            entry_role = self.ctx.bot.cache.get_role(entry.entry_id)
            entries_description.append(f"**{index}.** {entry_role.mention} (ID: {entry_role.id})")

        embed.description = '\n'.join(entries_description)
        return dict(embed=embed, components=self.build())

    async def send(self, ctx: typing.Union[miru.ViewContext, miru.ModalContext]):
        kwargs = self.get_kwargs(self.model)
        await ctx.edit_response(**kwargs)

    async def initial_send(self) -> None:
        kwargs = self.get_kwargs(self.model)
        await self.ctx.interaction.create_initial_response(hikari.ResponseType.MESSAGE_CREATE, **kwargs)
        message = await self.ctx.interaction.fetch_initial_response()
        await super(MenuView, self).start(message)


ViewT = typing.TypeVar("ViewT", bound=MenuView)


class AddRemoveRoleButton(miru.Button):
    def __init__(self, style: hikari.ButtonStyle, emoji: MenuEmojiEnum):
        super().__init__(label="Role", style=style, emoji=emoji)

    async def callback(self, context: miru.ViewContext) -> None:
        modal = RoleModal()
        await context.respond_with_modal(modal)
        await modal.wait()
        role = await helpers.parse_role(context, modal.data)

        if role:
            status, model = await SectionRolesService.update(guild_id=role.guild_id,
                                                             role_id=self.view.role.id,
                                                             entries_id=[role.id])
            self.view.model = model
        await self.view.send(modal.last_context)


class DeleteButton(miru.Button):
    def __init__(self):
        super().__init__(label="Delete", style=hikari.ButtonStyle.DANGER, emoji=MenuEmojiEnum.TRASHCAN)

    async def callback(self, context: miru.ViewContext) -> None:
        status, model = await SectionRolesService.delete(guild_id=self.view.role.guild_id,
                                                         role_id=self.view.role.id)
        await context.edit_response(embed=RespondEmbed.success("Group role was deleted"),
                                    components=[])
        self.view.stop()


class ChangeHierarchyButton(miru.Button):
    def __init__(self) -> None:
        super().__init__(style=hikari.ButtonStyle.SECONDARY, label="Change Hierarchy")

    async def callback(self, context: miru.ViewContext) -> None:
        modal = HierarchyModal()
        await context.respond_with_modal(modal)
        await modal.wait()
        hierarchy = await asyncio.threads.to_thread(process.extractOne, modal.data,
                                                    choices=[name for name in HierarchyRoles._member_map_.keys()])
        if not hierarchy:
            hierarchy = HierarchyRoles.Missing
        else:
            hierarchy = HierarchyRoles.try_name(hierarchy[0])
        status, model = await SectionRolesService.update(guild_id=self.view.role.guild_id,
                                                         role_id=self.view.role.id,
                                                         hierarchy=hierarchy)
        self.view.model = model
        await self.view.send(modal.last_context)


class QuitButton(miru.Button):
    def __init__(self) -> None:
        super().__init__(style=hikari.ButtonStyle.SECONDARY, label="Quit", emoji=MenuEmojiEnum.SAVE)

    async def callback(self, context: miru.ViewContext) -> None:
        for item in self.view.children:
            item.disabled = True

        kwargs = self.view.get_kwargs(self.view.model)
        await context.edit_response(**kwargs)
        self.view.stop()
