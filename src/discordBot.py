"""
"""
import traceback
import sys
import logging
import asyncio

from typing import Optional, Dict

import discord
from discord.ext import commands
from cogs.utils.dLogger import dLogger
import embeds
from botExceptions import UnsupportedGuild

log = logging.getLogger("PNBot")

extensions = (
    'cogs.AutoRole',
    # 'cogs.AutoRoleHelp',
    # 'cogs.Dev',
)


class PNBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db: Optional[str] = None
        self.error_log_channel_id: Optional[int] = None
        self.warning_log_channel_id: Optional[int] = None
        self.info_log_channel_id: Optional[int] = None

        self.dLog = dLogger(self)
        self.remove_command("help")  # Remove the built in help command so we can make the about section look nicer.

    def load_cogs(self):
        for extension in extensions:
            try:
                self.load_extension(extension)
                log.info(f"Loaded {extension}")
            except Exception as e:
                log.info(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()

    async def on_ready(self):

        self.add_cog(Utilities(self))
        log.info('Connected using discord.py {}!'.format(discord.__version__))
        log.info('Username: {0.name}, ID: {0.id}'.format(self.user))
        log.info("Connected to {} servers.".format(len(self.guilds)))

        activity = discord.Game("{}help".format(self.command_prefix))
        await self.change_presence(status=discord.Status.online, activity=activity)
        await self.dLog.initialize_logger(self.error_log_channel_id, self.warning_log_channel_id, self.info_log_channel_id)

    # ---- Command Error Handling ----- #
    # @client.event
    async def on_command_error(self, ctx, error):
        if type(error) == discord.ext.commands.NoPrivateMessage:
            await ctx.send("⚠ This command can not be used in DMs!!!")
            return
        elif type(error) == discord.ext.commands.CommandNotFound:
            await ctx.send("⚠ Invalid Command!!!")
            return
        elif type(error) == discord.ext.commands.MissingPermissions:
            await ctx.send(
                "⚠ You need the **Manage Messages** permission to use this command".format(error.missing_perms))
            return
        elif type(error) == discord.ext.commands.MissingRequiredArgument:
            await ctx.send("⚠ {}".format(error))
        elif type(error) == discord.ext.commands.BadArgument:
            await ctx.send("⚠ {}".format(error))
        elif type(error) == UnsupportedGuild:
            await ctx.send("⚠ This command is not yet supported outside of Plural Nest.")
            return
        else:
            await ctx.send("⚠ {}".format(error))
            await self.dLog.error(error)
            raise error

    # @client.event
    async def on_error(self, event_name, *args):
        logging.exception("Exception from event {}".format(event_name))
        #
        # embed = None
        # # Determine if we can get more info, otherwise post without embed
        # if args and type(args[0]) == discord.Message:
        #     message: discord.Message = args[0]
        #     embeds.exception_w_message(message)
        # elif args and type(args[0]) == discord.RawMessageUpdateEvent:
        #     logging.error("After Content:{}.".format(args[0].data['content']))
        #     if args[0].cached_message is not None:
        #         logging.error("Before Content:{}.".format(args[0].cached_message.content))
        # # Todo: Add more
        #
        # traceback_message = "```python\n{}```".format(traceback.format_exc())
        # traceback_message = (traceback_message[:1993] + ' ...```') if len(
        #     traceback_message) > 2000 else traceback_message

        # await error_log_channel.send(content=traceback_message, embed=embed)
        traceback_msg1 = f"Exception! {event_name}: {args}"
        traceback_msg2 = f"{traceback.format_exc()}"
        await self.dLog.error(traceback_msg1)
        await asyncio.sleep(0.5)
        await self.dLog.error(traceback_msg2)

    async def on_guild_join(self, guild: discord.Guild):
        log_msg = "Auto Role Changer joined **{} ({})**, owned by:** {} - {}#{} ({})**".format(guild.name, guild.id, guild.owner.display_name, guild.owner.name, guild.owner.discriminator, guild.owner.id)
        log.warning(log_msg)
        await self.dLog.warning(log_msg, header=f"[{__name__}]")


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="invite",
                      brief="Get an invite link.")
    async def invite(self, ctx: commands.Context):
        perm = discord.Permissions()
        perm.manage_roles = True
        perm.manage_nicknames = True
        perm.read_messages = True
        perm.send_messages = True
        perm.add_reactions = True
        perm.embed_links = True

        link = discord.utils.oauth_url(self.bot.user.id, permissions=perm)
        await ctx.send(link)

        log_msg = f"Invite for Auto Role Changer sent to ** {ctx.author.display_name} - {ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})**"
        log.warning(log_msg)
        await self.bot.dLog.warning(log_msg, header=f"[{__name__}]")

    @commands.is_owner()
    @commands.command(name="list_guilds", hidden=True)
    async def list_guilds(self, ctx: commands.Context):
        ZERO_WIDTH_CHAR = " ‌‌‌ "
        msg_list = []
        for guild in self.bot.guilds:
            log_msg = "Auto Role Changer in Guild **{} ({})**, owned by:** {} - {}#{} ({})**\n".format(guild.name, guild.id,
                                                                                                   guild.owner.display_name,
                                                                                                   guild.owner.name,
                                                                                                   guild.owner.discriminator,
                                                                                                   guild.owner.id)
            msg_list.append(log_msg)
        messages = f"\n{ZERO_WIDTH_CHAR}".join(msg_list)

        await dLogger.send_long_msg(ctx.channel, messages)


