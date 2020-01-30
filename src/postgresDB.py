import logging
import time
import functools

from datetime import datetime
from typing import Optional, List, Dict, Iterable, Union, NamedTuple

import aiosqlite
import sqlite3

import asyncpg

import discord
import cogs.utils.pluralKit as pk


log = logging.getLogger("ARC.pDB")



# --- Utility DB Functions --- #
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
        # except Exception:
        except asyncpg.exceptions.PostgresError:
            if len(args) > 1:
                log.exception("Error attempting database query: {} for server: {}".format(func.__name__, args[1]))
            else:
                log.exception("Error attempting database query: {}".format(func.__name__))
    return wrapper


async def create_db_pool(uri: str) -> asyncpg.pool.Pool:

    # FIXME: Error Handling

    pool: asyncpg.pool.Pool = await asyncpg.create_pool(uri)

    return pool

# async def test():
#     return DBGuildSettings(guild_id=1)


# --- System DB Functions --- #
@db_deco
async def add_new_system(pool: asyncpg.pool.Pool, pk_sid: str, system_name: str, current_fronter: str, pk_system_tag: Optional[str], pk_token: Optional[str] = None):
    """ """
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        update_ts =  datetime.utcnow().timestamp()
        await conn.execute(
            "INSERT INTO systems(pk_sid, system_name, pk_system_tag, pk_token, last_update) VALUES($1, $2, $3, $4, $5)",
             pk_sid, system_name, pk_system_tag, pk_token, update_ts)


# --- System DB Functions --- #
@db_deco
async def remove_system(pool: asyncpg.pool.Pool, pk_sid: str):
    """ """
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "DELETE FROM systems WHERE pk_sid = $1",
             pk_sid)


@db_deco
async def add_linked_discord_account(pool: asyncpg.pool.Pool, pk_sid: str, dis_uid: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "INSERT INTO accounts(dis_uid, pk_sid) VALUES($1, $2)",
             dis_uid, pk_sid)



@db_deco
async def get_system_id_by_discord_account(pool: asyncpg.pool.Pool, dis_uid: int) -> Optional[Dict]:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        raw_row = await conn.fetchrow(" SELECT * from accounts WHERE dis_uid = $1", dis_uid)
        # TODO: Settle on a name.
        if raw_row is not None:
            row = {
                    'discord_account': raw_row['dis_uid'],
                    'dis_uid': raw_row['dis_uid'],
                    'pk_system_id': raw_row['pk_sid'],
                    'pk_sid': raw_row['pk_sid']
                }
            return row
        else:
            return None


class DBSystem(NamedTuple):
    pk_sid: str
    system_name: Optional[str]
    pk_token: Optional[str]
    current_fronter: Optional[str]
    pk_system_tag: Optional[str]
    last_update: int


@db_deco
async def get_system_by_discord_account(pool: asyncpg.pool.Pool, dis_uid: int) -> Optional[DBSystem]:
    """ Returns just the pk_system_tag column from one row of 'systems' for a given pk system id."""
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        raw_row = await conn.fetchrow("""SELECT systems.pk_sid, systems.system_name, systems.pk_token, systems.current_fronter, systems.pk_system_tag, systems.last_update 
                                         from systems 
                                         INNER JOIN accounts on accounts.pk_sid = systems.pk_sid
                                         WHERE accounts.dis_uid = $1
                                         """, dis_uid)
        if raw_row is not None:
            return DBSystem(**raw_row)
        else:
            return None


@db_deco
async def update_system_by_pk_sid(pool: asyncpg.pool.Pool, pk_sid: str, system_name: str, system_tag: str):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        time = datetime.utcnow().timestamp()
        # No exceptions when UPDATE nonexistant roes.
        system_tag_map = ['pk_system_tag', 'system_tag_override', 'system_name']

        await conn.execute("""UPDATE systems
                              SET pk_system_tag = $1, system_name = $2, last_update = $3
                              WHERE pk_sid = $4""", system_tag, system_name, time, pk_sid)




