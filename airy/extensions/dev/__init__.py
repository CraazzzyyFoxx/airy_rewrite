from __future__ import annotations

import ast
import shlex
import subprocess
import textwrap
import traceback
import typing as t

import hikari
import lightbulb
import miru
from miru.ext import nav

from airy.models import AuthorOnlyNavigator, AiryPrefixContext, AuthorOnlyView, DatabaseBlacklist
from airy.utils.embeds import RespondEmbed

dev = lightbulb.Plugin("Development")
dev.add_checks(lightbulb.owner_only)

if t.TYPE_CHECKING:
    from airy.models.bot import Airy


class TrashButton(nav.NavButton):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.SECONDARY, emoji="🗑️", row=1)

    async def callback(self, ctx: miru.ViewContext) -> None:
        await self.view.message.delete()
        self.view.stop()


class OutputNav(AuthorOnlyNavigator):
    async def on_timeout(self) -> None:
        try:
            assert self.message is not None
            return await self.message.delete()
        except hikari.NotFoundError:
            pass


class TrashView(AuthorOnlyView):
    @miru.button(emoji="🗑️", style=hikari.ButtonStyle.SECONDARY)
    async def trash(self, button: miru.Button, ctx: miru.ViewContext) -> None:
        assert self.message is not None
        await self.message.delete()
        self.stop()

    async def on_timeout(self) -> None:
        try:
            assert self.message is not None
            return await self.message.delete()
        except hikari.NotFoundError:
            pass


def format_output(text: str) -> str:
    # Escape markdown fmt
    return text.replace("```py", "").replace("```ansi", "").replace("`", "´")


async def send_paginated(
        ctx: AiryPrefixContext,
        messageable: hikari.SnowflakeishOr[t.Union[hikari.TextableChannel, hikari.User]],
        text: str,
        *,
        prefix: str = "",
        suffix: str = "",
) -> None:
    """
    Send command output paginated if appropriate.
    """
    text = str(text)
    channel_id = None
    if not isinstance(messageable, hikari.User):
        channel_id = hikari.Snowflake(messageable)

    if len(text) <= 2000:
        if channel_id:
            view = TrashView(ctx, timeout=300)
            message = await ctx.app.rest.create_message(
                channel_id, f"{prefix}{format_output(text)}{suffix}", components=view.build()
            )
            return await view.start(message)
        else:
            assert isinstance(messageable, (hikari.TextableChannel, hikari.User))
            await messageable.send(f"{prefix}{format_output(text)}{suffix}")
            return

    buttons = [
        nav.FirstButton(),
        nav.PrevButton(),
        nav.IndicatorButton(),
        nav.NextButton(),
        nav.LastButton(),
        TrashButton(),
    ]
    paginator = lightbulb.utils.StringPaginator(prefix=prefix, suffix=suffix, max_chars=2000)

    for line in text.split("\n"):
        paginator.add_line(format_output(line))

    navmenu = OutputNav(ctx, pages=list(paginator.build_pages()), buttons=buttons, timeout=300)

    if not channel_id:
        assert isinstance(messageable, hikari.User)
        channel_id = await messageable.fetch_dm_channel()

    await navmenu.send(channel_id)


