from __future__ import annotations

import asyncio
import datetime
import traceback
import typing

import hikari
import lightbulb

from loguru import logger

from airy.models.bot import Airy
from airy.etc.perms_str import get_perm_str
from airy.etc import ColorEnum
from airy.models.context import AiryContext, AirySlashContext, AiryPrefixContext
from airy.models.errors import UserBlacklistedError, BotRoleHierarchyError, RoleHierarchyError, MemberExpectedError, \
    InteractionTimeOutError
from airy.utils import helpers, RespondEmbed

import config

ch = lightbulb.Plugin("Command Handler")


async def log_exc_to_channel(
        error_str: str,
        ctx: typing.Optional[lightbulb.Context] = None,
        event: typing.Optional[hikari.ExceptionEvent] = None
) -> None:
    error_lines = error_str.split("\n")
    paginator = lightbulb.utils.StringPaginator(max_chars=2000, prefix="```py\n", suffix="```")
    if ctx:
        if guild := ctx.get_guild():
            assert ctx.command is not None
            paginator.add_line(
                f"Error in '{guild.name}' ({ctx.guild_id}) during command '{ctx.command.name}' "
                f"executed by user '{ctx.author}' ({ctx.author.id})\n"
            )

    elif event:
        paginator.add_line(
            f"Ignoring exception in listener for {event.failed_event.__class__.__name__}, "
            f"callback {event.failed_callback.__name__}:\n"
        )
    else:
        paginator.add_line(f"Uncaught exception:")

    for line in error_lines:
        paginator.add_line(line)

    assert isinstance(ch.app, Airy)
    channel_id = config.bot.errors_trace_channel

    if not channel_id:
        return

    for page in paginator.build_pages():
        try:
            await ch.app.rest.create_message(channel_id, page)
        except Exception as error:
            logger.error(f"Failed sending traceback to error-logging channel: {error}")


async def application_error_handler(ctx: AiryContext, error: lightbulb.LightbulbError) -> None:
    try:
        if isinstance(error, lightbulb.CheckFailure):
            error = error.causes[0] if error.causes else error.__cause__ if error.__cause__ else error

        if isinstance(error, UserBlacklistedError):
            embed = RespondEmbed.error(title="Application access terminated")
            if ctx.deferred:
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)

        embeds = []

        if isinstance(error, lightbulb.MissingRequiredPermission):
            embeds.append(RespondEmbed.error(title="Missing Permissions",
                                             description=f"You require "
                                                         f"`{get_perm_str(error.missing_perms).replace('|', ', ')}` "
                                                         f"permissions to execute this command.", ))

        elif isinstance(error, lightbulb.BotMissingRequiredPermission):
            embeds.append(RespondEmbed.error(title="Bot Missing Permissions",
                                             description=f"The bot requires "
                                                         f"`{get_perm_str(error.missing_perms).replace('|', ', ')}` "
                                                         f"permissions to execute this command.", ))

        elif isinstance(error, lightbulb.CommandIsOnCooldown):
            embeds.append(RespondEmbed.cooldown(title="Cooldown Pending",
                                                description=f"Please retry in: "
                                                            f"`{datetime.timedelta(seconds=round(error.retry_after))}`", ))

        elif isinstance(error, lightbulb.MaxConcurrencyLimitReached):
            embeds.append(RespondEmbed.cooldown(title="Max Concurrency Reached",
                                                description=f"You have reached the maximum amount of running instances for this "
                                                            f"command. Please try again later.", ))

        elif isinstance(error, BotRoleHierarchyError):
            embeds.append(RespondEmbed.error(title="Role Hierarchy Error",
                                             description=f"The targeted user's highest role is higher "
                                                         f"than the bot's highest role.", ))

        elif isinstance(error, RoleHierarchyError):
            embeds.append(RespondEmbed.error(title="Role Hierarchy Error",
                                             description=f"The targeted user's highest role is higher "
                                                         f"than the your highest role."))

        elif isinstance(error, lightbulb.CommandInvocationError):
            if isinstance(error.original, asyncio.TimeoutError):
                embeds.append(RespondEmbed.error(title="Action timed out",
                                                 description=f"This command timed out.", ))

            elif isinstance(error.original, hikari.InternalServerError):
                embeds.append(RespondEmbed.error(title="Discord Server Error",
                                                 description="This action has failed due to an issue with Discord's servers. "
                                                             "Please try again in a few moments."))

            elif isinstance(error.original, hikari.ForbiddenError):
                embeds.append(RespondEmbed.error(title="Forbidden",
                                                 description=f"This action has failed due to a lack of permissions."
                                                             f"\n**Error:** ```{error.original}```", ))

            elif isinstance(error.original, RoleHierarchyError):
                embeds.append(RespondEmbed.error(title="Role Hiearchy Error",
                                                 description=f"This action failed due to trying to modify "
                                                             f"a user with a role higher or equal to your highest role.", ))

            elif isinstance(error.original, BotRoleHierarchyError):
                embeds.append(RespondEmbed.error(title="Role Hiearchy Error",
                                                 description=f"This action failed due to trying to modify "
                                                             f"a user with a role higher than the bot's highest role.", ))

            elif isinstance(error.original, MemberExpectedError):
                embeds.append(RespondEmbed.error(title="Member Expected",
                                                 description=f"Expected a user who is a member of this server.", ))

            logger.error("Ignoring exception in command {}:".format(ctx.command.name))
            exception_msg = "\n".join(traceback.format_exception(type(error), error, error.__traceback__))
            logger.error(exception_msg)

            if not ctx.command.error_handler:
                error = error.original if hasattr(error, "original") else error  # type: ignore

                await ctx.respond(
                    embed=RespondEmbed.error(
                        title="Unhandled exception",
                        description=f"An error happened that should not have happened. "
                                    f"Please [contact us](https://discord.gg/J4Dy8dTARf) "
                                    f"with a screenshot of this message!\n"
                                    f"**Error:** ```{error.__class__.__name__}: {str(error).replace(ctx.app._token, '')}```",
                    ).set_footer(text=f"Guild: {ctx.guild_id}"),
                    flags=hikari.MessageFlag.EPHEMERAL,
                )
            if embeds:
                if ctx.deferred:
                    await ctx.respond(embeds=embeds)
                else:
                    await ctx.respond(embeds=embeds, flags=hikari.MessageFlag.EPHEMERAL)
            await log_exc_to_channel(exception_msg, ctx)

    except hikari.NotFoundError:
        raise InteractionTimeOutError(
            f"Interaction timed out while handling error: \n{error.__class__} "
            f"{error}\nCommand: {ctx.command.name if ctx.command else 'None'}\n"
            f"Guild: {ctx.guild_id}\nUser: {ctx.user.id}",

        )


