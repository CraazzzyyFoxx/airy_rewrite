from __future__ import annotations

import asyncio
import typing as t

import hikari
import lightbulb
import miru

from fuzzywuzzy import process

from ..models import errors
from airy.models import AirySlashContext

from .matchers import URL_MATCHER, INVITE_MATCHER, MESSAGE_LINK_MATCHER
from .embeds import RespondEmbed

__all__ = ("add_embed_footer",
           "get_color",
           "sort_roles",
           "includes_permissions",
           "is_above",
           "is_member",
           "is_url",
           "is_invite",
           "parse_color",
           "parse_role",
           "parse_message_link",
           "maybe_delete",
           "maybe_edit",
           "format_reason")


def add_embed_footer(embed: hikari.Embed, invoker: hikari.Member) -> hikari.Embed:
    """
    Add a note about the command invoker in the embed passed.
    """
    avatar_url = invoker.display_avatar_url

    embed.set_footer(text=f"Requested by {invoker}", icon=avatar_url)
    return embed


def get_color(member: hikari.Member) -> t.Optional[hikari.Color]:
    roles = member.get_roles().__reversed__()
    if roles:
        for role in roles:
            if role.color != hikari.Color.from_rgb(0, 0, 0):
                return role.color

    return None


def sort_roles(roles: t.Sequence[hikari.Role]) -> t.Sequence[hikari.Role]:
    """Sort a list of roles in descending order based on position."""
    return sorted(roles, key=lambda r: r.position, reverse=True)


def includes_permissions(permissions: hikari.Permissions, should_include: hikari.Permissions) -> bool:
    """Check if permissions includes should_includes."""

    if permissions & hikari.Permissions.ADMINISTRATOR:
        return True

    missing_perms = ~permissions & should_include
    if missing_perms is not hikari.Permissions.NONE:
        return False
    return True


def is_above(me: hikari.Member, member: hikari.Member) -> bool:
    """
    Returns True if me top role's position is higher than the specified member's.
    """
    me_top_role = me.get_top_role()
    member_top_role = member.get_top_role()

    assert me_top_role is not None
    assert member_top_role is not None

    if me_top_role.position > member_top_role.position:
        return True
    return False


def can_harm(
        me: hikari.Member, member: hikari.Member, permission: hikari.Permissions, *, raise_error: bool = False
) -> bool:
    """
    Returns True if "member" can be harmed by "me", also checks if "me" has "permission".
    """

    perms = lightbulb.utils.permissions_for(me)

    if not includes_permissions(perms, permission):
        if raise_error:
            raise lightbulb.BotMissingRequiredPermission(perms=permission)
        return False

    guild = member.get_guild()
    if not guild:
        return True

    if member.id == guild.owner_id:
        if raise_error:
            raise errors.RoleHierarchyError
        return False

    if not is_above(me, member):
        if raise_error:
            raise errors.RoleHierarchyError
        return False

    return True


def is_url(string: str, *, fullmatch: bool = True) -> bool:
    """
    Returns True if the provided string is a URL, otherwise False.
    """

    if fullmatch and URL_MATCHER.fullmatch(string):
        return True
    elif not fullmatch and URL_MATCHER.match(string):
        return True

    return False


def is_invite(string: str, *, fullmatch: bool = True) -> bool:
    """
    Returns True if the provided string is a Discord invite, otherwise False.
    """

    if fullmatch and INVITE_MATCHER.fullmatch(string):
        return True
    elif not fullmatch and INVITE_MATCHER.match(string):
        return True

    return False


def is_member(user: hikari.PartialUser) -> bool:  # Such useful
    """Determine if the passed object is a member or not, otherwise raise an error.
    Basically equivalent to `assert isinstance(user, hikari.Member)` but with a fancier error."""
    if isinstance(user, hikari.Member):
        return True

    raise errors.MemberExpectedError(f"Expected an instance of hikari.Member, not {user.__class__.__name__}!")


