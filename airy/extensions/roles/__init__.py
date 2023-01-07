from airy.models.bot import Airy

from .group import group_role_plugin


def load(bot: Airy):
    bot.add_plugin(group_role_plugin)
    # bot.add_plugin(role_buttons)


def unload(bot: Airy):
    bot.remove_plugin(group_role_plugin)
    # bot.remove_plugin(role_buttons)
