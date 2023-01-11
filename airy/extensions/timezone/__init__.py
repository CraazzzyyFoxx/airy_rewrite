import asyncio
import datetime
import typing

import hikari
import lightbulb
import miru
import pytz

from fuzzywuzzy import process

from airy.models import AirySlashContext, DatabaseUser
from airy.etc import ColorEnum
from airy.utils import SimplePages, RespondEmbed, format_dt


if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


timezone = lightbulb.Plugin("Timezone")


class TimezoneSelect(miru.Select):
    def __init__(self, options: typing.Sequence[typing.Tuple[str, int]]):
        options = [miru.SelectOption(label=f"{index}. {value[0]}", value=value[0])
                   for index, value in enumerate(options, 1)]
        super().__init__(options=options)

    async def callback(self, context: miru.ViewContext) -> None:
        self.view.status = True
        self.view.tz = self.values[0]
        self.view.stop()


class TimezoneChoice(miru.View):
    def __init__(self, options: typing.Sequence[typing.Tuple[str, int]], author: hikari.User):
        super().__init__(timeout=20)
        self.user = author
        self.status: typing.Optional[bool] = None
        self.tz: typing.Optional[str] = None
        self.add_item(TimezoneSelect(options))

    async def view_check(self, context: miru.ViewContext) -> bool:
        return self.user == context.user

    async def on_timeout(self) -> None:
        self.status = False
        self.stop()


@timezone.command()
@lightbulb.command("timezone", "Manages timezones", app_command_dm_enabled=False)
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def tz_cmd(_: AirySlashContext):
    pass


@tz_cmd.child()
@lightbulb.option('tz', 'Please input timezone.', type=hikari.OptionType.STRING)
@lightbulb.command("set", "Choose your timezone")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def tz_set_cmd(ctx: AirySlashContext):
    tz = ctx.options.tz
    timezones = await asyncio.threads.to_thread(process.extract, tz, choices=pytz.common_timezones, limit=8)
    if (tz_ := timezones[0])[1] < 87:
        embed = hikari.Embed()
        embed.description = '\n'.join([f"**{index}.** {value[0]}" for index, value in enumerate(timezones, 1)])
        view = TimezoneChoice(timezones, ctx.author)
        resp = await ctx.respond(embed=embed, components=view.build())
        await view.start(await resp.message())
        await view.wait()

        if view.status:
            tz_ = view.tz
        else:
            return await ctx.edit_last_response(RespondEmbed.error("Timeout..."), components=[])
    await DatabaseUser(id=ctx.author.id, tz=tz_).update()
    await ctx.edit_last_response(RespondEmbed.success("Timezone setup successfully."), components=[])


@tz_cmd.child()
@lightbulb.option('user', 'Timezone', type=hikari.OptionType.USER)
@lightbulb.command("get", "Gets user's timezone")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def tz_get_cmd(ctx: AirySlashContext):
    model = await DatabaseUser.fetch(ctx.options.user.id)
    tz = pytz.timezone(model.tz) if model else pytz.utc
    embed = hikari.Embed(color=ColorEnum.blurple)
    embed.description = f"**Timezone:** {tz} \n " \
                        f"**Current time:** \n >>> " \
                        f"{datetime.datetime.now().astimezone(tz).strftime('%B %d, %Y %X')} \n " \
                        f"{format_dt(datetime.datetime.now().astimezone(tz))}"
    await ctx.respond(embed=embed)


@tz_cmd.child()
@lightbulb.command("list", "Shows all supported timezones")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def tz_diff_cmd(ctx: AirySlashContext):
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)
    pages = SimplePages(pytz.common_timezones, ctx=ctx)
    await pages.send(ctx.interaction, responded=True)


def load(bot: "Airy") -> None:
    bot.add_plugin(timezone)
    pass


def unload(bot: "Airy") -> None:
    bot.remove_plugin(timezone)
    pass
