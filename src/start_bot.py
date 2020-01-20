import json
import asyncio
import logging

from discordBot import PNBot

import db

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")


if __name__ == '__main__':

    with open('config.json') as json_data_file:
        config = json.load(json_data_file)

    bot = PNBot(command_prefix="ib!",
                max_messages=5000,
                # description="",
                owner_id=389590659335716867,
                case_insensitive=True)

    bot.db = config['db_address']
    bot.command_prefix = "lb;"

    asyncio.get_event_loop().run_until_complete(db.create_tables(bot.db))

    bot.load_cogs()
    bot.run(config['luna_token'])

