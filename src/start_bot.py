import json
import asyncio
import logging
import logging.config

import loggly.handlers

import asyncpg

from discordBot import PNBot
from cogs.utils.dLogger import dLogger

import db
import postgresDB as pdb


logging.config.fileConfig('logging.conf', disable_existing_loggers=False)
# logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

if __name__ == '__main__':

    with open('config.json') as json_data_file:
        config = json.load(json_data_file)

    bot = PNBot(command_prefix="lb!",
                max_messages=5000,
                # description="",
                owner_id=389590659335716867,
                case_insensitive=True)

    db_pool: asyncpg.pool.Pool = asyncio.get_event_loop().run_until_complete(pdb.create_db_pool(config['arc_prod_db_uri']))
    bot.pool = db_pool

    bot.command_prefix = config['bot_prefix']
    # bot.command_prefix = config['luna_bot_prefix']
    bot.error_log_channel_id = config['error_log_channel']
    bot.warning_log_channel_id = config['warning_log_channel']
    bot.info_log_channel_id = config['info_log_channel']

    asyncio.get_event_loop().run_until_complete(pdb.create_tables(bot.pool))
    asyncio.get_event_loop().run_until_complete(pdb.migrate_to_latest(bot.pool))

    bot.load_cogs()
    bot.run(config['arc_token'])
    # bot.run(config['luna_token'])

    log.warning("DONE!!! with Arc Bot")

