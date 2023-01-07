## Airy

Multipurpose bot that runs on Discord.

## Running

Nevertheless, the installation steps are as follows:

1. **Make sure to get Python 3.11 or higher**

This is required to actually run the bot.

2. **Set up venv**

Just do `python3.11 -m venv venv`

3. **Install dependencies**

This is `pip install -U -r requirements.txt`

4. **Create the database in PostgreSQL**

You will need PostgreSQL 9.5 or higher and type the following
in the `psql` tool:

```postgresql
CREATE ROLE airy WITH LOGIN PASSWORD 'your_password';
CREATE DATABASE airy OWNER airy;
```

5. **Setup configuration**

The next step is just to create a `.env` file in the root directory where
the bot is with the following template:

```env
BOT_TOKEN="token_here"
BOT_DEV_GUILDS="[guild_ids]"
BOT_DEV_MODE=<True|False>
BOT_ERRORS_TRACE_CHANNEL=<chanel_id>
BOT_INFO_CHANNEL=<chanel_id>
BOT_STATS_CHANNEL=<chanel_id>

POSTGRES_DB=""
POSTGRES_HOST=""
POSTGRES_PASSWORD=""
POSTGRES_PORT=5432
POSTGRES_USER=""
POSTGRES_VERSION=""
```
