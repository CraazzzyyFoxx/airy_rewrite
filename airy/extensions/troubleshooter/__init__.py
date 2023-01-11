import logging

import hikari
import lightbulb

from airy.models.bot import Airy
from airy.models import AirySlashContext
from airy.etc import RespondEmojiEnum, get_perm_str
from airy.utils import RespondEmbed

logger = logging.getLogger(__name__)

troubleshooter = lightbulb.Plugin("Troubleshooter")

# Find perms issues
# Find automod config issues
# Find missing channel perms issues
# ...

REQUIRED_PERMISSIONS = (
    hikari.Permissions.VIEW_AUDIT_LOG
    | hikari.Permissions.MANAGE_ROLES
    | hikari.Permissions.MANAGE_CHANNELS
    | hikari.Permissions.CHANGE_NICKNAME
    | hikari.Permissions.READ_MESSAGE_HISTORY
    | hikari.Permissions.VIEW_CHANNEL
    | hikari.Permissions.SEND_MESSAGES
    | hikari.Permissions.SEND_MESSAGES_IN_THREADS
    | hikari.Permissions.EMBED_LINKS
    | hikari.Permissions.ATTACH_FILES
    | hikari.Permissions.MENTION_ROLES
    | hikari.Permissions.USE_EXTERNAL_EMOJIS
    | hikari.Permissions.MODERATE_MEMBERS
    | hikari.Permissions.MANAGE_MESSAGES
    | hikari.Permissions.ADD_REACTIONS
    | hikari.Permissions.USE_EXTERNAL_EMOJIS
    | hikari.Permissions.SPEAK
)

# Explain why the bot requires the perm
PERM_DESCRIPTIONS = {
    hikari.Permissions.VIEW_AUDIT_LOG: "Required in logs to fill in details such as who the moderator in question "
                                       "was, or the reason of the action.",
    hikari.Permissions.MANAGE_ROLES: "Required to give users roles via role-buttons.",
    hikari.Permissions.MANAGE_CHANNELS: "This permission is currently unused, and reserved for future functionality.",
    hikari.Permissions.KICK_MEMBERS: "Required to use the `/kick` command and let auto-moderation actions kick users.",
    hikari.Permissions.BAN_MEMBERS: "Required to use the `/ban`, `/softban`, `/massban` command and let "
                                    "auto-moderation actions ban users.",
    hikari.Permissions.CHANGE_NICKNAME: "Required for the `/setnick` command.",
    hikari.Permissions.READ_MESSAGE_HISTORY: "Required for auto-moderation, starboard, `/edit`, and other commands "
                                             "that may require to fetch messages.",
    hikari.Permissions.VIEW_CHANNEL: "Required for auto-moderation, starboard, `/edit`, and other commands that may "
                                     "require to fetch messages.",
    hikari.Permissions.SEND_MESSAGES: "Required to send messages independently of commands, this includes `/echo`, "
                                      "`/edit`, logging, starboard, reports and auto-moderation.",
    hikari.Permissions.CREATE_PUBLIC_THREADS: "Required for the bot to access and manage threads.",
    hikari.Permissions.CREATE_PRIVATE_THREADS: "Required for the bot to access and manage threads.",
    hikari.Permissions.SEND_MESSAGES_IN_THREADS: "Required for the bot to access and manage threads.",
    hikari.Permissions.MANAGE_THREADS: "This permissions is currently unused, and reserved for future functionality.",
    hikari.Permissions.EMBED_LINKS: "Required for the bot to create embeds to display content, without this you may "
                                    "not see any responses from the bot, including this one :)",
    hikari.Permissions.ATTACH_FILES: "Required for the bot to attach files to a message, for example to send a list "
                                     "of users to be banned in `/massban`.",
    hikari.Permissions.MENTION_ROLES: "Required for the bot to always be able to mention roles, for example when "
                                      "reporting users. The bot will **never** mention @everyone or @here.",
    hikari.Permissions.USE_EXTERNAL_EMOJIS: "Required to display certain content with custom emojies, typically to "
                                            "better illustrate certain content.",
    hikari.Permissions.ADD_REACTIONS: "This permission is used for creating giveaways and adding the initial reaction "
                                      "to the giveaway message.",
    hikari.Permissions.MODERATE_MEMBERS: "Required to use the `/timeout` command and let auto-moderation actions "
                                         "timeout users.",
    hikari.Permissions.MANAGE_MESSAGES: "This permission is required to delete other user's messages, for example in "
                                        "the case of auto-moderation.",
    hikari.Permissions.SPEAK: "This permission is necessary to play music",
}


@troubleshooter.command
@lightbulb.command("troubleshoot", "Diagnose and locate common configuration issues.", app_command_dm_enabled=False)
@lightbulb.implements(lightbulb.SlashCommand)
async def troubleshoot(ctx: AirySlashContext) -> None:

    assert ctx.guild_id is not None

    me = ctx.app.cache.get_member(ctx.guild_id, ctx.app.user_id)
    assert me is not None

    perms = lightbulb.utils.permissions_for(me)
    missing_perms = ~perms & REQUIRED_PERMISSIONS
    content = []

    if missing_perms is not hikari.Permissions.NONE:
        content.append("**Missing Permissions:**")
        content += [
            f"{RespondEmojiEnum.ERROR} **{get_perm_str(perm)}**: {desc}"
            for perm, desc in PERM_DESCRIPTIONS.items() if missing_perms & perm
        ]

    if not content:
        embed = RespondEmbed.success(
            title="No problems found!",
            description="If you believe there is an issue with Airy, found a bug, or simply have a question, "
                        "please join the [support server!](https://discord.gg/J4Dy8dTARf)"
        )
    else:
        content = "\n".join(content)  # type: ignore
        embed = RespondEmbed.error(
            title="Uh Oh!",
            description=f"It looks like there may be some issues with the configuration. Please review the list "
                        f"below!\n\n{content}\n\nIf you need any assistance resolving these issues, please join the ["
                        f"support server!](https://discord.gg/J4Dy8dTARf)")

    await ctx.respond(embed=embed)


def load(bot: Airy) -> None:
    bot.add_plugin(troubleshooter)


def unload(bot: Airy) -> None:
    bot.remove_plugin(troubleshooter)