@db_deco
async def get_all_linked_accounts(pool: asyncpg.pool.Pool, pk_sid: str) -> Optional[List[int]]:  # Not currently in use.
    """ Gets all of the discord account IDs that are linked to a PK Account via the system ID."""
    raise NotImplementedError
    # async with aiosqlite.connect(db) as conn:
    #     cursor = await conn.execute("""SELECT dis_uid
    #                                    from accounts WHERE pk_sid = ?""", (pk_sid,))
    #     raw_rows = await cursor.fetchall()
    #
    #     if len(raw_rows) > 0:
    #         accounts = [row[0] for row in raw_rows]
    #         return accounts
    #
    #     return None


# Currently Unused...
@db_deco
async def get_all_outofdate_systems(pool: asyncpg.pool.Pool, older_than: int = 86400)-> Optional[List[Dict]]:  # Not currently in use.
    """ Returns the systemID and token for all systems whos data has gone stale per 'older_than'."""
    raise NotImplementedError
    # ood_sys_map = ['pk_sid', 'pk_token']
    # async with aiosqlite.connect(db) as conn:
    #     time = datetime.utcnow().timestamp() - older_than
    #     log.info(f"time: {time}")
    #
    #     cursor = await conn.execute("""SELECT systems.pk_sid, systems.pk_token
    #                                    from systems WHERE last_update < ?""", (time,))
    #     raw_rows = await cursor.fetchall()
    #     rows = [dict(zip(ood_sys_map, row)) for row in raw_rows]
    #     if len(rows) == 0:
    #         return None
    #     else:
    #         return rows


# @db_deco
# async def get_system_from_linked_account_if_ood(pool: asyncpg.pool.Pool, dis_uid: int, older_than: int = 86400)-> Optional[List[Dict]]:
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

# --- Add/Update/Delete Member(s) --- #


@db_deco
async def add_new_member(pool: asyncpg.pool.Pool, pk_sid: str, pk_mid: str, member_name: str, fronting: bool):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        # Convert ts to int
        update_ts: datetime = datetime.utcnow().timestamp()
        await conn.execute(
            "INSERT INTO members(pk_sid, pk_mid, member_name, fronting, last_update) VALUES($1, $2, $3, $4, $5)",
             pk_sid, pk_mid, member_name, fronting, update_ts)



@db_deco
async def delete_member(pool: asyncpg.pool.Pool, pk_sid: str, pk_mid: str):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection

        await conn.execute(
            "DELETE FROM members WHERE pk_sid = $1 AND pk_mid = $2",
             pk_sid, pk_mid)


@db_deco
async def update_member(pool: asyncpg.pool.Pool, pk_sid: str, pk_mid: str, member_name: str, fronting: bool):
    pk_mid = pk_mid.lower()  # Just to be sure...
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        # Convert ts to int
        update_ts: datetime = datetime.utcnow().timestamp()

        await conn.execute("""
                            INSERT INTO members(pk_sid, pk_mid, member_name, fronting, last_update) VALUES($1, $2, $3, $4, $5)
                            ON CONFLICT (pk_mid)
                            DO UPDATE 
                            SET pk_sid = EXCLUDED.pk_sid, pk_mid = EXCLUDED.pk_mid, member_name = EXCLUDED.member_name, fronting = EXCLUDED.fronting, last_update = EXCLUDED.last_update
                            """, pk_sid, pk_mid, member_name, fronting, update_ts)

        # TODO: Stop doing this
        await conn.execute(
            """UPDATE systems
               SET last_update = $1
               WHERE pk_sid = $2""", update_ts, pk_sid)


