import asyncio
import datetime
import json
import os
import re
import traceback
import typing
import uuid

from pathlib import Path

import asyncpg  # type: ignore
import click

from airy.config import db_config


class Revisions(typing.TypedDict):
    # The version key represents the current activated version
    # So v1 means v1 is active and the next revision should be v2
    # In order for this to work the number has to be monotonically increasing
    # and have no gaps
    version: int
    database_uri: str


REVISION_FILE = re.compile(r'(?P<kind>V|U)(?P<version>[0-9]+)__(?P<description>.+).sql')


class Revision:
    __slots__ = ('kind', 'version', 'description', 'file')

    def __init__(self, *, kind: str, version: int, description: str, file: Path) -> None:
        self.kind: str = kind
        self.version: int = version
        self.description: str = description
        self.file: Path = file

    @classmethod
    def from_match(cls, match: re.Match[str], file: Path):
        return cls(
            kind=match.group('kind'), version=int(match.group('version')), description=match.group('description'), file=file
        )


class Migrations:
    def __init__(self, *, filename: str = 'migrations/revisions.json'):
        self.filename: str = filename
        self.root: Path = Path(filename).parent
        self.revisions: dict[int, Revision] = self.get_revisions()

        self.ensure_path()
        data = self.load_metadata()
        self.version: int = data['version']
        self.database_uri: str = data['database_uri']

    def ensure_path(self) -> None:
        self.root.mkdir(exist_ok=True)

    def load_metadata(self) -> Revisions:
        try:
            with open(self.filename, 'r', encoding='utf-8') as fp:
                return json.load(fp)
        except FileNotFoundError:
            return {
                'version': 0,
                'database_uri': f"postgres://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.db}",
            }

    def get_revisions(self) -> dict[int, Revision]:
        result: dict[int, Revision] = {}
        for file in self.root.glob('*.sql'):
            match = REVISION_FILE.match(file.name)
            if match is not None:
                rev = Revision.from_match(match, file)
                result[rev.version] = rev

        return result

    def dump(self) -> Revisions:
        return {
            'version': self.version,
            'database_uri': self.database_uri,
        }

    def save(self):
        temp = f'{self.filename}.{uuid.uuid4()}.tmp'
        with open(temp, 'w', encoding='utf-8') as tmp:
            json.dump(self.dump(), tmp)

        # atomically move the file
        os.replace(temp, self.filename)

    def is_next_revision_taken(self) -> bool:
        return self.version + 1 in self.revisions

    @property
    def ordered_revisions(self) -> list[Revision]:
        return sorted(self.revisions.values(), key=lambda r: r.version)

    def create_revision(self, reason: str, *, kind: str = 'V') -> Revision:
        cleaned = re.sub(r'\s', '_', reason)
        filename = f'{kind}{self.version + 1}__{cleaned}.sql'
        path = self.root / filename

        stub = (
            f'-- Revises: V{self.version}\n'
            f'-- Creation Date: {datetime.datetime.utcnow()} UTC\n'
            f'-- Reason: {reason}\n\n'
        )

        with open(path, 'w', encoding='utf-8', newline='\n') as fp:
            fp.write(stub)

        self.save()
        return Revision(kind=kind, description=reason, version=self.version + 1, file=path)

    async def upgrade(self, connection: asyncpg.Connection) -> int:
        ordered = self.ordered_revisions
        successes = 0
        async with connection.transaction():
            for revision in ordered:
                if revision.version > self.version:
                    sql = revision.file.read_text('utf-8')
                    await connection.execute(sql)
                    successes += 1

        self.version += successes
        self.save()
        return successes

    def display(self) -> None:
        ordered = self.ordered_revisions
        for revision in ordered:
            if revision.version > self.version:
                sql = revision.file.read_text('utf-8')
                click.echo(sql)


@click.group()
def cli():
    from airy.utils import logging

    logging.setup()


@cli.command()
def run():
    """
    Start application
    """

    from airy import misc
    misc.setup()


@cli.group(short_help='database stuff', options_metavar='[options]')
def db():
    pass


async def ensure_uri_can_run() -> bool:
    dsn = f"postgres://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.db}"
    connection: asyncpg.Connection = await asyncpg.connect(dsn=dsn)
    await connection.close()
    return True


@db.command()
@click.option('--reason', '-r', help='The reason for this revision.', default='Initial migration')
def init(reason):
    """Initializes the database and creates the initial revision."""
    asyncio.run(ensure_uri_can_run())

    migrations = Migrations()
    revision = migrations.create_revision(reason)
    click.echo(f'created revision V{revision.version!r}')
    click.secho(f'hint: use the `upgrade` command to apply', fg='yellow')


@db.command()
@click.option('--reason', '-r', help='The reason for this revision.', required=True)
def migrate(reason):
    """Creates a new revision for you to edit."""
    migrations = Migrations()
    if migrations.is_next_revision_taken():
        click.echo('an unapplied migration already exists for the next version, exiting')
        click.secho('hint: apply pending migrations with the `upgrade` command', bold=True)
        return

    revision = migrations.create_revision(reason)
    click.echo(f'Created revision V{revision.version!r}')


async def run_upgrade(migrations: Migrations) -> int:
    connection: asyncpg.Connection = await asyncpg.connect(migrations.database_uri)  # type: ignore
    return await migrations.upgrade(connection)


@db.command()
@click.option('--sql', help='Print the SQL instead of executing it', is_flag=True)
def upgrade(sql):
    """Upgrades the database at the given revision (if any)."""
    migrations = Migrations()

    if sql:
        migrations.display()
        return

    try:
        applied = asyncio.run(run_upgrade(migrations))
    except Exception:
        traceback.print_exc()
        click.secho('failed to apply migrations due to error', fg='red')
    else:
        click.secho(f'Applied {applied} revisions(s)', fg='green')


@db.command()
def current():
    """Shows the current active revision version"""
    migrations = Migrations()
    click.echo(f'Version {migrations.version}')


@db.command()
@click.option('--reverse', help='Print in reverse order (oldest first).', is_flag=True)
def log(reverse):
    """Displays the revision history"""
    migrations = Migrations()
    # Revisions is the oldest first already
    revs = reversed(migrations.ordered_revisions) if not reverse else migrations.ordered_revisions
    for rev in revs:
        as_yellow = click.style(f'V{rev.version:>03}', fg='yellow')
        click.echo(f'{as_yellow} {rev.description.replace("_", " ")}')
