import hikari

from hikari.internal.enums import Enum


class ColorEnum(int, Enum):
    default = 0
    teal = 0x1abc9c
    dark_teal = 0x11806a
    green = 0x2ecc71
    dark_green = 0x1f8b4c
    blue = 0x3498db
    dark_blue = 0x206694
    purple = 0x9b59b6
    dark_purple = 0x71368a
    magenta = 0xe91e63
    dark_magenta = 0xad1457
    gold = 0xf1c40f
    dark_gold = 0xc27c0e
    orange = 0xe67e22
    dark_orange = 0xa84300
    red = 0xe74c3c
    dark_red = 0x992d22
    lighter_grey = 0x95a5a6
    dark_grey = 0x607d8b
    light_grey = 0x979c9f
    darker_grey = 0x546e7a
    blurple = 0x7289da
    grey = 0x99aab5
    dark_theme = 0x36393F

    ERROR: int = 0xFF0000
    WARN: int = 0xFFCC4D
    EMBED_BLUE: int = 0x009DFF
    EMBED_GREEN: int = 0x77B255
    UNKNOWN: int = 0xBE1931
    MISC: int = 0xC2C2C2


class RespondEmojiEnum(str, Enum):
    SUCCESS = "<:greenTick:882620180365185086>"
    ERROR = "<:redTick:882620191178129479>"
    NONE = "<:greyTick:882620201764524122>"
    COOLDOWN = "<:timer:959571499918983198>"


class RespondIconsEnum(str, Enum):
    SUCCESS = str(hikari.files.URL("https://cdn.discordapp.com/emojis/1062890067330343004"))
    ERROR = str(hikari.files.URL("https://cdn.discordapp.com/emojis/1062890056139935925"))
    NONE = str(hikari.files.URL("https://cdn.discordapp.com/emojis/882620201764524122"))
    COOLDOWN = str(hikari.files.URL("https://cdn.discordapp.com/emojis/1062889959721283594"))
    HELP = str(hikari.files.URL("https://cdn.discordapp.com/emojis/1062891169761206373"))


class MenuEmojiEnum(str, Enum):
    ADD = "<:icons8add:1062890029615173742>"
    REMOVE = "<:icons8remove:1062890013831987220>"
    SAVE = "<:icons8save:1062889982144036955>"
    TRASHCAN = "<:icons8trashcan:1062890043691237520>"


class MenuIconsEnum(str, Enum):
    ADD = str(hikari.files.URL("https://cdn.discordapp.com/emojis/1062890029615173742"))
    REMOVE = str(hikari.files.URL("https://cdn.discordapp.com/emojis/1062890013831987220"))
    SAVE = str(hikari.files.URL("https://cdn.discordapp.com/emojis/1062889982144036955"))
    TRASHCAN = str(hikari.files.URL("https://cdn.discordapp.com/emojis/1062890043691237520"))


class EmojisEnum(str, Enum):
    TEXT_CHANNEL = "<:text_channel:882620127672148019>"
    VOICE_CHANNEL = "<:voice_channel:882620160769417257>"
    STAGE_CHANNEL = "<:stage_channel:882620101222871141>"
    MENTION = "<:mention:658538492019867683>"
    SLOWMODE = "<:slowmode:951913313577603133>"
    MOD_SHIELD = "<:mod_shield:923752735768190976>"

    bullet = "\u2022"
    check_mark = "\u2705"
    cross_mark = "\u274C"
    new = "\U0001F195"
    pencil = "\u270F"
