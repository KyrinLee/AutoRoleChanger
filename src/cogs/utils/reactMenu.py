"""

"""
import logging
from typing import List, Union, Callable, Optional
from enum import Enum
import asyncio

import discord
from discord.ext import commands


async def do_nothing(*args, **kwargs):
    pass


class ResponseType(Enum):
    string = 1  # string input
    boolean = 2  # Boolean reaction
    simpleResponse = 3  # non-interactive response message.
    customResponse = 3  # Allows for a completely custom response. Only calls the callback.


class InvalidInput(Exception):
    pass


class Page:
    """
    An interactive form that can be interacted with in a variety of ways including Boolean reaction, string input, non-interactive response message, soon to be more.
    Calls a Callback with the channel and response data to enable further response and appropriate handling of the data.
    """
    LOG = logging.getLogger("PNBot.Page")

    def __init__(self, response: ResponseType, name: Optional[str] = None, body: Optional[str] = None,
                 callback: Callable = do_nothing, additional: str = None):
        # self.header_name = header_name
        # self.header_body = header_body
        self.name = name
        self.body = body
        self.additional = additional

        self.response_type = response
        self.callback = callback
        self.response = None


    async def run(self, client: commands.Bot, ctx: commands.Context):

        if self.response_type == ResponseType.boolean:
            await self.run_boolean(client, ctx)
        elif self.response_type == ResponseType.string:
            await self.run_string(client, ctx)
        elif self.response_type == ResponseType.simpleResponse:
            await self.run_simple_response(client, ctx)
        elif self.response_type == ResponseType.customResponse:
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

        await page_message.add_reaction("✅")
        await page_message.add_reaction("❌")


        def react_check(_reaction: discord.Reaction, _user):
            self.LOG.info("Checking Reaction: Reacted Message: {}, orig message: {}".format(_reaction.message.id, page_message.id))

            return _user == ctx.author and (str(_reaction.emoji) == '✅' or str(_reaction.emoji) == '❌')

        try:
            reaction, react_user = await client.wait_for('reaction_add', timeout=120.0, check=react_check)
            if str(reaction.emoji) == '✅':
                self.response = True
                await self.callback(self, client, ctx, True)
            elif str(reaction.emoji) == '❌':
                self.response = False
                await self.callback(self, client, ctx, False)

        except asyncio.TimeoutError:
            await page_message.remove_reaction("❌", client.user)
            await page_message.remove_reaction("✅", client.user)


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

        def message_check(_msg: discord.Message):
            # self.LOG.info("Checking Message: Reacted Message: {}, orig message: {}".format(_reaction.message.id,
            #                                                                                 page_message.id))
            return _msg.author == author and _msg.channel == channel

        try:
            msg: discord.Message = await client.wait_for('message', timeout=60.0, check=message_check)
            self.response = msg
            await self.callback(self, client, ctx, msg)

        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")

    async def run_simple_response(self, client: commands.Bot, ctx: commands.Context):
        pass

    async def run_custom_response(self, client: commands.Bot, ctx: commands.Context):
        await self.callback(self, client, ctx)


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

        if type(pages) == type(Page) or type(pages) == type(Menu):
            self.pages = [pages]
        else:
            self.pages = pages

    async def run(self, client: commands.Bot, ctx: commands.Context):  # , message: discord.Message):

        channel: discord.TextChannel = ctx.channel

        header = "**{}**\n{}\n{}".format(self.name, self.body, self.additional)
        await channel.send(header)

        msg = "```markdown\n"

        for i, page in enumerate(self.pages):

            msg += "[{page_num}]: {page_name}\n# {page_body}\n".format(page_num=i+1, page_name=page.name,
                                                                       page_body=page.body)
        msg += "\n[0]: Cancel```"

        await channel.send(msg)

        def check(m):
            return m.author.id == ctx.author.id and m.channel == channel

        try:
            response: discord.Message = await client.wait_for('message', timeout=120.0, check=check)

            try:
                response_number = int(response.content)
                if response_number > len(self.pages) or response_number < 0:
                    raise InvalidInput

                if response_number == 0:
                    await ctx.send("Canceled!")
                else:
                    await self.pages[response_number-1].run(client, ctx)
            except (ValueError, InvalidInput):
                await ctx.send("Invalid Option!")

        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")






