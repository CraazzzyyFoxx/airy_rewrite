import typing

import hikari
import lightbulb
from loguru import logger

from airy.services.reactionrole import ReactionRolesService
from airy.models import AirySlashContext, AiryPlugin, errors
from airy.utils import (helpers,
                        has_permissions,
                        RespondEmbed,
                        check_bot_permissions,
                        to_str_permissions,
                        PermissionsErrorEmbed)

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy

reaction_roles_plugin = AiryPlugin("ReactionRoles")


@reaction_roles_plugin.command
@lightbulb.add_checks(
    lightbulb.checks.has_guild_permissions(hikari.Permissions.MANAGE_ROLES, hikari.Permissions.MODERATE_MEMBERS),
    lightbulb.checks.bot_has_guild_permissions(hikari.Permissions.MANAGE_ROLES, hikari.Permissions.MODERATE_MEMBERS),
)
@lightbulb.command("reactionrole", "Commands relating to reactionroles.",
                   app_command_default_member_permissions=(hikari.Permissions.MODERATE_MEMBERS
                                                           | hikari.Permissions.MANAGE_ROLES),
                   app_command_dm_enabled=False
                   )
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def reactionrole(_: AirySlashContext) -> None:
    pass


@reactionrole.child()
@lightbulb.add_checks(has_permissions(hikari.Permissions.MANAGE_ROLES))
@lightbulb.option("message_link", "Please input message link", hikari.OptionType.STRING)
@lightbulb.option("role", "Please input role", type=hikari.OptionType.ROLE)
@lightbulb.option("emoji", "Please input emoji", type=hikari.OptionType.STRING)
@lightbulb.command("add", "Add emoji-role pair to a message", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def reactionrole_create(ctx: AirySlashContext,
                              message_link: str,
                              role: hikari.Role,
                              emoji: str
                              ) -> None:
    message = await helpers.parse_message_link(ctx, message_link)
    parsed_emoji = hikari.Emoji.parse(emoji)
    await ReactionRolesService.create(ctx.guild_id, message.channel_id, message.id, role.id, parsed_emoji)
    embed = RespondEmbed.success(
        title="Done!",
        description=f"A new reactionrole pair {parsed_emoji.mention} : {role.mention} in channel "
                    f"<#{message.channel_id}> has been created!", )
    await ctx.respond(embed=embed)


@reactionrole.set_error_handler()
async def reactionrole_error_handler(event: lightbulb.CommandErrorEvent):
    error = event.exception.original
    if isinstance(error, hikari.NotFoundError):
        embed = RespondEmbed.error(
            title="Insufficient permissions",
            description=f"The bot cannot edit the provided message due to insufficient permissions")
        await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
    elif isinstance(error, hikari.ForbiddenError):
        embed = RespondEmbed.error(
            title="Insufficient permissions",
            description=f"Bot cannot add/remove reactions due to insufficient permissions")
        await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
    elif isinstance(error, errors.RoleAlreadyExists):
        embed = RespondEmbed.error(
            title="This role-emoji pair already exists",
            description=f"Try deleting a role-emoji pair with **/reactionrole remove**")
        await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
    elif isinstance(error, errors.RoleDoesNotExist):
        embed = RespondEmbed.error(
            title="This role-emoji pair does not exists",
            description=f"Try creating a role-emoji pair with **/reactionrole add**")
        await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)

    if isinstance(error, (hikari.NotFoundError, hikari.ForbiddenError)):
        perms = await check_bot_permissions(event.app, event.context.guild_id)  # type: ignore
        if perms:
            description = to_str_permissions(perms)
            embed = PermissionsErrorEmbed(description=description)
            await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)


@reactionrole.child()
@lightbulb.add_checks(has_permissions(hikari.Permissions.MANAGE_ROLES))
# @lightbulb.option("channel", "The text channel, the message with reactionrole will be attached here.",
#                   type=hikari.OptionType.CHANNEL,
#                   channel_types=[hikari.ChannelType.GUILD_TEXT])
@lightbulb.option("message_link", "Please input message link", hikari.OptionType.STRING)
@lightbulb.option("role", "Please input role", type=hikari.OptionType.ROLE)
@lightbulb.command("remove", "Removes emoji-role pair to a message", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def reactionrole_remove(ctx: AirySlashContext,
                              message_link: str,
                              role: hikari.Role,
                              ) -> None:
    message = await helpers.parse_message_link(ctx, message_link)
    if not message:
        raise hikari.NotFoundError()

    model = await ReactionRolesService.delete(ctx.guild_id, message.channel_id, message.id, role.id)

    embed = RespondEmbed.success(
        title="Done!",
        description=f"Reactionrole pair {model.emoji.mention} : {role.mention} in channel "
                    f"<#{message.channel_id}> has been deleted!", )
    await ctx.respond(embed=embed)


@reactionrole.child()
@lightbulb.add_checks(has_permissions(hikari.Permissions.MANAGE_ROLES))
@lightbulb.option("message_link", "Please input message link", hikari.OptionType.STRING)
@lightbulb.command("show", "List all registered rolebuttons on this server.", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def reactionrole_show(ctx: AirySlashContext, message_link: str) -> None:
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    message = await helpers.parse_message_link(ctx, message_link)
    if not message:
        raise hikari.NotFoundError()

    models = await ReactionRolesService.get_all(message.channel_id, message.id)
    if len(models) == 0:
        await ctx.respond(embed=RespondEmbed.error("Reactionroles are missing"))
        return

    model_ = models[0]
    description = [
        f'[Message URL](https://discord.com/channels/{model_.guild_id}/{model_.channel_id}/{model_.message_id})\n\n']
    for index, model in enumerate(models, 1):
        description.append(f"**{index}.** {model.emoji.mention} : <@&{model.role_id}>")

    e = RespondEmbed.success("Reaction Roles",
                             description="\n".join(description))

    await ctx.respond(embed=e)


def load(bot: "Airy") -> None:
    bot.add_plugin(reaction_roles_plugin)


def unload(bot: "Airy") -> None:
    bot.remove_plugin(reaction_roles_plugin)