@db_deco
async def fake_member_update(pool: asyncpg.pool.Pool, pk_mid: str):
    """This just updates the last_update time to 24 hours in the future as a temporary work around for PK Privacy issues."""
    pk_mid = pk_mid.lower()  # Just to be sure...
    async with pool.acquire() as conn:
        # conn: asyncpg.connection.Connection
        # Convert ts to int
        update_ts: datetime = datetime.utcnow().timestamp() + 60*60*24
        await conn.execute(
            """UPDATE members
               SET last_update = $1
               WHERE pk_mid = $2""", update_ts, pk_mid)


# --- Get Member(s) --- #


class DBMember(NamedTuple):
    pk_mid: str
    pk_sid: str
    member_name: str
    fronting: bool
    last_update: int


members_map = ["pk_sid", "pk_mid", "member_name", "fronting", "last_update"]
@db_deco
async def get_members_by_pk_sid(pool: asyncpg.pool.Pool, pk_sid: str) -> List[Dict]:  # Not currently in use.
    """ Gets all the members belonging to a system by using the SystemID.
        While 'get_members_by_discord_account' is currently being used instead of this function,
            prehaps this function should get more use as it's lack of an INNER JOIN should make it more efficient."""
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
async def get_members_by_discord_account(pool: asyncpg.pool.Pool, discord_user_id: int) -> Optional[List[DBMember]]:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        """members_map = ["pk_sid", "pk_mid", "member_name", "fronting", "last_update"]"""
        raw_rows = await conn.fetch("""
                                    SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = $1""", discord_user_id)
        if len(raw_rows) > 0:
            return [DBMember(**row) for row in raw_rows] #raw_rows
        else:
            return None


@db_deco
async def get_members_by_discord_account_old(pool: asyncpg.pool.Pool, discord_user_id: int) -> Optional[List[asyncpg.Record]]:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        """members_map = ["pk_sid", "pk_mid", "member_name", "fronting", "last_update"]"""
        raw_rows = await conn.fetch("""
                                    SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = $1""", discord_user_id)
        if len(raw_rows) > 0:
            return raw_rows
        else:
            return None

# TODO: Test this function
# TODO: Rename to get_stale_members_by_discord_account()
@db_deco
async def get_members_by_discord_account_if_ood(pool: asyncpg.pool.Pool, discord_user_id: int, older_than: int = 86400)-> Optional[List[Dict]]:
    ood_members_map = ['pk_sid', 'pk_mid', 'member_name', 'fronting', 'last_update']
    async with pool.acquire() as conn:
        # dict_map = []
        expiration_age = datetime.utcnow().timestamp() - older_than
        # log.info(f"time: {time}")
        raw_rows = await conn.fetch("""
                                        SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update
                                        from members
                                        INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                        WHERE accounts.dis_uid = $1 and members.last_update < $2""", discord_user_id, expiration_age)
        if len(raw_rows) == 0:
            return None
        else:
            return raw_rows

@db_deco
async def get_fronting_members_by_pk_sid(pool: asyncpg.pool.Pool, pk_sid: str) -> Optional[List[pk.Member]]:  # Not currently in use.
    """ Gets all the members who are in front and belong to a system by using the SystemID.
        While 'get_fronting_members_by_discord_account' is currently being used instead of this function,
            prehaps this function should get more use as it's lack of an INNER JOIN should make it more efficient."""
    async with pool.acquire() as conn:
        cursor = await conn.execute("""SELECT members.pk_mid 
                                       from members where pk_sid = ? and fronting = 1
                                       """, (pk_sid, ))
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
async def get_fronting_members_by_discord_account(pool: asyncpg.pool.Pool, discord_user_id: int) -> Optional[List[pk.Member]]:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        raw_rows = await conn.fetch("""
                                    SELECT members.pk_mid, members.pk_sid
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = $1 and members.fronting = TRUE""",
                                    int(discord_user_id))
        # rows = [dict(zip(members_map, row)) for row in raw_rows]
        # TODO: Add member name
        rows = []
        for row in raw_rows:
            rows.append(pk.Member(id=row['pk_mid'], sid=row['pk_sid']))
        if len(rows) == 0:
            return None
        else:
            return rows


