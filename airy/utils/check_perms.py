import logging

import hikari
import lightbulb

from airy.models.bot import Airy
from airy.models import AirySlashContext
from airy.etc import RespondEmojiEnum, get_perm_str


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
    hikari.Permissions.EMBED_LINKS: "Required for the bot to create embed to display content, without this you may "
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


async def check_bot_permissions(app: Airy, guild: hikari.Snowflake):
    me = app.cache.get_member(guild, app.user_id)
    assert me is not None

    perms = lightbulb.utils.permissions_for(me)
    missing_perms = ~perms & REQUIRED_PERMISSIONS
    return missing_perms


def to_str_permissions(perms: hikari.Permissions) -> str:
    content = [
        f"{RespondEmojiEnum.ERROR} **{get_perm_str(perm)}**: {desc}"
        for perm, desc in PERM_DESCRIPTIONS.items() if perms & perm
    ]

    return "\n".join(content)



