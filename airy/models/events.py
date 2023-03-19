from __future__ import annotations

import typing

import attr
import hikari

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


__all__ = ("AiryEvent",
           "AiryGuildEvent",
           "AutoModMessageFlagEvent",
           "MassBanEvent",
           "WarnEvent",
           "WarnCreateEvent",
           "WarnRemoveEvent",
           "WarnsClearEvent",
           )


class AiryEvent(hikari.Event):
    """
    Base event for any custom event implemented by this application.
    """
    app: Airy


class AiryGuildEvent(AiryEvent):
    """
    Base event for any custom event that occurs within the context of a guild.
    """
    app: Airy
    _guild_id: hikari.Snowflakeish

    @property
    def guild_id(self) -> hikari.Snowflake:
        return hikari.Snowflake(self._guild_id)

    async def fetch_guild(self) -> hikari.RESTGuild:
        """Perform an API call to get the guild that this event relates to.

        Returns
        -------
        hikari.guilds.RESTGuild
            The guild this event occurred in.
        """
        return await self.app.rest.fetch_guild(self.guild_id)

    async def fetch_guild_preview(self) -> hikari.GuildPreview:
        """Perform an API call to get the preview of the event's guild.

        Returns
        -------
        hikari.guilds.GuildPreview
            The preview of the guild this event occurred in.
        """
        return await self.app.rest.fetch_guild_preview(self.guild_id)

    def get_guild(self) -> typing.Optional[hikari.GatewayGuild]:
        """Get the cached guild that this event relates to, if known.

        If not known, this will return `builtins.None` instead.

        Returns
        -------
        Optional[hikari.guilds.GatewayGuild]
            The guild this event relates to, or `builtins.None` if not known.
        """
        if not isinstance(self.app, hikari.CacheAware):
            return None

        return self.app.cache.get_guild(self.guild_id)


@attr.define()
class MassBanEvent(AiryGuildEvent):
    """
    Dispatched when a mass-ban occurs.
    """

    moderator: hikari.Member
    total: int
    successful: int
    users_file: hikari.Resourceish
    reason: typing.Optional[str] = None


@attr.define()
class WarnEvent(AiryGuildEvent):
    """
    Base class for all warning events.
    """

    member: hikari.Member
    moderator: hikari.Member
    warn_count: int
    reason: typing.Optional[str] = None


@attr.define()
class WarnCreateEvent(WarnEvent):
    """
    Dispatched when a user is warned.
    """

    ...


@attr.define()
class WarnRemoveEvent(WarnEvent):
    """
    Dispatched when a warning is removed from a user.
    """

    ...


@attr.define()
class WarnsClearEvent(WarnEvent):
    """
    Dispatched when warnings are cleared for a user.
    """

    ...


@attr.define()
class AutoModMessageFlagEvent(AiryGuildEvent):
    """
    Dispatched when a message is flagged by auto-mod.
    """

    message: hikari.PartialMessage
    user: hikari.PartialUser
    reason: typing.Optional[str] = None