@db_deco
async def get_member_by_mid_and_discord_account(pool: asyncpg.pool.Pool, pk_mid: str, discord_user_id: int) -> Optional[asyncpg.Record]:
    """gets a row of 'members' by using the memberID and their discord account. Used by db.get_member_fuzzy()"""
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        # TODO: Use something other than LOWER() for case insensitive matching.
        raw_row = await conn.fetchrow("""
                                    SELECT members.pk_sid,  members.pk_mid, members.member_name, members.fronting, members.last_update
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = $1 and LOWER(members.pk_mid) = LOWER($2)
                                    """, discord_user_id, pk_mid)

        """members_map = ["pk_sid", "pk_mid", "member_name", "fronting", "last_update"]"""
        return raw_row


@db_deco
async def get_member_by_name_and_discord_account(pool: asyncpg.pool.Pool, member_name: str, discord_user_id: int) -> Optional[asyncpg.Record]:
    """gets a row of 'members' by using their name and their discord account. Used by db.get_member_fuzzy()"""
    # FIXME: This could return multiple members as member_name is not unique.
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        raw_row = await conn.fetchrow("""
                                    SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update
                                    from members
                                    INNER JOIN accounts on accounts.pk_sid = members.pk_sid
                                    WHERE accounts.dis_uid = $1 and LOWER(members.member_name) = LOWER($2)
                                    """, discord_user_id, member_name)
        """members_map = ["pk_sid", "pk_mid", "member_name", "fronting", "last_update"]"""
        return raw_row


async def get_member_fuzzy(pool: asyncpg.pool.Pool, discord_user_id: int, search_value: str) -> Optional[asyncpg.Record]:
    # First search by name then hid
    search_value = search_value.lower()
    member = await get_member_by_name_and_discord_account(pool, search_value, discord_user_id)
    if member is None:
        member = await get_member_by_mid_and_discord_account(pool, search_value, discord_user_id)

    return member



@db_deco
async def get_all_outofdate_members(pool: asyncpg.pool.Pool, older_than: int = 86400)-> Optional[List[Dict]]:  # Not currently in use
    """Returns every stale member in the db"""
    raise NotImplementedError
    # async with pool.acquire() as conn:
    #     time = datetime.utcnow().timestamp() - older_than
    #     log.info(f"time: {time}")
    #     cursor = await conn.execute("""SELECT members.pk_sid, members.pk_mid, members.member_name, members.fronting, members.last_update
    #                                    from members WHERE last_update < ?""", (time,))
    #     raw_rows = await cursor.fetchall()
    #     rows = [dict(zip(members_map, row)) for row in raw_rows]
    #
    #     if len(rows) == 0:
    #         return None
    #     else:
    #         return rows

# --- Member Roles --- #

@db_deco
async def add_role_to_member(pool: asyncpg.pool.Pool, guild_id: int, pk_mid: str, pk_sid: str, role_id: int) -> bool:
    async with pool.acquire() as conn:
            await conn.execute("""
                                INSERT INTO roles(pk_mid, pk_sid, role_id, guild_id) VALUES($1, $2, $3, $4)
                                ON CONFLICT (pk_mid, role_id)
                                DO NOTHING
                                """, pk_mid, pk_sid, role_id, guild_id)
            return True


@db_deco
async def remove_role_from_member(pool: asyncpg.pool.Pool, guild_id: int, pk_mid: str, role_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM roles WHERE pk_mid = $1 and role_id = $2 and guild_id = $3",
             pk_mid, role_id, guild_id)


# WHile the below function does not exist, if we could find a DBy way of doing that rater than iterating over every member and using a separate DB call, that would be GREAT!
# @db_deco
# async def add_role_to_system(pool: asyncpg.pool.Pool, guild_id: int, pk_mid: str, role_id: int):
#     async with pool.acquire() as conn:
#         await conn.execute(
#             "INSERT INTO roles(pk_mid, role_id, guild_id) VALUES(?, ?, ?)",
#             (pk_mid, role_id, guild_id))
#         await conn.commit()


