"""
"""
import traceback
import sys
import logging

from typing import Optional, Dict

import discord
from discord.ext import commands

log = logging.getLogger("PNBot")

extensions = (
    'cogs.AutoRole',
    'cogs.Dev',
)


class PNBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db: Optional[str] = None

        # self.open_interviews: Optional[Interviews] = None


    def load_cogs(self):
        for extension in extensions:
            try:
                self.load_extension(extension)
                log.info(f"Loaded {extension}")
            except Exception as e:
                print(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()


    async def on_ready(self):
        log.info('Connected using discord.py {}!'.format(discord.__version__))
        log.info('Username: {0.name}, ID: {0.id}'.format(self.user))
        log.info("Connected to {} servers.".format(len(self.guilds)))

        activity = discord.Game("{}help".format(self.command_prefix))
        await self.change_presence(status=discord.Status.online, activity=activity)