async def run_shell(ctx: AiryPrefixContext, code: str) -> None:
    """
    Run code in shell and return output to Discord.
    """

    code = str(code).replace("```py", "").replace("`", "").strip()

    await ctx.app.rest.trigger_typing(ctx.channel_id)
    try:
        result = subprocess.run(shlex.split(code), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
    except subprocess.TimeoutExpired as e:
        await ctx.event.message.add_reaction("❗")
        out = e.stderr or e.stdout
        out: str = ":\n" + out.decode("utf-8") if out else ""  # type: ignore

        return await send_paginated(ctx, ctx.channel_id, "Process timed out" + out, prefix="```ansi\n", suffix="```")

    if result.returncode != 0:
        await ctx.event.message.add_reaction("❗")
        if result.stderr and result.stderr.decode("utf-8"):
            return await send_paginated(
                ctx, ctx.channel_id, result.stderr.decode("utf-8"), prefix="```ansi\n", suffix="```"
            )

    await ctx.event.message.add_reaction("✅")
    if result.stdout and result.stdout.decode("utf-8"):
        await send_paginated(ctx, ctx.channel_id, result.stdout.decode("utf-8"), prefix="```ansi\n", suffix="```")


@dev.command
@lightbulb.option("extension_name", "The name of the extension to reload.")
@lightbulb.command("reload", "Reload an extension.", pass_options=True)
@lightbulb.implements(lightbulb.PrefixCommand)
async def reload_cmd(ctx: AiryPrefixContext, extension_name: str) -> None:
    ctx.app.reload_service(extension_name)
    await ctx.event.message.add_reaction("✅")
    await ctx.respond(f"🔃 `{extension_name}`")


@dev.command
@lightbulb.option("extension_name", "The name of the extension to load.")
@lightbulb.command("load", "Load an extension.", pass_options=True)
@lightbulb.implements(lightbulb.PrefixCommand)
async def load_cmd(ctx: AiryPrefixContext, extension_name: str) -> None:
    ctx.app.load_extensions(extension_name)
    await ctx.event.message.add_reaction("✅")
    await ctx.respond(f"📥 `{extension_name}`")


@dev.command
@lightbulb.option("extension_name", "The name of the extension to unload.")
@lightbulb.command("unload", "Unload an extension.", pass_options=True)
@lightbulb.implements(lightbulb.PrefixCommand)
async def unload_cmd(ctx: AiryPrefixContext, extension_name: str) -> None:
    ctx.app.unload_extensions(extension_name)
    await ctx.event.message.add_reaction("✅")
    await ctx.respond(f"📤 `{extension_name}`")


@dev.command
@lightbulb.option("code", "Code to execute.", modifier=lightbulb.OptionModifier.CONSUME_REST)
@lightbulb.command("py", "Run code.", pass_options=True)
@lightbulb.implements(lightbulb.PrefixCommand)
async def eval_py(ctx: AiryPrefixContext, code: str) -> None:
    globals_dict = {
        "_author": ctx.author,
        "_bot": ctx.bot,
        "_app": ctx.app,
        "_channel": ctx.get_channel(),
        "_guild": ctx.get_guild(),
        "_message": ctx.event.message,
        "_ctx": ctx,
    }

    code = code.replace("```py", "").replace("`", "").strip()

    # Check if last line is an expression and return it if so
    abstract_syntax_tree = ast.parse(code, filename=f"{ctx.guild_id}{ctx.channel_id}.py")
    node: t.List[ast.stmt] = abstract_syntax_tree.body

    if node and type(node[0]) is ast.Expr:
        code_split = code.split("\n")
        code_split[-1] = f"return {code_split[-1]}"
        code = "\n".join(code_split)

    code_func = f"async def _container():\n" + textwrap.indent(code, "   ")

    async with ctx.app.rest.trigger_typing(ctx.channel_id):
        try:
            exec(code_func, globals_dict, locals())
            return_value = await locals()["_container"]()

            await ctx.event.message.add_reaction("✅")

            if return_value is not None:
                await send_paginated(ctx, ctx.channel_id, return_value, prefix="```py\n", suffix="```")

        except Exception as e:
            embed = RespondEmbed.error(title="Exception encountered",
                                       description=f"```{e.__class__.__name__}: {e}```", )

            try:
                await ctx.event.message.add_reaction("❗")
                await ctx.respond(embed=embed)
            except hikari.ForbiddenError:
                pass

            traceback_msg = "\n".join(traceback.format_exception(type(e), e, e.__traceback__))
            await send_paginated(ctx, ctx.author, traceback_msg, prefix="```py\n", suffix="```")


@dev.command
@lightbulb.option("code", "Code to execute.", modifier=lightbulb.OptionModifier.CONSUME_REST)
@lightbulb.command("sh", "Run code.", pass_options=True)
@lightbulb.implements(lightbulb.PrefixCommand)
async def eval_sh(ctx: AiryPrefixContext, code: str) -> None:
    await run_shell(ctx, code)


@dev.command
@lightbulb.option("code", "Code to execute.", modifier=lightbulb.OptionModifier.CONSUME_REST)
@lightbulb.command("git", "Run git commands.", pass_options=True)
@lightbulb.implements(lightbulb.PrefixCommand)
async def dev_git_pull(ctx: AiryPrefixContext, code: str) -> None:
    await run_shell(ctx, f"git {code}")


@dev.command
@lightbulb.option(
    "--force", "If True, purges application commands before re-registering them.", type=bool, required=False
)
@lightbulb.command("sync", "Sync application commands.")
@lightbulb.implements(lightbulb.PrefixCommand)
async def resync_app_cmds(ctx: AiryPrefixContext) -> None:
    await ctx.app.rest.trigger_typing(ctx.channel_id)
    if ctx.options["--force"]:
        await ctx.app.purge_application_commands(*ctx.app.default_enabled_guilds, global_commands=True)

    await ctx.app.sync_application_commands()
    await ctx.event.message.add_reaction("✅")
    await ctx.respond("🔃 Synced application commands.")


@dev.command
@lightbulb.command("sql", "Execute an SQL file")
@lightbulb.implements(lightbulb.PrefixCommand)
async def run_sql(ctx: AiryPrefixContext) -> None:
    if not ctx.attachments or not ctx.attachments[0].filename.endswith(".sql"):
        embed = RespondEmbed.error(title="No valid attachment",
                                   description=f"Expected a singular `.sql` file as attachment with `UTF-8` encoding!")
        await ctx.respond(embed=embed)
        return

    await ctx.app.rest.trigger_typing(ctx.channel_id)
    sql: str = (await ctx.attachments[0].read()).decode("utf-8")

    async with ctx.bot.db.acquire() as conn:
        return_value = await conn.execute(sql)

    await ctx.event.message.add_reaction("✅")
    await send_paginated(ctx, ctx.channel_id, str(return_value), prefix="```sql\n", suffix="```")


@dev.command
@lightbulb.command("shutdown", "Shut down the bot.")
@lightbulb.implements(lightbulb.PrefixCommand)
async def shutdown_cmd(ctx: AiryPrefixContext) -> None:
    confirm_payload = {"content": f"⚠️ Shutting down...", "components": []}
    cancel_payload = {"content": "❌ Shutdown cancelled", "components": []}
    confirmed = await ctx.confirm(
        "Are you sure you want to shut down the application?",
        confirm_payload=confirm_payload,
        cancel_payload=cancel_payload,
    )
    if confirmed:
        await ctx.event.message.add_reaction("✅")
        return await ctx.app.close()
    await ctx.event.message.add_reaction("❌")


@dev.command
@lightbulb.option("user", "The user to manage.", type=hikari.User)
@lightbulb.option("mode", "The mode of operation.", type=str)
@lightbulb.command("blacklist", "Commands to manage the blacklist.", pass_options=True)
@lightbulb.implements(lightbulb.PrefixCommand)
async def blacklist_cmd(ctx: AiryPrefixContext, mode: str, user: hikari.User) -> None:
    if user.id == ctx.user.id:
        await ctx.event.message.add_reaction("❌")
        await ctx.respond("❌ Cannot blacklist self")
        return

    entry = await DatabaseBlacklist.fetch(user.id)

    if mode.casefold() == "add":
        if entry:
            await ctx.event.message.add_reaction("❌")
            await ctx.respond("❌ Already blacklisted")
            return

        await DatabaseBlacklist.create(entry=user.id)

        await ctx.event.message.add_reaction("✅")
        await ctx.respond("✅ User added to blacklist")
    elif mode.casefold() in ["del", "delete", "remove"]:
        if not entry:
            await ctx.event.message.add_reaction("❌")
            await ctx.respond("❌ Not blacklisted")
            return

        await entry.delete()
        await ctx.event.message.add_reaction("✅")
        await ctx.respond("✅ User removed from blacklist")

    else:
        await ctx.event.message.add_reaction("❌")
        await ctx.respond("❌ Invalid mode\nValid modes:`add`, `del`.")


@dev.command
@lightbulb.option("guild_id", "The guild_id to reset all settings for.", type=int)
@lightbulb.command("resetsettings", "Reset all settings for the specified guild.", pass_options=True)
@lightbulb.implements(lightbulb.PrefixCommand)
async def resetsettings_cmd(ctx: AiryPrefixContext, guild_id: int) -> None:
    guild = ctx.app.cache.get_guild(guild_id)

    if not guild:
        await ctx.event.message.add_reaction("❌")
        await ctx.respond("❌ Guild not found.")
        return

    confirmed = await ctx.confirm(
        f"Are you sure you want to wipe all settings for guild `{guild.id}`?",
        cancel_payload={"content": "❌ Cancelled", "components": []},
        confirm_payload={"content": "✅ Confirmed", "components": []},
    )

    if not confirmed:
        return await ctx.event.message.add_reaction("❌")

    await ctx.bot.db.wipe_guild(guild, keep_record=True)

    await ctx.event.message.add_reaction("✅")
    await ctx.respond(f"✅ Wiped data for guild `{guild.id}`.")


def load(bot: "Airy") -> None:
    bot.add_plugin(dev)


def unload(bot: "Airy") -> None:
    bot.remove_plugin(dev)