role_map = ["pk_mid", "pk_sid", "role_id", "guild_id"]
@db_deco
async def get_roles_for_member_by_guild(pool: asyncpg.pool.Pool, pk_mid: str, guild_id: int) -> Optional[List[asyncpg.Record]]:
    #FIXME: Possible breaking change. pk_mid is no longer case insensitive.
    pk_mid = pk_mid.lower()
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch(" SELECT * from roles where pk_mid = $1 AND guild_id = $2", pk_mid, guild_id)
        """role_map = ["pk_mid", "pk_sid", "role_id", "guild_id"]"""
        if len(raw_rows) == 0:
            return None
        return raw_rows


@db_deco
async def get_roles_for_member(pool: asyncpg.pool.Pool, pk_mid: str) -> Optional[List[Dict]]:  # Not currently in use.
    """gets all the role IDs for a member, regardless of the guild they are in. Could be useful when we implement Cross guild ARCing"""
    async with pool.acquire() as conn:
        pk_mid = pk_mid.lower()
        raw_rows = await conn.fetch(" SELECT * from roles where pk_mid = $1", pk_mid)
        if len(raw_rows) == 0:
            return None
        return raw_rows

# --- Settings --- #


# --- Guild Allowable Roles --- #

class AllowableRoles:
    role_ids: List[int]
    guild_id: int
    # roles: Optional[List[discord.Role]]
    row_map = ['role_id', 'guild_id']

    def __init__(self, guild_id: int, role_ids: List[int]): #rows: Iterable[aiosqlite.Row]):

        self.guild_id: int = guild_id  # Guild ID will be the same for every role, so just set it from the first
        self.role_ids = role_ids

    @classmethod
    def from_list_of_dict(cls, rows: Iterable[aiosqlite.Row]):

        obj = cls(rows[0][1], [row[0] for row in rows])
        return obj


    # self.guild_id: int = rows[0][1]  # Guild ID will be the same for every role, so just set it from the first
    # self.role_ids = [row[0] for row in rows]

    def is_allowed(self, other_role: discord.Role):
        for allowed_role_id in self.role_ids:
            if allowed_role_id == other_role.id:
                return True

        return False

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


@db_deco
async def add_allowable_role(pool: asyncpg.pool.Pool, guild_id: int, role_id: int):
    async with pool.acquire() as conn:
        # await conn.execute("""
        #                     INSERT INTO allowable_roles(role_id, guild_id) VALUES($1, $2)
        #                     ON CONFLICT (role_id, guild_id)
        #                     DO NOTHING
        #                     """, role_id, guild_id)

        await conn.execute("""
                            INSERT INTO allowable_roles(role_id, guild_id) VALUES($1, $2)
                            """, role_id, guild_id)

        # await conn.execute(
        #     "INSERT or ignore INTO allowable_roles(role_id, guild_id) VALUES(?, ?)",
        #     (role_id, guild_id))
        # await conn.commit()


@db_deco
async def get_allowable_roles(pool: asyncpg.pool.Pool, guild_id: int) -> AllowableRoles:
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch(" SELECT * from allowable_roles where guild_id = $1", guild_id)

        if len(raw_rows) == 0:
            return AllowableRoles(guild_id=guild_id, role_ids=[])
        allowable_roles = AllowableRoles.from_list_of_dict(raw_rows)
        return allowable_roles


@db_deco
async def remove_allowable_role(pool: asyncpg.pool.Pool, guild_id: int, role_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM allowable_roles WHERE guild_id = $1 and role_id = $2",
             guild_id, role_id)


# --- User Settings --- #

