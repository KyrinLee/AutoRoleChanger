"""

"""
import logging
from typing import List, Union, Callable, Optional, Tuple, Any  #, Literal
from enum import Enum
import asyncio

import discord
from discord.ext import commands


async def do_nothing(*args, **kwargs):
    pass


#
# class ResponseType(Enum):
#     string = 1  # string input
#     boolean = 2  # Boolean reaction
#     simpleResponse = 3  # non-interactive response message.
#     customResponse = 4  # Allows for a completely custom response. Only calls the callback.
#

class InvalidInput(Exception):
    pass



class DiscordPermissionsError(Exception):
    pass

class AddReactionsError(DiscordPermissionsError):
    def __init__(self):
        super().__init__(f"Insufficient permissions to add reactions to user interface!\nPlease have an admin add the **Add Reactions** and **Read Message History** permissions to this bot.")

# PageType = Literal[
#     "str",
#     "bool",
#     "simple",
#     "custom"
# ]


class Page:
    """
    An interactive form that can be interacted with in a variety of ways including Boolean reaction, string input, non-interactive response message, soon to be more.
    Calls a Callback with the channel and response data to enable further response and appropriate handling of the data.
    """
    LOG = logging.getLogger("PNBot.Page")

    def __init__(self, page_type: str, name: Optional[str] = None, body: Optional[str] = None,
                 callback: Callable = do_nothing, additional: str = None, previous_page: Optional = None, timeout: int = 120.0):
        # self.header_name = header_name
        # self.header_body = header_body
        self.name = name
        self.body = body
        self.additional = additional
        self.timeout = timeout

        self.page_type = page_type.lower()
        self.callback = callback
        self.response = None
        self.previous = previous_page
        self.page_message: Optional[discord.Message] = None
        self.user_message: Optional[discord.Message] = None

    async def run(self, ctx: commands.Context):
        client = ctx.bot

        if self.page_type == "bool":
            await self.run_boolean(client, ctx)
        elif self.page_type == "str":
            await self.run_string(client, ctx)
        elif self.page_type == "simple":
            await self.run_simple_response(client, ctx)
        elif self.page_type == "custom":
            await self.run_custom_response(client, ctx)

        self.LOG.info("Ran {}".format(self.name))

    async def run_boolean(self, client: commands.Bot, ctx: commands.Context):
        """
        Callback signature: page: reactMenu.Page, _client: commands.Bot, ctx: commands.Context, response: bool
        """
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        page_msg = ""
        if self.name is not None:
            page_msg += "**{}**\n".format(self.name)

        if self.body is not None:
            page_msg += "{}\n".format(self.body)

        if self.additional is not None:
            page_msg += "{}\n".format(self.additional)

        page_message = await channel.send(page_msg)
        self.page_message = page_message

        try:
            await page_message.add_reaction("✅")
            await page_message.add_reaction("❌")
        except discord.Forbidden as e:
            await ctx.send(f"CRITICAL ERROR!!! \n{ctx.guild.me.name} does not have the `Add Reactions` permissions!. Please have an Admin fix this issue and try again.")
            raise e

        def react_check(_reaction: discord.Reaction, _user):
            self.LOG.info("Checking Reaction: Reacted Message: {}, orig message: {}".format(_reaction.message.id, page_message.id))

            return _user == ctx.author and (str(_reaction.emoji) == '✅' or str(_reaction.emoji) == '❌')

        try:
            reaction, react_user = await client.wait_for('reaction_add', timeout=self.timeout, check=react_check)
            if str(reaction.emoji) == '✅':
                self.response = True
                await self.remove()
                await self.callback(self, client, ctx, True)
            elif str(reaction.emoji) == '❌':
                self.response = False
                await self.remove()
                await self.callback(self, client, ctx, False)

        except asyncio.TimeoutError:
            await self.remove()

    async def run_string(self, client: commands.Bot, ctx: commands.Context):
        """
        Callback signature: page: reactMenu.Page, _client: commands.Bot, ctx: commands.Context, response: discord.Message
        """
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        page_msg = ""
        if self.name is not None:
            page_msg += "**{}**\n".format(self.name)

        if self.body is not None:
            page_msg += "{}\n".format(self.body)

        if self.additional is not None:
            page_msg += "{}\n".format(self.additional)

        page_message = await channel.send(page_msg)
        self.page_message = page_message

        def message_check(_msg: discord.Message):
            # self.LOG.info("Checking Message: Reacted Message: {}, orig message: {}".format(_reaction.message.id,
            #                                                                                 page_message.id))
            return _msg.author == author and _msg.channel == channel

        try:
            user_msg: discord.Message = await client.wait_for('message', timeout=self.timeout, check=message_check)
            self.user_message = user_msg
            self.response = user_msg
            await self.remove()
            await self.callback(self, client, ctx, user_msg)

        except asyncio.TimeoutError:
            # await ctx.send("Command timed out.")
            await self.remove()


    async def run_simple_response(self, client: commands.Bot, ctx: commands.Context):
        pass

    async def run_custom_response(self, client: commands.Bot, ctx: commands.Context):
        await self.remove()
        await self.callback(self, client, ctx)

    def construct_std_page_msg(self) -> str:
        page_msg = ""
        if self.name is not None:
            page_msg += "**{}**\n".format(self.name)

        if self.body is not None:
            page_msg += "{}\n".format(self.body)

        if self.additional is not None:
            page_msg += "{}\n".format(self.additional)

        # self.page_message = page_message
        return page_msg


    async def remove(self, user: bool = True, page: bool = True):

        if self.previous is not None:
            await self.previous.remove(user, page)

        try:
            if user and self.user_message is not None:
                await self.user_message.delete(delay=1)
        except Exception:
            pass

        try:
            if page and self.page_message is not None:
                await self.page_message.delete(delay=1)
        except Exception:
            pass


