"""

"""
import logging
import textwrap
import discord

from typing import TYPE_CHECKING, Optional, List, Union

if TYPE_CHECKING:
    from discordBot import PNBot


class dLogger:

    def __init__(self, bot: 'PNBot'):

        self.log = logging.getLogger(__name__)
        self.bot = bot

        self.error_log_cid = None
        self.warning_log_cid = None
        self.info_log_cid = None

        self.error_ch: Optional[discord.TextChannel] = None
        self.warning_ch: Optional[discord.TextChannel] = None
        self.info_ch: Optional[discord.TextChannel] = None


    async def initialize_logger(self, error_log_cid: int, warning_log_cid: int, info_log_cid: int):

        self.error_log_cid = error_log_cid
        self.warning_log_cid = warning_log_cid
        self.info_log_cid = info_log_cid

        # Wait for d.py to be ready.
        await self.bot.wait_until_ready()

        # Get and store log channels.

        self.error_ch = self.bot.get_channel(self.error_log_cid)
        self.warning_ch = self.bot.get_channel(self.warning_log_cid)
        self.info_ch = self.bot.get_channel(self.info_log_cid)


    async def error(self, message: Optional[Union[str, List[str]]], header: Optional[str] = None, code_block: bool = True):

        if self.error_ch is not None:
            msg = await self.send_msg_to_log(self.error_ch, message, header, code_block)
            return msg

        return None


    async def warning(self, message: Optional[Union[str, List[str]]], header: Optional[str] = None, code_block: bool = True):

        if self.warning_ch is not None:
            msg = await self.send_msg_to_log(self.warning_ch, message, header, code_block)
            return msg

        return None


    async def info(self, message: Optional[Union[str, List[str]]], header: Optional[str] = None, code_block: bool = True):

        if self.info_ch is not None:
            msg = await self.send_msg_to_log(self.info_ch, message, header, code_block)
            return msg

        return None


    async def send_msg_to_log(self, log_channel: Optional[discord.TextChannel], error_messages: Optional[Union[str, List[str]]],
                                    header: Optional[str] = None, code_block: bool = False, ) -> bool:

        """
        Attempts to send a message to a Discord Logging Channel.
        Returns False if there is no log_channel,
            if the error_log_channel can not be resolved to an actual channel, or if the message fails to send.
        Returns True if successful.
        """

        if not log_channel:
            return False  # No log channel, can not log

        # Check to see if there was an error message passed and bail if there wasn't
        if error_messages is None:
            return False

        # If list is empty, return
        elif isinstance(error_messages, list):  # If type is list

            if len(error_messages) == 0:  # List is empty. Bail
                return False
            # Convert it into a single string.
            error_messages = "\n".join(error_messages)
        else:
            if error_messages == "":  # Empty
                return False


        # If the header option is used, include the header message at the front of the message
        if header is not None:
            error_messages = f"{header}\n{error_messages}"
        else:
            error_messages = f"{error_messages}"

        # Remove '#' to improve discord codeblock support.
        error_messages = error_messages.replace("#", "⋕")
        # Attempt to send the message
        try:
            await self.send_long_msg(log_channel, error_messages, code_block=code_block)
            return True
        except discord.DiscordException as e:
            self.log.exception(f"Error sending log to Discord Channel!: {e}")
            return False


    async def send_long_msg(self, channel: discord.TextChannel, message: str, code_block: bool = False,
                            code_block_lang: str = "python"):# -> Optional[discord.Message]:

        if code_block:
            if len(code_block_lang) > 0:
                code_block_lang = code_block_lang + "\n"
            code_block_start = "```" + code_block_lang
            code_block_end = "```"
            code_block_extra_length = len(code_block_start) + len(code_block_end)
            chunks = textwrap.wrap(message, width=2000 - code_block_extra_length)
            message_chunks = [code_block_start + chunk + code_block_end for chunk in chunks]

        else:
            message_chunks = textwrap.wrap(message, width=2000)

        for chunk in message_chunks:
            message = await channel.send(chunk)



