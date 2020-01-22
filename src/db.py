import aiosqlite
import logging
import time
import functools
import sqlite3

from datetime import datetime
from typing import Optional, List, Dict, Iterable

import discord
import cogs.utils.pluralKit as pk

log = logging.getLogger("RoleChanger.db")


def db_deco(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            response = await func(*args, **kwargs)
            end_time = time.perf_counter()
            if len(args) > 1:
                log.info("DB Query {} from {} in {:.3f} ms.".format(func.__name__, args[1], (end_time - start_time) * 1000))
            else:
                log.info("DB Query {} in {:.3f} ms.".format(func.__name__, (end_time - start_time) * 1000))
            return response
        except Exception:
        # except asyncpg.exceptions.PostgresError:
            log.exception("Error attempting database query: {} for server: {}".format(func.__name__, args[1]))
    return wrapper


# ---------- Interview Methods ---------- #

# --- Inserts --- #
# @db_deco
# async def add_new_interview(db: str, sid: int, member_id: int, username: str, channel_id: int):
#     async with aiosqlite.connect(db) as conn:
#         await conn.execute(
#             "INSERT INTO interviews(guild_id, member_id, user_name, channel_id, join_ts) VALUES(?, ?, ?, ?, ?)",
#             (sid, member_id, username, channel_id, datetime.utcnow()))
#         await conn.commit()
#

@db_deco
async def add_new_system(db: str, pk_sid: str, system_name: str, current_fronter: str, pk_token: Optional[str] = None):
    async with aiosqlite.connect(db) as conn:
        # Convert ts to int
        update_ts: datetime = datetime.utcnow().timestamp()
        await conn.execute(
            "INSERT INTO systems(pk_sid, system_name, last_update) VALUES(?, ?, ?)",
            (pk_sid, system_name, update_ts))
        await conn.commit()


@db_deco
async def add_linked_discord_account(db: str, pk_sid: str, dis_uid: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "INSERT INTO accounts(dis_uid, pk_sid) VALUES(?, ?)",
            (dis_uid, pk_sid))
        await conn.commit()


@db_deco
async def get_system_id_from_linked_account(db: str, dis_uid: int) -> Optional:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from accounts WHERE dis_uid = ?", (dis_uid,))
        row = await cursor.fetchone()
        # interview_dict = dict(zip(interview_row_map, row))
        # return row_to_interview_dict(row)
        if row is not None and len(row) > 0:
            row = {
                'discord_account': row[0],
                'pk_system_id': row[1]
            }
            return row
        else:
            return None


async def get_all_linked_accounts(db: str, pk_sid: str) -> Optional[List[int]]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute("""SELECT dis_uid
                                       from accounts WHERE pk_sid = ?""", (pk_sid,))
        raw_rows = await cursor.fetchall()

        if len(raw_rows) > 0:
            accounts = [row[0] for row in raw_rows]
            return accounts

        return None


ood_sys_map = ['pk_sid', 'pk_token']
@db_deco
async def get_all_outofdate_systems(db: str, older_than: int = 86400)-> Optional[List[Dict]]:
    async with aiosqlite.connect(db) as conn:
        time = datetime.utcnow().timestamp() - older_than
        log.info(f"time: {time}")

        cursor = await conn.execute("""SELECT systems.pk_sid, systems.pk_token 
                                       from systems WHERE last_update < ?""", (time,))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(ood_sys_map, row)) for row in raw_rows]
        if len(rows) == 0:
            return None
        else:
            return rows


# @db_deco
# async def get_system_from_linked_account_if_ood(db: str, dis_uid: int, older_than: int = 86400)-> Optional[List[Dict]]:
#     async with aiosqlite.connect(db) as conn:
#         time = datetime.utcnow().timestamp() - older_than
#         log.info(f"time: {time}")
#
#         cursor = await conn.execute("""SELECT systems.pk_sid, systems.pk_token
#                                        from systems WHERE last_update < ?""", (time,))
#         raw_rows = await cursor.fetchall()
#         rows = [dict(zip(ood_sys_map, row)) for row in raw_rows]
#         if len(rows) == 0:
#             return None
#         else:
#             return rows


