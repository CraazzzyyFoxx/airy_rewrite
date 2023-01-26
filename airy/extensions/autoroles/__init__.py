from __future__ import annotations

import typing

import hikari
import lightbulb

from airy.models import AiryPlugin, AirySlashContext, errors
from airy.utils import RespondEmbed, SimplePages, to_str_permissions, PermissionsErrorEmbed

from airy.services.autorole import AutoRolesService

auto_role_plugin = AiryPlugin('AutoRoles')
auto_role_plugin.add_checks(lightbulb.guild_only)
auto_role_plugin.add_checks(lightbulb.checks.has_guild_permissions(hikari.Permissions.MANAGE_ROLES,
                                                                   hikari.Permissions.MODERATE_MEMBERS))
auto_role_plugin.add_checks(lightbulb.checks.bot_has_guild_permissions(hikari.Permissions.MANAGE_ROLES,
                                                                       hikari.Permissions.MODERATE_MEMBERS))

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


@auto_role_plugin.command()
@lightbulb.command("autorole",
                   "Shows which roles will be added upon joining",
                   app_command_default_member_permissions=(hikari.Permissions.MODERATE_MEMBERS
                                                           | hikari.Permissions.MANAGE_ROLES),
                   app_command_dm_enabled=False

                   )
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def auto_role_cmd(_: AirySlashContext):
    pass


@auto_role_cmd.set_error_handler()
async def reactionrole_error_handler(event: lightbulb.CommandErrorEvent):
    error = event.exception.original
    if isinstance(error, errors.RoleAlreadyExists):
        embed = RespondEmbed.error(
            title="This autorole already exists",
            description=f"Try deleting a autorole with **/autorole remove**")
        await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
    elif isinstance(error, errors.RoleDoesNotExist):
        embed = RespondEmbed.error(
            title="This autorole does not exists",
            description=f"Try creating a autorole with **/autorole add**")
        await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)

    if isinstance(error, (hikari.NotFoundError, hikari.ForbiddenError)):
        perms = await check_bot_permissions(event.app, event.context.guild_id)  # type: ignore
        if perms:
            description = to_str_permissions(perms)
            embed = PermissionsErrorEmbed(description=description)
            await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)


@auto_role_cmd.child()
@lightbulb.option('role', 'Autorole that will be issued when the condition is triggered ',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("add", "Adds the role to be automatically assigned", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def auto_role_create(ctx: AirySlashContext, role: hikari.Role):
    try:
        _ = await AutoRolesService.create(ctx.guild_id, role)
    except ValueError:
        return await ctx.respond(embed=RespondEmbed.error("The specified  auto role already exists"),
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