class UserSettings:
    pk_sid: str
    guild_id: int
    name_change: bool
    role_change: bool
    system_role: Optional[int]
    system_role_enabled: Optional[bool]

    row_map = ['pk_sid', 'guild_id', 'name_change', 'role_change', 'system_tag_override']

    # TODO, add option to create default settign object. Till then, don't forget to update the default settings in the following places:
    #  AutoRole:UserSettingsRolesMenuHandler
    def __init__(self, row: Union[aiosqlite.Row, Dict]):
        self.pk_sid: str = row['pk_sid']
        self.guild_id: int = row['guild_id']
        self.name_change: bool = bool(row['name_change'])
        self.role_change: bool = bool(row['role_change'])
        self.system_role: Optional[int] = row['system_role']
        self.system_role_enabled: Optional[bool] = row['system_role_enabled']
        # self.system_tag_override: Optional[str] = row['system_tag_override]



# We don't really NEED add_user_settings if we just use update_user_setting instead.
# @db_deco
# async def add_user_setting(pool: asyncpg.pool.Pool, pk_sid: str, guild_id: int, name_change: bool, role_change: bool):
#     async with pool.acquire() as conn:
#         await conn.execute(
#             "INSERT INTO user_settings(pk_sid, guild_id, name_change, role_change) VALUES(?, ?, ?, ?)",
#             (pk_sid, guild_id, name_change, role_change))
#         await conn.commit()
#


@db_deco
async def update_user_setting(pool: asyncpg.pool.Pool, pk_sid: str, guild_id: int, name_change: bool, role_change: bool):
    async with pool.acquire() as conn:
        await conn.execute("""
                            INSERT INTO user_settings(pk_sid, guild_id, name_change, role_change) VALUES($1, $2, $3, $4)
                            ON CONFLICT (pk_sid, guild_id)
                            DO UPDATE 
                            SET name_change = EXCLUDED.name_change, role_change = EXCLUDED.role_change
                            """, pk_sid, guild_id, name_change, role_change)


@db_deco
async def update_system_role(pool: asyncpg.pool.Pool, pk_sid: str, guild_id: int, system_role: Optional[int], enabled: bool):
    """Updates the system role ID and the Enabled flag for a users settings on a guild."""
    async with pool.acquire() as conn:
        await conn.execute("""
                              UPDATE user_settings
                              SET system_role = $1, system_role_enabled = $2
                              WHERE pk_sid = $3 AND guild_id = $4
                            """, system_role, enabled, pk_sid, guild_id)

#
# @db_deco
# async def get_user_settings_for_guildby_pksid(pool: asyncpg.pool.Pool, pk_sid: str, guild_id: int) -> Optional[UserSettings]:  # Not currently in use.
#     """ Gets the user settings for a system by using thier systemID and guildID.
#         While 'get_user_settings_from_discord_id' is currently being used instead of this function,
#             prehaps this function should get more use as it's lack of an INNER JOIN should make it more efficient."""
#     async with pool.acquire() as conn:
#         cursor = await conn.execute(" SELECT * from user_settings where pk_sid = ? AND guild_id = ? COLLATE NOCASE", (pk_sid, guild_id))
#         raw_row = await cursor.fetchone()
#         if raw_row is None:
#             return None
#         user_settings = UserSettings(raw_row)
#         return user_settings


@db_deco
async def get_user_settings_from_discord_id(pool: asyncpg.pool.Pool, discord_user_id: int, guild_id: int) -> Optional[UserSettings]:
    async with pool.acquire() as conn:
        # cursor = await conn.execute(" SELECT * from user_settings where pk_sid = ? AND guild_id = ? COLLATE NOCASE", (pk_sid, guild_id))
        row = await conn.fetchrow("""
                                    SELECT *
                                    from user_settings
                                    INNER JOIN accounts on accounts.pk_sid = user_settings.pk_sid
                                    WHERE accounts.dis_uid = $1 AND user_settings.guild_id = $2
                                    """, discord_user_id, guild_id)
        if row is None:
            return None
        user_settings = UserSettings(row)
        return user_settings

