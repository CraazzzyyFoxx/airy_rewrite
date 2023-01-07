

import logging
from dataclasses import dataclass

import hikari
import lightbulb
from pygount import SourceAnalysis

import airy
from airy.models.bot import Airy
from airy.models import AiryPlugin


class MetaPlugin(AiryPlugin):
    def __init__(self):
        super().__init__("Meta")

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

        await mp.bot.rest.create_message(mp.bot.config.stats_channel, embed=e)


mp = MetaPlugin()
logger = logging.getLogger(__name__)


@dataclass
class CodeCounter:
    code: int = 0
    docs: int = 0
    empty: int = 0

    def count(self) -> "CodeCounter":
        for file in airy.ROOT_DIR.rglob("*.py"):
            analysis = SourceAnalysis.from_file(file, "pygount", encoding="utf-8")
            self.code += analysis.code_count
            self.docs += analysis.documentation_count
            self.empty += analysis.empty_count

        return self


@mp.listener(lightbulb.CommandInvocationEvent)
async def command_invoke_listener(event: lightbulb.CommandInvocationEvent) -> None:
    logger.info(
        f"Command {event.command.name} was invoked by {event.context.author} in guild {event.context.guild_id}."
    )


def load(bot: Airy) -> None:
    if not bot.d.loc:
        bot.d.loc = CodeCounter().count()
    bot.add_plugin(mp)


def unload(bot: Airy) -> None:
    bot.remove_plugin(mp)