@db_deco
async def add_new_member(db: str, pk_sid: str, pk_mid: str, member_name: str, fronting: bool):
    async with aiosqlite.connect(db) as conn:
        # Convert ts to int
        update_ts: datetime = datetime.utcnow().timestamp()
        await conn.execute(
            "INSERT INTO members(pk_sid, pk_mid, member_name, fronting, last_update) VALUES(?, ?, ?, ?, ?)",
            (pk_sid, pk_mid, member_name, fronting, update_ts))
        await conn.commit()


@db_deco
async def update_member(db: str, pk_sid: str, pk_mid: str, member_name: str, fronting: bool):
    async with aiosqlite.connect(db) as conn:
        # Convert ts to int
        update_ts: datetime = datetime.utcnow().timestamp()

        await conn.execute(
            """insert or ignore into members (pk_sid, pk_mid, member_name, fronting, last_update) values(?,?,?,?,?)""",
            (pk_sid, pk_mid, member_name, fronting, update_ts))

        await conn.execute(
            """UPDATE members
               SET pk_sid = ?, pk_mid = ?, member_name = ?, fronting = ?, last_update = ?
               WHERE pk_mid = ?""",
            (pk_sid, pk_mid, member_name, fronting, update_ts, pk_mid))

        await conn.execute(
            """UPDATE systems
               SET last_update = ?
               WHERE pk_sid = ?""", (update_ts, pk_sid))
        await conn.commit()


# --- Get Member(s) --- #
members_map = ["pk_sid", "pk_mid", "member_name", "fronting", "last_update"]
@db_deco
async def get_members_by_pk_sid(db: str, pk_sid: str) -> List[Dict]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute("""SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update 
                                       from members where pk_sid = ?
                                       COLLATE NOCASE""", (pk_sid, ))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(members_map, row)) for row in raw_rows]
        # rows = []
        # for row in raw_rows:
        #     rows.append(row_to_interview_dict(row))
        return rows


@db_deco
async def get_members_by_discord_account(db: str, discord_user_id: int) -> List[Dict]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute("""
                                    SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = ?""", (discord_user_id, ))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(members_map, row)) for row in raw_rows]
        # rows = []
        # for row in raw_rows:
        #     rows.append(row_to_interview_dict(row))
        return rows


@db_deco
async def get_members_by_discord_account_if_ood(db: str, discord_user_id: int, older_than: int = 86400)-> Optional[List[Dict]]:
    async with aiosqlite.connect(db) as conn:
        # dict_map = []
        time = datetime.utcnow().timestamp() - older_than
        log.info(f"time: {time}")
        cursor = await conn.execute("""
                                        SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update
                                        from members
                                        INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                        WHERE accounts.dis_uid = ? and members.last_update < ?""", (discord_user_id, time))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(ood_sys_map, row)) for row in raw_rows]  # FIXME: The map is wrong.
        if len(rows) == 0:
            return None
        else:
            return rows


@db_deco
async def get_fronting_members_by_pk_sid(db: str, pk_sid: str) -> Optional[List[pk.Member]]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute("""SELECT members.pk_mid 
                                       from members where pk_sid = ? and fronting = 1
                                       COLLATE NOCASE""", (pk_sid, ))
        raw_rows = await cursor.fetchall()
        # rows = [dict(zip(members_map, row)) for row in raw_rows]
        rows = []
        for row in raw_rows:
            rows.append(pk.Member(id=row[0], sid=pk_sid))
        if len(rows) == 0:
            return None
        else:
            return rows