@ch.listener(lightbulb.UserCommandErrorEvent)
@ch.listener(lightbulb.MessageCommandErrorEvent)
@ch.listener(lightbulb.SlashCommandErrorEvent)
async def application_command_error_handler(event: lightbulb.CommandErrorEvent) -> None:
    assert isinstance(event.context, AirySlashContext)
    await application_error_handler(event.context, event.exception)


@ch.listener(lightbulb.UserCommandCompletionEvent)
@ch.listener(lightbulb.SlashCommandCompletionEvent)
@ch.listener(lightbulb.MessageCommandCompletionEvent)
async def application_command_completion_handler(event: lightbulb.events.CommandCompletionEvent):
    if event.context.author.id in event.context.app.owner_ids:  # Ignore cooldowns for owner c:
        if cm := event.command.cooldown_manager:
            await cm.reset_cooldown(event.context)


@ch.listener(lightbulb.PrefixCommandErrorEvent)
async def prefix_error_handler(event: lightbulb.PrefixCommandErrorEvent) -> None:
    if event.context.author.id not in event.app.owner_ids:  # type: ignore
        return
    if isinstance(event.exception, lightbulb.CheckFailure):
        return
    if isinstance(event.exception, lightbulb.CommandNotFound):
        return

    error = event.exception.original if hasattr(event.exception, "original") else event.exception  # type: ignore

    await event.context.respond(
        embed=hikari.Embed(
            title="❌ Exception encountered",
            description=f"```{error}```",
            color=ColorEnum.ERROR,
        )
    )
    raise event.exception


@ch.listener(lightbulb.events.CommandInvocationEvent)
async def command_invoke_listener(event: lightbulb.events.CommandInvocationEvent) -> None:
    logger.info(
        f"Command {event.command.name} was invoked by {event.context.author} in guild {event.context.guild_id}."
    )


@ch.listener(lightbulb.PrefixCommandInvocationEvent)
async def prefix_command_invoke_listener(event: lightbulb.PrefixCommandInvocationEvent) -> None:
    if event.context.author.id not in event.app.owner_ids:  # type: ignore
        return

    if event.context.guild_id:
        assert isinstance(event.app, Airy)
        me = event.app.cache.get_member(event.context.guild_id, event.app.user_id)  # type: ignore
        assert me is not None

        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.ADD_REACTIONS):
            return

    assert isinstance(event.context, AiryPrefixContext)
    await event.context.event.message.add_reaction("▶️")


@ch.listener(hikari.ExceptionEvent)
async def event_error_handler(event: hikari.ExceptionEvent) -> None:
    logger.error("Ignoring exception in listener {}:".format(event.failed_event.__class__.__name__))
    exception_msg = "\n".join(traceback.format_exception(*event.exc_info))
    logger.error(exception_msg)
    await log_exc_to_channel(exception_msg, event=event)


def load(bot: Airy) -> None:
    bot.add_plugin(ch)


def unload(bot: Airy) -> None:
    bot.remove_plugin(ch)
