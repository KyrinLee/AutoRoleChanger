"""

"""

import asyncio
import logging
from typing import Optional
import traceback
import sys

import discord
from discord.ext import commands


log = logging.getLogger(__name__)


class Dev(commands.Cog):
    def __init__(self, bot):

        self.bot: commands.Bot = bot
        self.pool = bot.pool

    @commands.command(hidden=True)
    async def load(self, ctx, *, module):
        """Loads a module."""
        try:
            self.bot.load_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        try:
            self.bot.unload_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.group(name='reload', hidden=True, invoke_without_command=True)
    async def _reload(self, ctx, *, module):
        """Reloads a module."""
        try:
            self.bot.reload_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')


    @_reload.command(name='all', hidden=True)
    async def _reload_all(self, ctx):

        for extension in self.bot.extensions:
            try:
                self.bot.reload_extension(extension)
                log.info(f"Loaded {extension}")
            except Exception as e:
                print(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()


def setup(bot):
    bot.add_cog(Dev(bot))
