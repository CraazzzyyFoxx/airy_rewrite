from __future__ import annotations

import typing

import hikari
import lightbulb

from airy.models import AiryPlugin, AirySlashContext
from airy.utils import RespondEmbed, SimplePages

from airy.services.autoroles import AutoRolesService

auto_role_plugin = AiryPlugin('AutoRoles')
auto_role_plugin.add_checks(lightbulb.guild_only)


if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


@auto_role_plugin.command()
@lightbulb.add_checks(
    lightbulb.checks.has_guild_permissions(hikari.Permissions.MANAGE_ROLES, hikari.Permissions.MODERATE_MEMBERS),
    lightbulb.checks.bot_has_guild_permissions(hikari.Permissions.MANAGE_ROLES, hikari.Permissions.MODERATE_MEMBERS),
)
@lightbulb.command("autorole",
                   "Shows which roles will be added upon joining")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def auto_role_cmd(_: AirySlashContext):
    pass


@auto_role_cmd.child()
@lightbulb.option('role', 'Autorole that will be issued when the condition is triggered ',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("add", "Adds the role to be automatically assigned", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def auto_role_create(ctx: AirySlashContext, role: hikari.Role):
    try:
        _ = await AutoRolesService.create(ctx.guild_id, role)
    except ValueError:
        return await ctx.respond(embed=RespondEmbed.error("The specified group role already exists"),
                                 flags=hikari.MessageFlag.EPHEMERAL)

    await ctx.respond(embed=RespondEmbed.success('Successfully added.',
                                                 description=f'{role.mention} (ID: {role.id})'))


@auto_role_cmd.child()
@lightbulb.option('role', 'Please input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("remove", "Removes the role from being automatically assigned", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def auto_role_remove(ctx: AirySlashContext, role: hikari.Role):
    try:
        await AutoRolesService.delete(ctx.guild_id, role)
    except ValueError:
        return await ctx.respond(embed=RespondEmbed.error("Autorole does not exist "),
                                 flags=hikari.MessageFlag.EPHEMERAL)

    await ctx.respond(embed=RespondEmbed.success('Successfully removed.'))


@auto_role_cmd.child()
@lightbulb.command("show", "Show all registered autorol on this server.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def auto_role_list(ctx: AirySlashContext):
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    models = await AutoRolesService.get_all_for_guild(ctx.guild_id)
    if len(models) == 0:
        return await ctx.respond(embed=RespondEmbed.error("No automatic roles",
                                                          description="Use /autorole add to add a new role"))
    entries = []
    for index, model in enumerate(models, 1):
        role = ctx.bot.cache.get_role(model.role_id)
        entries.append(f'**{index}.** {role.mention} (ID: {role.id})')

    pages = SimplePages(entries, ctx=ctx)
    await pages.send(ctx.interaction, responded=True)


def load(bot: "Airy") -> None:
    bot.add_plugin(auto_role_plugin)


def unload(bot: "Airy") -> None:
    bot.remove_plugin(auto_role_plugin)