async def parse_message_link(ctx: AirySlashContext, message_link: str) -> t.Optional[hikari.Message]:
    """Parse a message_link string into a message object."""

    assert ctx.guild_id is not None

    if not MESSAGE_LINK_MATCHER.fullmatch(message_link):
        embed = RespondEmbed.error(title="Invalid link",
                                   description="This does not appear to be a valid message link! "
                                               "You can get a message's link by right-clicking it and selecting "
                                               "`Copy Message Link`!")
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
        return None

    snowflakes = message_link.split("/channels/")[1].split("/")
    guild_id = hikari.Snowflake(snowflakes[0]) if snowflakes[0] != "@me" else None
    channel_id = hikari.Snowflake(snowflakes[1])
    message_id = hikari.Snowflake(snowflakes[2])

    if ctx.guild_id != guild_id:
        embed = RespondEmbed.error(title="Invalid link",
                                   description="The message seems to be from another server! "
                                               "Please copy a message link from this server!")
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
        return None

    channel = ctx.app.cache.get_guild_channel(channel_id)
    me = ctx.app.cache.get_member(ctx.guild_id, ctx.app.user_id)
    assert channel is not None and me is not None and isinstance(channel, hikari.TextableGuildChannel)

    perms = lightbulb.utils.permissions_in(channel, me)
    if not (perms & hikari.Permissions.READ_MESSAGE_HISTORY):
        raise lightbulb.BotMissingRequiredPermission(perms=hikari.Permissions.READ_MESSAGE_HISTORY)

    try:
        message = await ctx.app.rest.fetch_message(channel, message_id)
    except (hikari.NotFoundError, hikari.ForbiddenError):
        embed = RespondEmbed.error(
            title="Unknown message",
            description="Could not find message with this link. "
                        "Ensure the link is valid, and that the bot has permissions to view the channel.",
        )
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
        return None

    return message


async def maybe_delete(message: hikari.PartialMessage) -> None:
    try:
        await message.delete()
    except (hikari.NotFoundError, hikari.ForbiddenError, hikari.HTTPError):
        pass


async def maybe_edit(message: hikari.PartialMessage, *args, **kwargs) -> None:
    try:
        await message.edit(*args, **kwargs)
    except (hikari.NotFoundError, hikari.ForbiddenError, hikari.HTTPError):
        pass


def format_reason(
        reason: t.Optional[str] = None, moderator: t.Optional[hikari.Member] = None, *,
        max_length: t.Optional[int] = 512
) -> str:
    """
    Format a reason for a moderation action
    """
    if not reason:
        reason = "No reason provided."

    if moderator:
        reason = f"{moderator} ({moderator.id}): {reason}"

    if max_length and len(reason) > max_length:
        reason = reason[: max_length - 3] + "..."

    return reason


def parse_color(value: t.Union[int, str]) -> t.Optional[hikari.Color]:
    if isinstance(value, int) and (0 <= value <= 16777215):
        return hikari.Color.from_int(value)

    elif len(value) == 3 and len([x for x in value if str(x).isdigit() and 255 >= int(x) >= 0]) == len(value):
        color = [int(x) for x in value]
        return hikari.Color.from_int(color[0] << 16 | color[1] << 8 | color[2] << 0)

    if isinstance(value, tuple) and len(value) == 1:
        value = value[0]

    color = value.lstrip('#')
    if len(color) == 6:
        try:
            return hikari.Color.from_hex_code(color)
        except ValueError:
            return None


async def parse_role(
        ctx: t.Union[AirySlashContext, miru.ViewContext, miru.ModalContext],
        value: t.Union[int, str]
        ) -> hikari.Role | None:
    """Checks that provided value is role by id and name"""
    roles = ctx.bot.cache.get_roles_view_for_guild(ctx.guild_id)
    if value.isdigit():
        if (role := roles.get(hikari.Snowflake(value))) is not None:
            return role

    role_names = [role.name for role in roles.values()]
    role_name = await asyncio.threads.to_thread(process.extractOne, value, choices=role_names)
    role_name = role_name[0]
    for role in roles.values():
        if role.name == role_name:
            return role

    return None