@db_deco
async def get_fronting_members_by_discord_account(db: str, discord_user_id: int) -> Optional[List[pk.Member]]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute("""
                                    SELECT members.pk_mid, members.pk_sid
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = ? and members.fronting = 1""",
                                    (int(discord_user_id), ))
        raw_rows = await cursor.fetchall()
        # rows = [dict(zip(members_map, row)) for row in raw_rows]
        rows = []
        for row in raw_rows:
            rows.append(pk.Member(id=row[0], sid=row[1]))
        if len(rows) == 0:
            return None
        else:
            return rows


@db_deco
async def get_member_by_mid_and_discord_account(db: str, pk_mid: str, discord_user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute("""
                                    SELECT members.pk_sid,  members.pk_mid, members.member_name, members.fronting, members.last_update
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = ? and members.pk_mid = ?
                                    COLLATE NOCASE""", (discord_user_id, pk_mid))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(members_map, row)) for row in raw_rows]
        # rows = []
        # for row in raw_rows:
        #     rows.append(row_to_interview_dict(row))

        if len(rows) == 1:
            return rows[0]
        elif len(rows) == 0:
            log.info(f"Could not find member {pk_mid}.")
        elif len(rows) > 0:
            log.warning(f"Found too many members ({len(rows)}) matching: {pk_mid}. Returning first match.")
            return rows[0]

        return None


@db_deco
async def get_member_by_name_and_discord_account(db: str, member_name: str, discord_user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute("""
                                    SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = ? and members.member_name = ?
                                    COLLATE NOCASE""", (discord_user_id, member_name))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(members_map, row)) for row in raw_rows]
        # rows = []
        # for row in raw_rows:
        #     rows.append(row_to_interview_dict(row))
        if len(rows) == 1:
            return rows[0]
        elif len(rows) == 0:
            log.info(f"Could not find member {member_name}.")
        elif len(rows) > 0:
            log.warning(f"Found too many members ({len(rows)}) matching: {member_name}. Returning first match.")
            return rows[0]

        return None


async def get_member_fuzzy(db: str, discord_user_id: int, search_value: str) -> Optional[Dict]:
    # First search by name then hid

    member = await get_member_by_name_and_discord_account(db, search_value, discord_user_id)
    if member is None:
        member = await get_member_by_mid_and_discord_account(db, search_value, discord_user_id)

    return member



@db_deco
async def get_all_outofdate_members(db: str, older_than: int = 86400)-> Optional[List[Dict]]:
    async with aiosqlite.connect(db) as conn:
        time = datetime.utcnow().timestamp() - older_than
        log.info(f"time: {time}")
        cursor = await conn.execute("""SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update 
                                       from members WHERE last_update < ?""", (time,))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(members_map, row)) for row in raw_rows]

        if len(rows) == 0:
            return None
        else:
            return rows

# --- Roles --- #
@db_deco
async def add_role_to_member(db: str, guild_id: int, pk_mid: str, pk_sid: str, role_id: int) -> bool:
    async with aiosqlite.connect(db) as conn:
        try:
            await conn.execute(
                "INSERT INTO roles(pk_mid, pk_sid, role_id, guild_id) VALUES(?, ?, ?, ?)",
                (pk_mid, pk_sid, role_id, guild_id))
            await conn.commit()
        except sqlite3.InterfaceError as e:
            # Could not enter role into DB as it already exists.
            return False
        return True


@db_deco
async def remove_role_from_member(db: str, guild_id: int, pk_mid: str, role_id: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "DELETE FROM roles WHERE pk_mid = ? and role_id = ? and guild_id = ?",
            (pk_mid, role_id, guild_id))
        await conn.commit()


# @db_deco
# async def add_role_to_system(db: str, guild_id: int, pk_mid: str, role_id: int):
#     async with aiosqlite.connect(db) as conn:
#         await conn.execute(
#             "INSERT INTO roles(pk_mid, role_id, guild_id) VALUES(?, ?, ?)",
#             (pk_mid, role_id, guild_id))
#         await conn.commit()


