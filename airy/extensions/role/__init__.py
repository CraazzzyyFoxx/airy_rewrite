from __future__ import annotations

import asyncio
import typing

import hikari
import lightbulb

from airy.models import AiryPlugin, AirySlashContext
from airy.utils import RespondEmbed, SimplePages, helpers, time
from airy.etc import RespondEmojiEnum

role_plugin = AiryPlugin('Role')
role_plugin.add_checks(lightbulb.guild_only)
role_plugin.add_checks(lightbulb.checks.has_guild_permissions(hikari.Permissions.MANAGE_ROLES,
                                                              hikari.Permissions.MODERATE_MEMBERS))
role_plugin.add_checks(lightbulb.checks.bot_has_guild_permissions(hikari.Permissions.MANAGE_ROLES,
                                                                  hikari.Permissions.MODERATE_MEMBERS))

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


@role_plugin.command()
@lightbulb.command("role",
                   "Manages role",
                   app_command_default_member_permissions=(hikari.Permissions.MODERATE_MEMBERS
                                                           | hikari.Permissions.MANAGE_ROLES),
                   app_command_dm_enabled=False

                   )
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def role_cmd(_: AirySlashContext):
    pass


@role_cmd.child()
@lightbulb.option("member", "Enter member's name",
                  type=hikari.OptionType.USER)
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("add", "Adds the role to the specified member", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_add(ctx: AirySlashContext, role: hikari.Role, member: hikari.Member):
    await ctx.bot.rest.add_role_to_member(ctx.guild_id, member.id, role.id)
    await ctx.respond(embed=RespondEmbed.success("Added", description=f"Role {role.mention} to {member.mention}"))


@role_cmd.child()
@lightbulb.option("member", "Enter member's name",
                  type=hikari.OptionType.USER)
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("remove", "Removes the role to the specified member", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_remove(ctx: AirySlashContext, role: hikari.Role, member: hikari.Member):
    await ctx.bot.rest.remove_role_from_member(ctx.guild_id, member.id, role.id)
    await ctx.respond(embed=RespondEmbed.success("Removed", description=f"Role {role.mention} from {member.mention}"))


@role_cmd.child()
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("all", "Adds the role to all members", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_all(ctx: AirySlashContext, role: hikari.Role):
    agree = await ctx.confirm(embed=RespondEmbed.help(title="Confirmation",
                                                      description=f"{ctx.author.mention} This will add {role.mention}"
                                                                  f"to all members. Do you want to continue?"))

    if not agree:
        await ctx.edit_last_response(embed=RespondEmbed.error("Canceled"), components=[])
        return

    count = 0
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async with asyncio.TaskGroup() as tg:
        members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
        for member_id in members.keys():
            tg.create_task(ctx.bot.rest.add_role_to_member(ctx.guild_id, member_id, role.id))
            count += 1

    e = RespondEmbed.success("Success",
                             description=f"Added {role.mention} to {count} members")

    await ctx.edit_last_response(embed=e, components=[])


@role_cmd.child()
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("rall", "Removes the role to all members", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_rall(ctx: AirySlashContext, role: hikari.Role):
    e = RespondEmbed.help(title="Confirmation",
                          description=f"{ctx.author.mention} This will remove {role.mention}"
                                      f"from all members. Do you want to continue?")

    agree = await ctx.confirm(embed=e)

    if not agree:
        await ctx.edit_last_response(embed=RespondEmbed.error("Canceled"), components=[])
        return

    count = 0
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async with asyncio.TaskGroup() as tg:
        members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
        for member_id in members.keys():
            tg.create_task(ctx.bot.rest.remove_role_from_member(ctx.guild_id, member_id, role.id))
            count += 1

    e = RespondEmbed.success("Success",
                             description=f"Removed {role.mention} from {count} members")

    await ctx.edit_last_response(embed=e, components=[])


@role_cmd.child()
@lightbulb.command("allroles", "Displays all roles and their id", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_allroles(ctx: AirySlashContext):
    roles = ctx.bot.cache.get_roles_view_for_guild(ctx.guild_id)
    pages = [f"{role.mention} - (ID: {role.id})" for role in roles.values()]
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)
    pages = SimplePages(pages, ctx=ctx)
    await pages.send(ctx.interaction, responded=True)


@role_cmd.child()
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("diagnose", "Diagnose a role", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_diagnose(ctx: AirySlashContext, role: hikari.Role):
    me = ctx.bot.cache.get_member(ctx.guild_id, ctx.bot.user_id)
    me_per = lightbulb.utils.permissions_for(me)
    mem_per = helpers.includes_permissions(lightbulb.utils.permissions_for(ctx.member),
                                           hikari.Permissions.MANAGE_ROLES | hikari.Permissions.MODERATE_MEMBERS)
    top_role_me = me.get_top_role()
    top_role_mem = ctx.member.get_top_role()

    if me.get_top_role().position > role.position and me_per:
        me_assign = True
    else:
        me_assign = False

    if (ctx.member.get_top_role().position > role.position and mem_per) or ctx.author.id == ctx.get_guild().owner_id:
        mem_assign = True
    else:
        mem_assign = False

    description = [f"Manage roles for me: {RespondEmojiEnum.SUCCESS if mem_per else RespondEmojiEnum.ERROR}",
                   f"Manage roles for you: {RespondEmojiEnum.SUCCESS if me_per else RespondEmojiEnum.ERROR}",
                   f"My top role: {top_role_me.mention} (position {top_role_me.position})",
                   f"Author's top role: {top_role_mem.mention} (position {top_role_mem.position})",
                   f"Specified role: {role.mention} (position {role.position})",
                   f"I can assign: {RespondEmojiEnum.SUCCESS if me_assign else RespondEmojiEnum.ERROR}",
                   f"You can assign: {RespondEmojiEnum.SUCCESS if mem_assign else RespondEmojiEnum.ERROR}"]

    await ctx.respond(embed=RespondEmbed.success(description="\n".join(description)))


@role_cmd.child()
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("humans", "Adds a role to all humans (non bots)", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_humans(ctx: AirySlashContext, role: hikari.Role):
    agree = await ctx.confirm(embed=RespondEmbed.help(title="Confirmation",
                                                      description=f"{ctx.author.mention} This will add {role.mention}"
                                                                  f"to all members. Do you want to continue?"))

    if not agree:
        await ctx.edit_last_response(embed=RespondEmbed.error("Canceled"), components=[])
        return

    count = 0
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async with asyncio.TaskGroup() as tg:
        members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
        for member in members.values():
            if not member.is_bot:
                tg.create_task(ctx.bot.rest.add_role_to_member(ctx.guild_id, member.id, role.id))
                count += 1

    e = RespondEmbed.success("Success",
                             description=f"Added {role.mention} to {count} members")

    await ctx.edit_last_response(embed=e, components=[])


@role_cmd.child()
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("removehumans", "Adds a role to all humans (non bots)", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_removehumans(ctx: AirySlashContext, role: hikari.Role):
    e = RespondEmbed.help(title="Confirmation",
                          description=f"{ctx.author.mention} This will removes {role.mention}"
                                      f"from all members. Do you want to continue?")

    agree = await ctx.confirm(embed=e)

    if not agree:
        await ctx.edit_last_response(embed=RespondEmbed.error("Canceled"), components=[])
        return

    count = 0
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async with asyncio.TaskGroup() as tg:
        members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
        for member in members.values():
            if not member.is_bot:
                tg.create_task(ctx.bot.rest.remove_role_from_member(ctx.guild_id, member.id, role.id))
                count += 1

    e = RespondEmbed.success("Success",
                             description=f"Removed {role.mention} from {count} members")

    await ctx.edit_last_response(embed=e, components=[])


@role_cmd.child()
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("bots", "Adds a role to all bots", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_bots(ctx: AirySlashContext, role: hikari.Role):
    agree = await ctx.confirm(embed=RespondEmbed.help(title="Confirmation",
                                                      description=f"{ctx.author.mention} This will add {role.mention}"
                                                                  f"to all bots. Do you want to continue?"))

    if not agree:
        await ctx.edit_last_response(embed=RespondEmbed.error("Canceled"), components=[])
        return

    count = 0
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async with asyncio.TaskGroup() as tg:
        members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
        for member in members.values():
            if member.is_bot:
                tg.create_task(ctx.bot.rest.add_role_to_member(ctx.guild_id, member.id, role.id))
                count += 1

    e = RespondEmbed.success("Success",
                             description=f"Added {role.mention} to {count} bots")

    await ctx.edit_last_response(embed=e, components=[])


@role_cmd.child()
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("removebots", "Removes a role to all bots", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_removebots(ctx: AirySlashContext, role: hikari.Role):
    e = RespondEmbed.help(title="Confirmation",
                          description=f"{ctx.author.mention} This will removes {role.mention}"
                                      f"from all bots. Do you want to continue?")

    agree = await ctx.confirm(embed=e)

    if not agree:
        await ctx.edit_last_response(embed=RespondEmbed.error("Canceled"), components=[])
        return

    count = 0
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async with asyncio.TaskGroup() as tg:
        members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
        for member in members.values():
            if member.is_bot:
                tg.create_task(ctx.bot.rest.remove_role_from_member(ctx.guild_id, member.id, role.id))
                count += 1

    e = RespondEmbed.success("Success",
                             description=f"Removed {role.mention} from {count} bots")

    await ctx.edit_last_response(embed=e, components=[])


@role_cmd.child()
@lightbulb.option('base_role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.option('new_role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("in", "Adds a role to all members currently in a role", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_in(ctx: AirySlashContext, base_role: hikari.Role, new_role: hikari.Role):
    agree = await ctx.confirm(embed=RespondEmbed.help(title="Confirmation",
                                                      description=f"{ctx.author.mention} "
                                                                  f"This will add {new_role.mention}"
                                                                  f"to all members currently in {base_role.mention}. "
                                                                  f"Do you want to continue?"))
    if not agree:
        await ctx.edit_last_response(embed=RespondEmbed.error("Canceled"), components=[])
        return

    count = 0
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async with asyncio.TaskGroup() as tg:
        members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
        for member in members.values():
            if base_role in member.get_roles():
                tg.create_task(ctx.bot.rest.add_role_to_member(ctx.guild_id, member.id, new_role.id))
                count += 1

    e = RespondEmbed.success("Success",
                             description=f"Added {new_role.mention} to {count} members")

    await ctx.edit_last_response(embed=e, components=[])


@role_cmd.child()
@lightbulb.option('base_role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.option('new_role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("removein", "Removes a role to all members currently in a role", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_removein(ctx: AirySlashContext, base_role: hikari.Role, new_role: hikari.Role):
    agree = await ctx.confirm(embed=RespondEmbed.help(title="Confirmation",
                                                      description=f"{ctx.author.mention} "
                                                                  f"This will remove {new_role.mention}"
                                                                  f"from all members currently in {base_role.mention}. "
                                                                  f"Do you want to continue?"))
    if not agree:
        await ctx.edit_last_response(embed=RespondEmbed.error("Canceled"), components=[])
        return

    count = 0
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async with asyncio.TaskGroup() as tg:
        members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
        for member in members.values():
            if base_role in member.get_roles():
                tg.create_task(ctx.bot.rest.remove_role_from_member(ctx.guild_id, member.id, new_role.id))
                count += 1

    e = RespondEmbed.success("Success",
                             description=f"Added {new_role.mention} to {count} members")

    await ctx.edit_last_response(embed=e, components=[])


@role_cmd.child()
@lightbulb.option('role', 'Input role',
                  type=hikari.OptionType.ROLE)
@lightbulb.command("info", "Check info for a role", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def role_info(ctx: AirySlashContext, role: hikari.Role):
    count = 0
    members = ctx.bot.cache.get_members_view_for_guild(ctx.guild_id)
    for member in members.values():
        if role in member.get_roles():
            count += 1

    description = [f"Name: {role.mention}",
                   f"Members: {count}",
                   f"Color: {role.color}",
                   f"Created {time.format_dt(role.created_at, 'R')}", ]

    await ctx.respond(embed=RespondEmbed.success(description="\n".join(description)))


def load(bot: "Airy") -> None:
    bot.add_plugin(role_plugin)


def unload(bot: "Airy") -> None:
    bot.remove_plugin(role_plugin)
