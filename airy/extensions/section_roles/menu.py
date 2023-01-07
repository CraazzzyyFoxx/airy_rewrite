from __future__ import annotations

import typing as t

import hikari
import miru

from airy.models import AirySlashContext, DatabaseSectionRole, MenuViewAuthorOnly
from airy.services.sectionroles import SectionRolesService
from airy.static import ColorEnum, MenuEmojiEnum
from airy.utils import utcnow, helpers, RespondEmbed


class RoleModal(miru.Modal):
    def __init__(self, ) -> None:
        super().__init__("Enter Role")
        self.data: t.Optional[str] = None
        self.item = miru.TextInput(label="Role (name or id)",
                                   placeholder="For example: Airy or 947964654230052876")
        self.add_item(self.item)

    async def callback(self, ctx: miru.ModalContext) -> None:
        self.data = ctx.values[self.item]


class MenuView(MenuViewAuthorOnly):
    def __init__(self, ctx: AirySlashContext, role: hikari.Role):
        super().__init__(ctx)
        self.role = role
        for item in self.default_buttons:
            self.add_item(item)

    @property
    def default_buttons(self):
        return [AddRoleButton(), RemoveRoleButton(), DeleteButton(), QuitButton()]

    def get_kwargs(self, model: DatabaseSectionRole):
        embed = hikari.Embed(title=f"{self.role.name}",
                             color=ColorEnum.teal,
                             timestamp=utcnow())
        entries_description = []

        for index, entry in enumerate(model.entries, 1):
            entry_role = self.ctx.bot.cache.get_role(entry.entry_id)
            entries_description.append(f"**{index}.** {entry_role.mention} (ID: {entry_role.id})")

        embed.description = '\n'.join(entries_description)
        return dict(embed=embed, components=self.build())

    async def send(self, ctx: t.Union[miru.ViewContext, miru.ModalContext], model: DatabaseSectionRole):
        kwargs = self.get_kwargs(model)
        await ctx.edit_response(**kwargs)

    async def initial_send(self) -> None:
        model = await SectionRolesService.get(guild_id=self.ctx.guild_id, role_id=self.role.id)

        if not model:
            await self.ctx.respond(embed=RespondEmbed.error("The specified group role is missing"))
            return

        kwargs = self.get_kwargs(model)
        await self.ctx.interaction.create_initial_response(hikari.ResponseType.MESSAGE_CREATE, **kwargs)
        message = await self.ctx.interaction.fetch_initial_response()
        await super(MenuView, self).start(message)


ViewT = t.TypeVar("ViewT", bound=MenuView)


class AddRoleButton(miru.Button):
    def __init__(self):
        super().__init__(label="Role", style=hikari.ButtonStyle.SECONDARY, emoji=MenuEmojiEnum.ADD)

    async def callback(self, context: miru.ViewContext) -> None:
        modal = RoleModal()
        await context.respond_with_modal(modal)
        await modal.wait()
        role = await helpers.parse_role(context, modal.data)

        model = await SectionRolesService.update(guild_id=role.guild_id,
                                                 role_id=self.view.role.id,
                                                 entries_id=[role.id])

        await self.view.send(modal.last_context, model)


class RemoveRoleButton(miru.Button):
    def __init__(self):
        super().__init__(label="Role", style=hikari.ButtonStyle.SECONDARY, emoji=MenuEmojiEnum.REMOVE)

    async def callback(self, context: miru.ViewContext) -> None:
        modal = RoleModal()
        await context.respond_with_modal(modal)
        await modal.wait()
        role = await helpers.parse_role(context, modal.data)

        model = await SectionRolesService.update(guild_id=role.guild_id,
                                                 role_id=self.view.role.id,
                                                 entries_id=[role.id])

        await self.view.send(modal.last_context, model)


class DeleteButton(miru.Button):
    def __init__(self):
        super().__init__(label="Delete", style=hikari.ButtonStyle.DANGER, emoji=MenuEmojiEnum.TRASHCAN)

    async def callback(self, context: miru.ViewContext) -> None:
        model = await SectionRolesService.delete(guild_id=self.view.role.guild_id,
                                                 role_id=self.view.role.id)
        await context.edit_response(embed=RespondEmbed.success("Group role was deleted"),
                                    components=[])
        self.view.stop()


class QuitButton(miru.Button):
    def __init__(self) -> None:
        super().__init__(style=hikari.ButtonStyle.SECONDARY, label="Quit", emoji=MenuEmojiEnum.SAVE)

    async def callback(self, context: miru.ViewContext) -> None:
        for item in self.view.children:
            item.disabled = True
        model = await SectionRolesService.get(guild_id=context.guild_id, role_id=self.view.role.id)
        kwargs = self.view.get_kwargs(model)
        await context.edit_response(**kwargs)
        self.view.stop()