role_map = ["pk_mid", "pk_sid", "role_id", "guild_id"]
@db_deco
async def get_roles_for_member_by_guild(db: str, pk_mid: str, guild_id: int) -> Optional[List[Dict]]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from roles where pk_mid = ? AND guild_id = ? COLLATE NOCASE", (pk_mid, guild_id))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(role_map, row)) for row in raw_rows]
        if len(rows) == 0:
            return None
        return rows


@db_deco
async def get_roles_for_member(db: str, pk_mid: str) -> Optional[List[Dict]]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from roles where pk_mid = ? COLLATE NOCASE", (pk_mid,))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(role_map, row)) for row in raw_rows]
        if len(rows) == 0:
            return None
        return rows

# --- Settings --- #


class AllowableRoles:
    role_ids: List[int]
    guild_id: int
    roles: Optional[List[discord.Role]]
    row_map = ['role_id', 'guild_id']

    def __init__(self, rows: Iterable[aiosqlite.Row]):
        self.guild_id: int = rows[0][1]  # Guild ID will be the same for every role, so just set it from the first
        self.role_ids = [row[0] for row in rows]

    def allowed_intersection(self, other_roles: List[discord.Role]):
        """ returns list of allowed discord role objects """
        good_roles = []
        for other_role in other_roles:  # Loop through all the other roles.
            for allowed_role_id in self.role_ids:
                if allowed_role_id == other_role.id:
                    good_roles.append(other_role)
                    break

        return good_roles

    def disallowed_intersection(self, other_roles: List[discord.Role]):
        """ returns list of disallowed discord role objects """
        bad_roles = []
        for other_role in other_roles:  # Loop through all the other roles.
            allowed = False
            for allowed_role_id in self.role_ids:
                if allowed_role_id == other_role.id:
                    allowed = True
                    break

            if not allowed:
                bad_roles.append(other_role)

        return bad_roles


class UserSettings:
    pk_sid: str
    guild_id: int
    name_change: bool
    role_change: bool
    row_map = ['pk_sid', 'guild_id', 'name_change', 'role_change']

    def __init__(self, row: aiosqlite.Row):
        self.pk_sid: str = row[0]
        self.guild_id: int = row[1]
        self.name_change: bool = bool(row[2])
        self.role_change: bool = bool(row[3])


@db_deco
async def add_allowable_role(db: str, guild_id: int, role_id: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "INSERT or ignore INTO allowable_roles(role_id, guild_id) VALUES(?, ?)",
            (role_id, guild_id))
        await conn.commit()

# We don't really NEED add_user_settings if we just use update_user_setting instead.
# @db_deco
# async def add_user_setting(db: str, pk_sid: str, guild_id: int, name_change: bool, role_change: bool):
#     async with aiosqlite.connect(db) as conn:
#         await conn.execute(
#             "INSERT INTO user_settings(pk_sid, guild_id, name_change, role_change) VALUES(?, ?, ?, ?)",
#             (pk_sid, guild_id, name_change, role_change))
#         await conn.commit()
#


@db_deco
async def update_user_setting(db: str, pk_sid: str, guild_id: int, name_change: bool, role_change: bool):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            """insert or ignore into user_settings(pk_sid, guild_id, name_change, role_change) VALUES(?, ?, ?, ?)""",
            (pk_sid, guild_id, name_change, role_change))

        await conn.execute(
            """UPDATE user_settings
               SET name_change = ?, role_change = ?
               WHERE pk_sid = ? AND guild_id = ?""",
            (name_change, role_change, pk_sid, guild_id))
        await conn.commit()


@db_deco
async def get_allowable_roles(db: str, guild_id: int) -> Optional[AllowableRoles]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from allowable_roles where guild_id = ?", (guild_id,))
        raw_rows = await cursor.fetchall()

        if len(raw_rows) == 0:
            return None
        allowable_roles = AllowableRoles(raw_rows)
        return allowable_roles