# TODO: Test this function
@db_deco
async def get_all_user_settings_from_discord_id(pool: asyncpg.pool.Pool, discord_user_id: int) -> Optional[List[UserSettings]]:
    """Not currently in use, will be useful for cros guild ARCing"""
    async with pool.acquire() as conn:
        # cursor = await conn.execute(" SELECT * from user_settings where pk_sid = ? COLLATE NOCASE", (pk_sid, ))
        raw_rows = await conn.fetch("""
                                    SELECT *
                                    from user_settings
                                    INNER JOIN accounts on accounts.pk_sid = user_settings.pk_sid
                                    WHERE accounts.dis_uid = $1
                                    """, discord_user_id)

        if len(raw_rows) == 0:
            return None

        all_user_settings = [UserSettings(row) for row in raw_rows]
        return all_user_settings

@db_deco
async def DEBUG_get_every_user_settings(pool: asyncpg.pool.Pool) -> Optional[List[UserSettings]]:
    """Not currently in use, will be useful for cros guild ARCing"""
    async with pool.acquire() as conn:
        # cursor = await conn.execute(" SELECT * from user_settings where pk_sid = ? COLLATE NOCASE", (pk_sid, ))
        raw_rows = await conn.fetch("""
                                    SELECT *
                                    from user_settings
                                    """)
        if len(raw_rows) == 0:
            return None

        all_user_settings = [UserSettings(row) for row in raw_rows]
        return all_user_settings


# @db_deco
# async def remove_user_settings(pool: asyncpg.pool.Pool, pk_sid: str, guild_id: int):  # Not currently in use.
#     raise NotImplementedError


# --- Guild settings --- #


@db_deco
async def add_guild_setting(pool: asyncpg.pool.Pool, guild_id: int, name_change: bool, role_change: bool, log_channel: Optional[int], name_logging: bool, role_logging: bool):
    async with pool.acquire() as conn:
        await conn.execute("""
                            INSERT INTO guilds(guild_id, name_change, role_change, log_channel, name_logging, role_logging) VALUES($1, $2, $3, $4, $5, $6)
                            """, guild_id, name_change, role_change, log_channel, name_logging, role_logging)


@db_deco
async def update_all_guild_setting(pool: asyncpg.pool.Pool, guild_id: int, name_change: bool, role_change: bool, log_channel: Optional[int], name_logging: bool, role_logging: bool):
    async with pool.acquire() as conn:
        await conn.execute("""
                            INSERT INTO guilds(guild_id, name_change, role_change, log_channel, name_logging, role_logging) VALUES($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (guild_id)
                            DO UPDATE 
                            SET name_change = EXCLUDED.name_change, role_change = EXCLUDED.role_change, log_channel = EXCLUDED.log_channel, name_logging = EXCLUDED.name_logging, role_logging = EXCLUDED.role_logging
                            """, guild_id, name_change, role_change, log_channel, name_logging, role_logging)


@db_deco
async def update_custom_role_guild_setting(pool: asyncpg.pool.Pool, guild_id: int, custom_role_setting: bool):
    async with pool.acquire() as conn:
        await conn.execute("""
                            UPDATE guilds
                            SET custom_roles = $1
                            WHERE guild_id = $2
                            """, custom_role_setting, guild_id)


