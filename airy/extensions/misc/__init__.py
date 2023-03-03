import hikari
import lightbulb

from loguru import logger

from airy.etc import ColorEnum
from airy.models.bot import Airy
from airy.models.context import AirySlashContext
from airy.models.plugin import AiryPlugin
from airy.utils import RespondEmbed


class MetaPlugin(AiryPlugin):
    def __init__(self):
        super().__init__("Meta")

    async def on_guild_join(self, event: hikari.GuildJoinEvent):
        e = RespondEmbed.success("Guild Available")
        await self.send_guild_stats(e, event.guild)

    async def on_guild_leave(self, event: hikari.GuildLeaveEvent):
        e = RespondEmbed.error("Guild Leave")
        await self.send_guild_stats(e, event.old_guild)

    async def send_guild_stats(self, e: hikari.Embed, guild: hikari.GatewayGuild):
        owner = guild.get_member(guild.owner_id)
        members = self.bot.cache.get_members_view_for_guild(guild.id)
        bots = sum(m.is_bot for m in members.values())

        e.add_field(name='Name', value=guild.name, inline=True)
        e.add_field(name='ID', value=str(guild.id), inline=True)
        e.add_field(name='Shard ID', value=guild.shard_id or 'N/A', inline=True)
        if owner:
            e.add_field(name='Owner',
                        value=f'{owner.display_name}#{owner.discriminator} (ID: {guild.owner_id})',
                        inline=True)

        e.add_field(name='Members', value=str(guild.member_count), inline=True)
        e.add_field(name='Bots', value=f'{bots} ({bots / guild.member_count:.2%})', inline=True)

        if guild.icon_url:
            e.set_thumbnail(guild.icon_url)

        await mp.bot.rest.create_message(self.bot.config.stats_channel, embed=e)


mp = MetaPlugin()


@mp.command
@lightbulb.command("ping", "Check the bot's latency.")
@lightbulb.implements(lightbulb.SlashCommand)
async def ping(ctx: AirySlashContext) -> None:
    embed = hikari.Embed(
        title="🏓 Pong!",
        description=f"Latency: `{round(ctx.app.heartbeat_latency * 1000)}ms`",
        color=ColorEnum.MISC,
    )
    await ctx.respond(embed=embed)


def load(bot: Airy) -> None:
    bot.add_plugin(mp)
    bot.subscribe(hikari.GuildJoinEvent, mp.on_guild_join)
    bot.subscribe(hikari.GuildLeaveEvent, mp.on_guild_leave)


def unload(bot: Airy) -> None:
    bot.unsubscribe(hikari.GuildJoinEvent, mp.on_guild_join)
    bot.unsubscribe(hikari.GuildLeaveEvent, mp.on_guild_leave)
    bot.remove_plugin(mp)