class ReactPage(Page):

    def __init__(self, *buttons: Tuple[Union[discord.PartialEmoji, str], Union[Callable, Any]], cancel_btn=True, **kwrgs):
        """
        Callback signature: ctx: commands.Context, page: reactMenu.Page
        """

        self.buttons = list(buttons)
        self.ctx = None
        self.match = None

        if cancel_btn:
            self.buttons.append(("❌", self.cancel))

        super().__init__(page_type="n/a", **kwrgs)

    async def run(self, ctx: commands.Context):
        self.ctx = ctx
        self.page_message: discord.Message = await ctx.send(self.construct_std_page_msg())

        for (reaction, _) in self.buttons:
            try:
                await self.page_message.add_reaction(reaction)
            except discord.Forbidden:
                raise AddReactionsError()

        try:
            payload = await self.ctx.bot.wait_for('raw_reaction_add', timeout=self.timeout, check=self.react_check)

            if callable(self.match):
                await self.match(self.ctx, self)
            # else:
            #     await ctx.send(f"clicked on: {self.match}")

            await self.remove()
        except asyncio.TimeoutError:
            await self.remove()

    def react_check(self, payload):
        """Uses raw_reaction_add"""
        if payload.user_id != self.ctx.author.id:
            return False

        if payload.message_id != self.page_message.id:
            return False

        to_check = str(payload.emoji)
        for (emoji, func) in self.buttons:
            if to_check == emoji:
                self.match = func
                # self.match = emoji
                return True
        return False

    @staticmethod
    async def cancel(ctx, self):
        await self.remove()
        await ctx.send("Canceled!")


class Menu:
    """
    Sends a menu populated by Pages that can be interacted with by the user responding with numbers.
    """
    LOG = logging.getLogger("PNBot.Menu")
    BOOLEAN = "bool"
    SETTINGS = "settings"

    def __init__(self, name: str, body: str, pages: Union[Page, List[Page]], additional: str = ""):

        self.name = name
        self.body = body
        self.additional = additional
        self.sent = []

        if type(pages) == type(Page) or type(pages) == type(Menu):
            self.pages = [pages]
        else:
            self.pages = pages

    async def run(self, ctx: commands.Context):  # , message: discord.Message):

        channel: discord.TextChannel = ctx.channel
        bot = ctx.bot

        header = "**{}**\n{}\n{}".format(self.name, self.body, self.additional)

        self.sent.append(await channel.send(header))

        msg = "```markdown\n"

        for i, page in enumerate(self.pages):

            msg += "[{page_num}]: {page_name}\n# {page_body}\n".format(page_num=i+1, page_name=page.name,
                                                                       page_body=page.body)
        msg += "\n[0]: Cancel```"

        self.sent.append(await channel.send(msg))

        def check(m):
            return m.author.id == ctx.author.id and m.channel == channel

        try:
            response: discord.Message = await bot.wait_for('message', timeout=120.0, check=check)
            content = response.content

            try:
                response_number = int(content)
                if response_number > len(self.pages) or response_number < 0:
                    raise InvalidInput

                if response_number == 0:
                    await ctx.send("Canceled!")
                else:
                    await self.pages[response_number-1].run(ctx)
            except (ValueError, InvalidInput):
                await ctx.send("Invalid Option!")

        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")






