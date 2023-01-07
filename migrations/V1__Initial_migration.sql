-- Revises: V0
-- Creation Date: 2022-04-25 03:26:29.804348 UTC
-- Reason: Initial migration

CREATE TABLE IF NOT EXISTS guild
(
    guild_id bigint NOT NULL,
    re_assigns_roles bool default FALSE,
    PRIMARY KEY (guild_id)
);


CREATE TABLE IF NOT EXISTS users
(
    id bigint not null primary key,
    tz text not null
);


CREATE TABLE IF NOT EXISTS guild_users
(
    id serial primary key,
    guild_id bigint not null references guild (guild_id) on delete cascade ,
    user_id bigint not null,
    experience bigint default (0),
        constraint un_guild_users_guld_id_user_id unique (guild_id, user_id)
);


CREATE TABLE IF NOT EXISTS sectionrole
(
    id serial primary key,
    guild_id bigint not null references guild (guild_id) on DELETE cascade ,
    role_id bigint not null
        unique,
    hierarchy smallint default 0 not null,
    constraint un_sectionrole_guild_id_role_id unique (guild_id, role_id)
);


CREATE TABLE IF NOT EXISTS sectionrole_entry
(
    id serial primary key,
    entry_id bigint not null,
    role_id bigint not null references sectionrole (role_id) on delete cascade,
    constraint un_sectionrole_entry_role_id_entry_id unique (role_id, entry_id)
);



CREATE TABLE IF NOT EXISTS autorole
(
  id serial primary key,
  guild_id bigint not null references guild (guild_id) on delete cascade,
  role_id bigint not null,
  constraint un_autorole_guild_id_role_id unique (guild_id, role_id)
);

CREATE TABLE IF NOT EXISTS autorole_for_member
(
    id serial primary key,
    guild_id bigint not null references guild (guild_id) on delete cascade,
    role_id bigint not null,
    user_id bigint not null,
    constraint un_autorole_for_member_guild_id_role_id unique (guild_id, role_id)
);


CREATE TABLE IF NOT EXISTS blacklist
(
    id serial primary key,
    entry_id bigint not null
);


CREATE TABLE IF NOT EXISTS timer
(
    id serial primary key,
    guild_id bigint not null,
    user_id bigint not null,
    channel_id bigint,
    expires timestamp with time zone not null,
    created timestamp with time zone default (now() at time zone 'utc'),
    event smallint not null,
    extra jsonb default ('{}'::jsonb),
    constraint un_timer_id_created unique (id, created)
);


CREATE INDEX IF NOT EXISTS reminders_expires_idx ON timer (expires);


CREATE TABLE IF NOT EXISTS voice_rooms_creators
(
    id serial primary key,
    guild_id bigint not null references guild (guild_id) on delete cascade,
    channel_id bigint not null,
    channel_name text not null,
    user_limit smallint,
    editable boolean not null,
    auto_inc boolean not null,
    sync_permissions boolean not null,
    additional_category_name text not null
);
