from __future__ import annotations

import json
import typing

from datetime import timedelta

import hikari
import lightbulb
import miru

from loguru import logger

from airy.models.context import AirySlashContext
from airy.models.plugin import AiryPlugin
from airy.models.views import AuthorOnlyNavigator
from airy.models.bot import Airy
from airy.services.scheduler import SchedulerService, TimerEnum, DatabaseTimer
from airy.etc import ColorEnum
from airy.services.scheduler.events import ReminderEvent
from airy.utils import RespondEmbed, formats, utcnow


class ReminderPlugin(AiryPlugin):
    """Reminders to do something."""

    def __init__(self):
        super().__init__(name='Reminder')


reminders = ReminderPlugin()
reminders.add_checks(lightbulb.guild_only)


class SnoozeSelect(miru.TextSelect):
    def __init__(self) -> None:
        super().__init__(
            options=[
                miru.SelectOption(label="5 minutes", value="5"),
                miru.SelectOption(label="15 minutes", value="15"),
                miru.SelectOption(label="30 minutes", value="30"),
                miru.SelectOption(label="1 hour", value="60"),
                miru.SelectOption(label="2 hours", value="120"),
                miru.SelectOption(label="3 hours", value="180"),
                miru.SelectOption(label="6 hours", value="360"),
                miru.SelectOption(label="12 hours", value="720"),
                miru.SelectOption(label="1 day", value="1440"),
            ],
            placeholder="Snooze reminder...",
        )

    async def callback(self, ctx: miru.ViewContext) -> None:
        assert isinstance(self.view, SnoozeView)

        expiry = utcnow() + timedelta(minutes=int(self.values[0]))
        assert (
                self.view.reminder_message.embeds[0].description
                and isinstance(ctx.app, Airy)
                and ctx.guild_id
                and isinstance(self.view, SnoozeView)
        )
        message = self.view.reminder_message.embeds[0].description.split("\n\n[Jump to original message!](")[0]

        reminder_data = {
            "message": message,
            "jump_url": ctx.message.make_link(ctx.guild_id),
            "additional_recipients": [],
            "is_snoozed": True,
        }

        timer = await SchedulerService.create_timer(
            expiry,
            TimerEnum.REMINDER,
            ctx.guild_id,
            ctx.user,
            ctx.channel_id,
            extra=reminder_data,
        )

        await ctx.edit_response(
            embed=RespondEmbed.success(
                title="Reminder snoozed",
                description=f"Reminder snoozed until: {formats.format_dt(expiry)} "
                            f"({formats.format_dt(expiry, style='R')})\n\n**Message:**\n{message}",
            ).set_footer(f"Reminder ID: {timer.id}"),
            components=miru.View().add_item(
                miru.Select(placeholder="Reminder snoozed!", options=[miru.SelectOption("foo")], disabled=True)
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        self.view.stop()


class SnoozeView(miru.View):
    def __init__(
            self, reminder_message: hikari.Message, *, timeout: typing.Optional[float] = 600, autodefer: bool = True
    ) -> None:
        super().__init__(timeout=timeout, autodefer=autodefer)
        self.reminder_message = reminder_message
        self.add_item(SnoozeSelect())

    async def on_timeout(self) -> None:
        return await super().on_timeout()


@reminders.listener(miru.ComponentInteractionCreateEvent, bind=True)
async def reminder_component_handler(plugin: AiryPlugin, event: miru.ComponentInteractionCreateEvent) -> None:
    if not event.context.custom_id.startswith(("RMSS:", "RMAR:")):
        return

    assert event.context.guild_id is not None

    if event.context.custom_id.startswith("RMSS:"):  # Snoozes
        author_id = hikari.Snowflake(event.context.custom_id.split(":")[1])

        if author_id != event.context.user.id:
            await event.context.respond(
                embed=RespondEmbed.error(
                    title="Invalid interaction",
                    description="You cannot snooze someone else's reminder!",
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if not event.context.message.embeds:
            return

        view = miru.View.from_message(event.context.message)
        view.children[0].disabled = True  # type: ignore
        await event.context.edit_response(components=view)

        view = SnoozeView(event.context.message)  # I literally added InteractionResponse just for this
        resp = await event.context.respond(
            embed=hikari.Embed(
                title="🕔 Select a snooze duration!",
                description="Select a duration to snooze the reminder for!",
                color=ColorEnum.EMBED_BLUE,
            ),
            components=view,
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        await view.start(await resp.retrieve_message())

    else:  # Reminder additional recipients
        timer_id = int(event.context.custom_id.split(":")[1])
        try:
            timer: DatabaseTimer = await SchedulerService.get_timer(timer_id)
            if timer.channel_id != event.context.channel_id or timer.event != TimerEnum.REMINDER:
                raise ValueError

        except ValueError:
            await event.context.respond(
                embed=RespondEmbed.error(
                    title="Invalid interaction",
                    description="Oops! It looks like this reminder is no longer valid!",
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            view = miru.View.from_message(event.context.message)

            for item in view.children:
                if isinstance(item, miru.Button):
                    item.disabled = True
            await event.context.message.edit(components=view)
            return

        if timer.user_id == event.context.user.id:
            await event.context.respond(
                embed=RespondEmbed.error(
                    title="Invalid interaction",
                    description="You cannot do this on your own reminder.",
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        assert timer.extra is not None
        notes: typing.Dict[str, typing.Any] = timer.extra

        if event.context.user.id not in notes["additional_recipients"]:

            if len(notes["additional_recipients"]) > 50:
                await event.context.respond(
                    embed=RespondEmbed.error(
                        title="Invalid interaction",
                        description="Oops! Looks like too many people signed up for this reminder. "
                                    "Try creating a new reminder! (Max cap: 50)",
                    ),
                    flags=hikari.MessageFlag.EPHEMERAL,
                )
                return

            notes["additional_recipients"].append(event.context.user.id)
            timer.extra = notes
            await SchedulerService.update_timer(timer)
            await event.context.respond(
                embed=RespondEmbed.success(
                    title="Signed up to reminder",
                    description="You will be notified when this reminder is due!",
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )

        else:
            notes["additional_recipients"].remove(event.context.user.id)
            timer.extra = notes
            await SchedulerService.update_timer(timer)
            await event.context.respond(
                embed=RespondEmbed.success(
                    title="Removed from reminder",
                    description="Removed you from the list of recipients!",
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )


@reminders.command()
@lightbulb.app_command_permissions(None, dm_enabled=False)
@lightbulb.command("reminder", "Manage reminders!", app_command_dm_enabled=False)
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def reminder(_: AirySlashContext) -> None:
    pass


@reminder.child()
@lightbulb.option("message", "The message that should be sent to you when this reminder expires.")
@lightbulb.option(
    "when", "When this reminder should expire. Examples: 'in 10 minutes', 'tomorrow at 20:00', '2022-04-01'"
)
@lightbulb.command("create", "Create a new reminder.", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def reminder_create(ctx: AirySlashContext, when: str, message: typing.Optional[str] = None) -> None:
    assert ctx.guild_id is not None

    if message and len(message) >= 1000:
        await ctx.respond(
            embed=RespondEmbed.error(
                title="Reminder too long",
                description="Your reminder cannot exceed **1000** characters!",
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    try:
        time = await SchedulerService.convert_time(when, user=ctx.user, future_time=True)

    except ValueError as error:
        await ctx.respond(
            embed=RespondEmbed.error(
                title="Invalid data entered",
                description=f"Your time-format is invalid! \n**Error:** {error}",
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if (time - utcnow()).total_seconds() >= 31536000 * 5:
        await ctx.respond(
            embed=RespondEmbed.error(
                title="Invalid data entered",
                description="Sorry, but that's a bit too far in the future.",
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if (time - utcnow()).total_seconds() < 10:
        await ctx.respond(
            embed=RespondEmbed.error(
                title="Invalid data entered",
                description="Sorry, but that's a bit too short, reminders must last longer than `10` seconds.",
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    reminder_data = {'message': message, 'jump_url': None, 'additional_recipients': []}

    timer = await SchedulerService.create_timer(
        expires=time,
        event=TimerEnum.REMINDER,
        guild=ctx.guild_id,
        user=ctx.author,
        channel=ctx.channel_id,
        extra=reminder_data,
    )

    proxy = await ctx.respond(
        embed=RespondEmbed.success(
            title="Reminder set",
            description=f"Reminder set for: {formats.format_dt(time)} ({formats.format_dt(time, style='R')})"
                        f"\n\n**Message:**\n{message}",
        ).set_footer(f"Reminder ID: {timer.id}"),
        components=miru.View().add_item(miru.Button(label="Remind me too!", emoji="✉️", custom_id=f"RMAR:{timer.id}")),
    )
    reminder_data["jump_url"] = (await proxy.message()).make_link(ctx.guild_id)  # type: ignore
    timer.extra = reminder_data

    await SchedulerService.update_timer(timer)


@reminder.child()
@lightbulb.option("id", "The ID of the timer to delete. You can get this via /reminder list", type=int)
@lightbulb.command("delete", "Delete a currently pending reminder.", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def reminder_del(ctx: AirySlashContext, id: int) -> None:
    assert ctx.guild_id is not None

    try:
        await SchedulerService.cancel_timer(id)
    except ValueError:
        await ctx.respond(
            embed=RespondEmbed.error(
                title="Reminder not found",
                description=f"Cannot find reminder with ID **{id}**.",
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    await ctx.respond(
        embed=RespondEmbed.success(
            title="Reminder deleted",
            description=f"Reminder **{id}** has been deleted.",
        )
    )


@reminder.child()
@lightbulb.command("list", "List your currently pending reminders.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def reminder_list(ctx: AirySlashContext) -> None:
    records = await ctx.app.db.fetch(
        """SELECT * FROM timer WHERE guild_id = $1 AND user_id = $2 AND event = $3 ORDER BY expires""",
        ctx.guild_id,
        ctx.author.id,
        TimerEnum.REMINDER
    )

    if not records:
        await ctx.respond(
            embed=hikari.Embed(
                title="✉️ No pending reminders!",
                description="You have no pending reminders. You can create one via `/reminder create`!",
                color=ColorEnum.WARN,
            )
        )
        return

    reminders = []

    for record in records:
        time = record.get("expires")
        notes = json.loads(record["extra"])["message"].replace("\n", " ")
        if len(notes) > 50:
            notes = notes[:47] + "..."

        reminders.append(
            f"**ID: {record.get('id')}** - {formats.format_dt(time)} ({formats.format_dt(time, style='R')})\n{notes}\n"
        )

    reminders = [reminders[i * 10: (i + 1) * 10] for i in range((len(reminders) + 10 - 1) // 10)]

    pages = [
        hikari.Embed(title="✉️ Your reminders:", description="\n".join(content), color=ColorEnum.EMBED_BLUE)
        for content in reminders
    ]
    # TODO: wtf
    navigator = AuthorOnlyNavigator(ctx, pages=pages, timeout=600)
    await navigator.send(ctx.interaction)


@reminders.listener(ReminderEvent, bind=True)
async def on_reminder(plugin: AiryPlugin, event: ReminderEvent):
    """
    Listener for expired reminders
    """
    if event.timer.event != TimerEnum.REMINDER:
        return

    guild = event.get_guild()

    if not guild:
        return

    assert event.timer.channel_id is not None

    user = guild.get_member(event.timer.user_id)

    if not user:
        return

    if not guild:
        return

    assert event.timer.event is not None
    notes = event.timer.extra

    to_ping = [user]

    if len(notes["additional_recipients"]) > 0:
        for user_id in notes["additional_recipients"]:
            member = guild.get_member(user_id)
            if member:
                to_ping.append(member)

    embed = hikari.Embed(
        title=f"✉️ {user.display_name}{f' and {len(to_ping) - 1} others' if len(to_ping) > 1 else ''}, "
              f"your {'snoozed ' if notes.get('is_snoozed') else ''}reminder:",
        description=f"{notes['message']}\n\n[Jump to original message!]({notes['jump_url']})",
        color=ColorEnum.EMBED_BLUE,
    )

    try:
        await plugin.app.rest.create_message(
            event.timer.channel_id,
            content=" ".join([user.mention for user in to_ping]),
            embed=embed,
            components=miru.View().add_item(
                miru.Button(emoji="🕔", label="Snooze!", custom_id=f"RMSS:{event.timer.user_id}")
            ),
            user_mentions=True,
        )
    except (
            hikari.ForbiddenError,
            hikari.NotFoundError,
            hikari.HTTPError,
    ):
        try:
            await user.send(
                content="I lost access to the channel this reminder was sent from, so here it is!",
                embed=embed,
            )

        except hikari.ForbiddenError:
            logger.info(f"Failed to deliver a reminder to user {user}.")


def load(bot: Airy):
    bot.add_plugin(reminders)


def unload(bot: Airy):
    bot.remove_plugin(reminders)