@db_deco
async def remove_guild_setting(pool: asyncpg.pool.Pool, guild_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
                            DELETE FROM guilds where guild_id = $1
                            """, guild_id)


@db_deco
async def get_guild_settings(pool: asyncpg.pool.Pool, guild_id: int):# -> Optional[DBGuildSettings]:
    """Gets the guild_settings for a guild by the guildID."""
    async with pool.acquire() as conn:
        raw_row = await conn.fetchrow(" SELECT * from guilds where guild_id = $1", guild_id)
        if raw_row is None:
            return None

        return raw_row




# ---------- Table Migration ---------- #
# Defined down here so it's on our mind when doing migration code
TARGET_DB_VERSION = 0

@db_deco
async def migrate_to_latest(pool: asyncpg.pool.Pool):

    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        # check if db_info table has any rows yet if not, we are at version zero and we need to set that..
        db_info_initialized = (await conn.fetchval("SELECT COUNT(*) FROM db_info") == 1)
        if not db_info_initialized:
            # Start the DB Version at 0.
            await conn.execute("insert into db_info (schema_version) values (0);")

        current_db_version = await conn.fetchval("SELECT schema_version FROM db_info")
        if current_db_version >= TARGET_DB_VERSION:
            # The DB is all up to date!!! Nothing left to do, so return
            return True

        # Rest of migration code will get implemented when we have a migration to do.
        raise NotImplementedError

# ---------- Table Creation ---------- #
@db_deco
async def create_tables(pool: asyncpg.pool.Pool):
    async with pool.acquire() as conn:
        await conn.execute('''
                               CREATE TABLE if not exists systems (
                               pk_sid               TEXT PRIMARY KEY,
                               system_name          TEXT default 'None',
                               pk_token             TEXT DEFAULT NULL,
                               current_fronter      TEXT DEFAULT NULL,
                               pk_system_tag        TEXT DEFAULT NULL,
                               last_update          bigint  --TIMESTAMPTZ NOT NULL DEFAULT NOW()
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists members  (
                               pk_mid               TEXT PRIMARY KEY,
                               pk_sid               TEXT NOT NULL REFERENCES systems(pk_sid) ON DELETE CASCADE,
                               member_name          TEXT default 'unknown',
                               fronting             boolean DEFAULT false,
                               last_update          bigint  --TIMESTAMPTZ NOT NULL DEFAULT NOW()
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists accounts  (
                               dis_uid              BIGINT PRIMARY KEY,
                               pk_sid               TEXT NOT NULL REFERENCES systems(pk_sid) ON DELETE CASCADE
                              );
                        ''')

        await conn.execute('''
                           CREATE TABLE if not exists guilds  (
                           guild_id             bigint PRIMARY KEY ,
                           name_change          boolean default TRUE,
                           role_change          boolean default TRUE,
                           log_channel          bigint default null,
                           name_logging         boolean default TRUE,
                           role_logging         boolean default TRUE,
                           custom_roles         boolean default FALSE
                        );
                    ''')

        await conn.execute('''
                               CREATE TABLE if not exists roles (             
                               pk_mid               TEXT NOT NULL REFERENCES members(pk_mid) ON DELETE CASCADE,
                               pk_sid               TEXT NOT NULL REFERENCES systems(pk_sid) ON DELETE CASCADE,
                               role_id              bigint not null,
                               guild_id             bigint not null NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE, 
                               PRIMARY KEY (pk_mid, role_id)
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists allowable_roles  (
                               role_id              bigint NOT NULL,
                               guild_id             bigint not null REFERENCES guilds(guild_id) ON DELETE CASCADE,
                               PRIMARY KEY (role_id, guild_id)
                            );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists user_settings  (
                               pk_sid               TEXT NOT NULL REFERENCES systems(pk_sid) ON DELETE CASCADE,
                               guild_id             bigint not null NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
                               name_change          boolean default FALSE,
                               role_change          boolean default TRUE,
                               system_role          bigint default NULL,
                               system_role_enabled  boolean default false, 
                               PRIMARY KEY (pk_sid, guild_id)
                            );
                        ''')

        await conn.execute('''
                                CREATE TABLE if not exists db_info(
                                id                  int primary key not null default 1, -- enforced only equal to 1
                                schema_version      int,
                                CONSTRAINT singleton CHECK(id=1)  -- enforce singleton table/row
                                );
                        ''')


