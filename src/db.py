import aiosqlite
import logging
import time
import functools

from datetime import datetime
from typing import Optional, List, Dict

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
        # Convert ts to str
        update_ts: datetime = datetime.utcnow()
        update_ts = update_ts.isoformat()
        await conn.execute(
            "INSERT INTO systems(pk_sid, system_name, last_update) VALUES(?, ?, ?)",
            (pk_sid, system_name, update_ts))
        await conn.commit()


@db_deco
async def add_new_member(db: str, pk_sid: str, pk_mid: str, member_name: str, fronting: bool):
    async with aiosqlite.connect(db) as conn:
        # Convert ts to str
        update_ts: datetime = datetime.utcnow()
        update_ts = update_ts.isoformat()
        await conn.execute(
            "INSERT INTO members(pk_sid, pk_mid, member_name, fronting, last_update) VALUES(?, ?, ?, ?, ?)",
            (pk_sid, pk_mid, member_name, fronting, update_ts))
        await conn.commit()


@db_deco
async def add_linked_discord_account(db: str, pk_sid: str, dis_uid: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "INSERT INTO accounts(dis_uid, pk_sid) VALUES(?, ?)",
            (dis_uid, pk_sid))
        await conn.commit()


@db_deco
async def get_system_from_linked_account(db: str, dis_uid: int):
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from accounts WHERE dis_uid = ?", (dis_uid,))
        row = await cursor.fetchone()
        # interview_dict = dict(zip(interview_row_map, row))
        # return row_to_interview_dict(row)
        if row is not None:
            row = {
                'discord_account': row[0],
                'pk_system_id': row[1]
            }
        return row


members_map = ["id", "pk_sid", "pk_mid", "member_name", "fronting", "last_update"]
@db_deco
async def get_members_by_pk_sid(db: str, pk_sid: str):
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from members where pk_sid = ?", (pk_sid, ))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(members_map, row)) for row in raw_rows]
        # rows = []
        # for row in raw_rows:
        #     rows.append(row_to_interview_dict(row))
        return rows


# --- Roles --- #
@db_deco
async def add_role_to_member(db: str, guild_id: int, pk_mid: str, role_id: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "INSERT INTO roles(pk_mid, role_id, guild_id) VALUES(?, ?, ?)",
            (pk_mid, role_id, guild_id))
        await conn.commit()


@db_deco
async def remove_role_from_member(db: str, guild_id: int, pk_mid: str, role_id: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "DELETE FROM roles WHERE pk_mid = ? and role_id = ? and guild_id = ?",
            (pk_mid, role_id, guild_id))
        await conn.commit()


role_map = ["id", "pk_mid", "role_id", "guild_id"]
@db_deco
async def get_roles_for_member(db: str, pk_mid: str, guild_id: int):
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from roles where pk_mid = ? AND guild_id = ?", (pk_mid, guild_id))
        raw_rows = await cursor.fetchall()
        rows = [dict(zip(role_map, row)) for row in raw_rows]
        return rows

# --- Updates --- #
@db_deco
async def update_interview_all_mutable(db: str, cid: int, mid: int, question_number: int, interview_finished: bool, paused: bool, interview_type: str, read_rules: bool):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "UPDATE interviews SET question_number = ?, interview_finished = ?, paused = ?, interview_type = ?, read_rules = ? WHERE channel_id = ? AND member_id = ?",
            (question_number, interview_finished, paused, interview_type, read_rules, cid, mid))
        await conn.commit()


@db_deco
async def update_interview_question_number(db: str, cid: int, mid: int, question_number: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "UPDATE interviews SET question_number = ? WHERE channel_id = ? AND member_id = ?",
            (question_number, cid, mid))
        await conn.commit()


@db_deco
async def update_interview_finished(db: str, cid: int, mid: int, interview_finished: bool):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "UPDATE interviews SET interview_finished = ? WHERE channel_id = ? AND member_id = ?",
            (interview_finished, cid, mid))
        await conn.commit()


@db_deco
async def update_interview_paused(db: str, cid: int, mid: int, paused: bool):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "UPDATE interviews SET paused = ? WHERE channel_id = ? AND member_id = ?",
            (paused, cid, mid))
        await conn.commit()


@db_deco
async def update_interview_type(db: str, cid: int, mid: int, interview_type: str):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "UPDATE interviews SET interview_type = ? WHERE channel_id = ? AND member_id = ?",
            (interview_type, cid, mid))
        await conn.commit()


