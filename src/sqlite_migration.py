"""
Migrate from sqlite to postgres
"""
import postgresDB as pdb
import db
import logging
import asyncio
import asyncpg
import json

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

log = logging.getLogger(__name__)


async def migrate_from_sqlite(sqlite_db: str, pool):

    # Move guilds, then Systems, then members, accounts, roles, allowable_roles, user_settings

    # Since the guild table did not exist in the SQLite DB, and since there are many table which are now dependent on them,
    #   Manually create all the Guild Settings Records.
    await pdb.update_all_guild_setting(pool, 433446063022538753, name_change=True, role_change=True, log_channel=None, name_logging=False, role_logging=False)  # PN
    await pdb.update_all_guild_setting(pool, 624361300327268363, True, True, None, False, False)  # BD
    await pdb.update_all_guild_setting(pool, 575424652776833035, True, True, None, False, False)  #
    await pdb.update_all_guild_setting(pool, 603734300831121419, True, True, None, False, False)  #
    await pdb.update_all_guild_setting(pool, 608370324685193252, True, True, None, False, False)  #

    all_systems = await db.get_all_systems_from_sqlite(sqlite_db)
    for system in all_systems:
        await pdb.add_new_system(pool, pk_sid=system['pk_sid'], system_name=system['system_name'], current_fronter=system['current_fronter'], pk_system_tag=system['pk_system_tag'])

    all_members = await db.get_all_members_from_sqlite(sqlite_db)
    for member in all_members:
        await pdb.add_new_member(pool, pk_sid=member['pk_sid'], pk_mid=member['pk_mid'], member_name=member['member_name'], fronting=bool(member['fronting']))

    all_accounts = await db.get_all_accounts_from_sqlite(sqlite_db)
    for account in all_accounts:
        await pdb.add_linked_discord_account(pool, pk_sid=account['pk_sid'], dis_uid=account['dis_uid'])

    all_roles = await db.get_all_roles_from_sqlite(sqlite_db)
    for role in all_roles:
        await pdb.add_role_to_member(pool, guild_id=role['guild_id'], pk_mid=role['pk_mid'], pk_sid=role['pk_sid'], role_id=role['role_id'])

    all_alow_roles = await db.get_all_allowable_roles_from_sqlite(sqlite_db)
    for al_role in all_alow_roles:
        await pdb.add_allowable_role(pool, guild_id=al_role['guild_id'], role_id=al_role['role_id'])

    all_user_settings = await db.get_all_user_settings_from_sqlite(sqlite_db)
    for sett in all_user_settings:
        await pdb.update_user_setting(pool, pk_sid=sett['pk_sid'], guild_id=sett['guild_id'], name_change=bool(sett['name_change']), role_change=bool(sett['role_change']))

    log.info("SQLite DB has been migrated to Postgres!")


if __name__ == '__main__':

    with open('config.json') as json_data_file:
        config = json.load(json_data_file)

    db_pool: asyncpg.pool.Pool = asyncio.get_event_loop().run_until_complete(pdb.create_db_pool(config['arc_prod_db_uri']))
    litedb = config['db_address']

    asyncio.get_event_loop().run_until_complete(db.create_tables(litedb))
    asyncio.get_event_loop().run_until_complete(db.migrate_to_latest(litedb))

    asyncio.get_event_loop().run_until_complete(pdb.create_tables(db_pool))
    asyncio.get_event_loop().run_until_complete(pdb.migrate_to_latest(db_pool))

    asyncio.get_event_loop().run_until_complete(migrate_from_sqlite(litedb, db_pool))

    log.warning("DONE!!! with SQLITE migrations")