@db_deco
async def get_user_settings(db: str, pk_sid: str, guild_id: int) -> Optional[UserSettings]:
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from user_settings where pk_sid = ? AND guild_id = ? COLLATE NOCASE", (pk_sid, guild_id))
        raw_row = await cursor.fetchone()
        if raw_row is None:
            return None
        user_settings = UserSettings(raw_row)
        return user_settings


@db_deco
async def get_user_settings_from_discord_id(db: str, discord_user_id: str, guild_id: int) -> Optional[UserSettings]:
    async with aiosqlite.connect(db) as conn:
        # cursor = await conn.execute(" SELECT * from user_settings where pk_sid = ? AND guild_id = ? COLLATE NOCASE", (pk_sid, guild_id))
        cursor = await conn.execute("""
                                    SELECT *
                                    from user_settings
                                    INNER JOIN accounts on accounts.pk_sid = user_settings.pk_sid
                                    WHERE accounts.dis_uid = ? AND user_settings.guild_id = ?
                                    """, (discord_user_id, guild_id))
        raw_row = await cursor.fetchone()
        if raw_row is None:
            return None
        user_settings = UserSettings(raw_row)
        return user_settings


@db_deco
async def remove_allowable_role(db: str, guild_id: int, role_id: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "DELETE FROM allowable_roles WHERE guild_id = ? and role_id = ?",
            (guild_id, role_id))
        await conn.commit()


@db_deco
async def remove_user_settings(db: str, pk_sid: str, guild_id: int):
    async with aiosqlite.connect(db) as conn:
        # await conn.execute(
        #     "DELETE FROM roles WHERE pk_mid = ? and role_id = ? and guild_id = ?",
        #     (pk_mid, role_id, guild_id))
        # await conn.commit()

        # This will be implemented when we support removing users when they delete their account or leave the guild.
        raise NotImplementedError




# --- Updates --- #


# --- Selects --- #


# ---------- Table Creation ---------- #
@db_deco
async def create_tables(db: str):
    async with aiosqlite.connect(db) as conn:
        await conn.execute("PRAGMA foreign_keys = 0")
        await conn.execute('''
                               CREATE TABLE if not exists systems (
                               pk_sid               TEXT PRIMARY KEY,
                               system_name          TEXT default 'unknown',
                               pk_token             TEXT DEFAULT NULL,
                               current_fronter      TEXT DEFAULT NULL,
                               last_update          BIGINT
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists members  (
                               pk_mid               TEXT PRIMARY KEY,
                               pk_sid               TEXT NOT NULL,
                               member_name          TEXT default 'unknown',
                               fronting             boolean DEFAULT false,
                               last_update          BIGINT,
                               
                               CONSTRAINT fk_m_system
                                    FOREIGN KEY (pk_sid)
                                    REFERENCES systems(pk_sid)
                                    ON DELETE CASCADE
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists accounts  (
                               dis_uid              BIGINT PRIMARY KEY,
                               pk_sid               TEXT NOT NULL,
                               
                               CONSTRAINT fk_acc_system
                                    FOREIGN KEY (pk_sid)
                                    REFERENCES systems(pk_sid)
                                    ON DELETE CASCADE
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists roles  (             
                               pk_mid               TEXT NOT NULL,
                               pk_sid               TEXT NOT NULL,
                               role_id              bigint not null,
                               guild_id             bigint not null, 
                               UNIQUE (pk_mid, role_id),
                               CONSTRAINT fk_role_member
                                    FOREIGN KEY (pk_mid)
                                    REFERENCES members(pk_mid)
                                    ON DELETE CASCADE
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists allowable_roles  (
                               role_id              bigint NOT NULL,
                               guild_id             bigint not null,
                               PRIMARY KEY (role_id, guild_id)
                            );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists user_settings  (
                               pk_sid               TEXT NOT NULL,
                               guild_id             bigint not null,
                               name_change          boolean default FALSE,
                               role_change          boolean default TRUE,
                               PRIMARY KEY (pk_sid, guild_id)
                            );
                        ''')

        await conn.execute("PRAGMA foreign_keys = 1")