@db_deco
async def update_interview_read_rules(db: str, cid: int, mid: int, read_rules: bool):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "UPDATE interviews SET read_rules = ? WHERE channel_id = ? AND member_id = ?",
            (read_rules, cid, mid))
        await conn.commit()


# --- Selects --- #
interview_row_map = ('guild_id', 'member_id', 'user_name', 'channel_id', 'question_number', 'interview_finished',
                     'paused', 'interview_type', 'read_rules', 'join_ts')


def row_to_interview_dict(row: aiosqlite.Row) -> Dict:
    interview_dict = {
        interview_row_map[0]: row[0],   # Guild ID
        interview_row_map[1]: row[1],   # Member_id
        interview_row_map[2]: row[2],   # user_name
        interview_row_map[3]: row[3],   # channel_id
        interview_row_map[4]: row[4],   # quest_num
        interview_row_map[5]: bool(row[5]),   # int_fin
        interview_row_map[6]: bool(row[6]),   # Paused
        interview_row_map[7]: row[7],   # interview_type
        interview_row_map[8]: bool(row[8]),   # read_rules
        interview_row_map[9]: datetime.fromisoformat(row[9])  # join_ts
    }
    return interview_dict


# @db_deco
# async def get_interview_by_member(db: str, member_id: int):
#     async with aiosqlite.connect(db) as conn:
#         cursor = await conn.execute(" SELECT * from interviews WHERE member_id = ?", (member_id,))
#         row = await cursor.fetchone()
#         # interview_dict = dict(zip(interview_row_map, row))
#
#         return row_to_interview_dict(row)
#
#
# @db_deco
# async def get_all_interview_for_guild(db: str, sid: int):
#     async with aiosqlite.connect(db) as conn:
#         cursor = await conn.execute(" SELECT * from interviews WHERE guild_id = ?", (sid,))
#         raw_rows = await cursor.fetchall()
#         # rows = [dict(zip(interview_row_map, row)) for row in raw_rows]
#         rows = []
#         for row in raw_rows:
#             rows.append(row_to_interview_dict(row))
#         return rows


@db_deco
async def get_all_interviews(db: str):
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(" SELECT * from interviews")
        raw_rows = await cursor.fetchall()
        # rows = [dict(zip(interview_row_map, row)) for row in raw_rows]
        rows = []
        for row in raw_rows:
            rows.append(row_to_interview_dict(row))
        return rows


# --- Deletes --- #
@db_deco
async def delete_interview(db: str, cid: int, mid: int):
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "DELETE FROM interviews WHERE channel_id = ? AND member_id = ?",
            (cid, mid))
        await conn.commit()


# ---------- Table Creation ---------- #
@db_deco
async def create_tables(db: str):
    async with aiosqlite.connect(db) as conn:
        await conn.execute("PRAGMA foreign_keys = 0")
        # TODO: Move interview_type over to an int and use an enum?
        await conn.execute('''
                               CREATE TABLE if not exists systems (
                               id                   SERIAL PRIMARY KEY,
                               pk_sid               TEXT UNIQUE NOT NULL,
                               system_name          TEXT default 'unknown',
                               pk_token             TEXT DEFAULT NULL,
                               current_fronter      TEXT DEFAULT NULL,
                               last_update          TEXT
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists members  (
                               id                   SERIAL PRIMARY KEY,
                               pk_sid               TEXT NOT NULL,
                               pk_mid               TEXT UNIQUE NOT NULL,
                               member_name          TEXT default 'unknown',
                               fronting             boolean DEFAULT false,
                               last_update          TEXT,
                               
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
                               id                   SERIAL PRIMARY KEY,             
                               pk_mid               TEXT NOT NULL,
                               role_id              bigint not null,
                               guild_id             bigint not null, 

                               CONSTRAINT fk_role_member
                                    FOREIGN KEY (pk_mid)
                                    REFERENCES members(pk_mid)
                                    ON DELETE CASCADE
                              );
                        ''')

        await conn.execute("PRAGMA foreign_keys = 1")

        # await conn.execute('''
        #                        CREATE TABLE if not exists rule_confirmations (
        #                        member_id        BIGINT NOT NULL,
        #                        guild_id         BIGINT NOT NULL,
        #                        question_number  INT,
        #                        paused           BOOLEAN,
        #                        interview_type   TEXT,
        #                        user_name        TEXT NOT NULL,
        #                        content          TEXT DEFAULT NULL
        #                    );
        #                     ''')
