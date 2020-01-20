"""

"""

import asyncio
import logging
import re
from typing import Optional, Dict, List

import discord
from discord.ext import commands

import aiohttp

import utils
import db

log = logging.getLogger(__name__)


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.pk_id = 466378653216014359
        self.bot = bot
        self.db = bot.db
        self._last_nick_change: Optional[discord.Member] = None


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.content.lower().strip().startswith("pk;sw"):
            log.info("switch detected!")
            await asyncio.sleep(10)  # Pause to let API catch up
            # pk_info = await self.get_pk_system_by_discord_id(message.author.id)
            await self.update_member(message=message)


    async def update_member(self, ctx: Optional[commands.Context]=None, message: Optional[discord.Message]=None):
        if message is None:
            message:discord.Message = ctx.message

        pk_info = await db.get_system_from_linked_account(self.db, message.author.id)
        if pk_info is not None:
            pk_id = pk_info['pk_system_id']
            fronters = await self.get_pk_system_fronters(pk_id)
            if fronters is not None:
                log.info(f"Got fronters: {fronters}")
                first_fronter = fronters['members'][0]
                proto_roles = await db.get_roles_for_member(self.db, first_fronter['id'], message.guild.id)
                roles = []
                for proto_role in proto_roles:
                    roles.append(discord.Object(id=proto_role['role_id']))

                author: discord.Member = message.author
                log.info(f"Setting {first_fronter['name']}'s {len(roles)} role(s) on {author.display_name}")
                await author.edit(roles=roles)

                try:
                    await author.edit(nick=first_fronter['name'])
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.system_channel
        if channel is not None:
            await channel.send('Welcome {0.mention}.'.format(member))


    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        event_type_nick = "guild_member_nickname"  # nickname
        event_type_update = "guild_member_update"  # Everything else. Currently unused.

        if before.nick != after.nick:
            log.info(f"{after.nick} changed their nickname from {before.nick}")
            self._last_nick_change = after


    @commands.command()
    async def nick(self, ctx: commands.Context, name: str):
        await ctx.author.edit(nick=name)
        await ctx.send(f"Set name to {name}")

    @commands.command()
    async def add_role(self, ctx: commands.Context, member_id: str, role: discord.Role):
        log.info(f"Adding Role: {role.name} to member {member_id}")
        # Todo: Ensure pk member exists
        if len(member_id) != 5:
            await ctx.send(f"`{member_id}` is not a valid member id")
            return
        await db.add_role_to_member(self.db, ctx.guild.id, member_id, role.id)
        await ctx.send(f"Added {role.name} to member {member_id}")


    @commands.command()
    async def remove_role(self, ctx: commands.Context, member_id: str, role: discord.Role):
        log.info(f"Removing Role: {role.name} from member {member_id}")
        # Todo: Ensure pk member exists
        if len(member_id) != 5:
            await ctx.send(f"`{member_id}` is not a valid member id")
            return
        await db.remove_role_from_member(self.db, ctx.guild.id, member_id, role.id)
        await ctx.send(f"Removed {role.name} from member {member_id}")


    @commands.command()
    async def reg_sys(self, ctx: commands.Context):
        """The last nick change"""

        await ctx.send(f"To register your Plural Kit account, please use the command `pk;s` to have Plural Kit send you system card")

        def check_for_pk_response(m: discord.Message):
            # log.info(f"Got Message: {m}, Embeds: {len(m.embeds)}")
            return m.author.id == self.pk_id and len(m.embeds) == 1

        try:
            pk_msg: discord.Message = await self.bot.wait_for('message', timeout=45.0, check=check_for_pk_response)
        except asyncio.TimeoutError:
            await ctx.send("Command timed out!")
            return None

        log.info(f"Got PK Embed: {pk_msg.embeds}")
        pk_info = self.parse_system_card(pk_msg.embeds[0])

        detailed_sys_info = await self.get_pk_system_by_pkid(pk_info['system_id'])
        try:
            member_info = await self.get_pk_system_members(pk_info['system_id'])
        except MemberListHidden:
            await ctx.send(f"Your Plural Kit setting require that I get additional information for in order to operate properly.\n"
                           f"Sending you a DM for further configuration.")
            await self.prompt_for_pk_token(ctx)
            return


        # log.info(detailed_sys_info)
        # log.info(member_info)

        log.info(f"adding new system to DB: {detailed_sys_info['name']}")
        await db.add_new_system(self.db, pk_info['system_id'], detailed_sys_info['name'], None, None)

        log.info(f"adding linked discord accounts DB: {detailed_sys_info['name']}")

        for account in pk_info['discord_accounts']:
            await db.add_linked_discord_account(self.db, pk_info['system_id'], int(account))

        for member in member_info:
            log.info(f"adding new member to DB: {member['name']}")
            await db.add_new_member(self.db, pk_info['system_id'], member['id'], member['name'], fronting=False)

        await ctx.send(f"Your system and {len(member_info)} members of your system have been registered successfully!\n"
                       f"Any hidden members may now be registered manually.")


    def parse_system_card(self, embed: discord.Embed) -> Dict:
        discord_member_id_regex = "<@!?([0-9]{15,21})>"
        pk_system_id_regex = "System ID: ([A-Za-z]{5})"

        if len(embed.fields) == 0:
            raise UnableToParseSystemCard(f"No embed fields present!")

        linked_account_field = None
        for field in embed.fields:
            if field.name == 'Linked accounts':
                linked_account_field = field

        if linked_account_field is None:
            raise UnableToParseSystemCard(f"Could not locate the 'Linked accounts' field'")

        discord_accounts = re.findall(discord_member_id_regex, linked_account_field.value)

        if len(discord_accounts) == 0:
            raise UnableToParseSystemCard(f"Unable to find any linked account ids. Field: {linked_account_field.value}!")

        if not hasattr(embed.footer, 'text'):
            raise UnableToParseSystemCard(f"No footer present in embed!")

        pk_system_id = re.findall(pk_system_id_regex, embed.footer.text)
        if len(pk_system_id) == 0:
            raise UnableToParseSystemCard(f"Unable to find pk system ID. Field: {embed.footer.text}!.")

        pk_info = {
            'discord_accounts': discord_accounts,
            'system_id': pk_system_id[0]
        }
        return pk_info


    async def prompt_for_pk_token(self, ctx: commands.Context):
        author: discord.Member = ctx.author

        dm_channel: discord.DMChannel = author.dm_channel
        if dm_channel is None:
            log.warning(f"Creating DM Channel for {author.display_name}")
            dm_channel = await author.create_dm()

        await dm_channel.send("Due to your Plural Kit privacy settings, I am unable to get a list of your system members.\n"
                              "As such, I require your Plural Kit system token. "
                              "Since you are obviously concerned about your systems privacy, "
                              "let me reassure you that all of your private information will be kept encrypted and that none of your details will **EVER** be shared with anyone else or looked at by the developer of this bot.\n"
                              "You may retrieve your system token by DMing <@!466378653216014359> with the command: `pk;token`\n"
                              "Once you have done so, please send that token to me via DM. And remember, never post your system token in a public channel!")
        # TODO: Implement PK Token stuff.


    async def get_pk_system_fronters(self, pk_sys_id: str) -> Dict:
        try:
            async with aiohttp.ClientSession() as session:
                log.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}/fronters'}")
                async with session.get(f'https://api.pluralkit.me/s/{pk_sys_id}/fronters') as r:
                    if r.status == 200:  # We received a valid response from the PK API.
                        # TODO: Remove logging once bugs are worked out.
                        log.info(f"Got Fronters for: {pk_sys_id}")
                        # Convert the JSON response to a dict, Cache the details of the proxied message, and then bail.
                        pk_response = await r.json()
                        # log.info(f"Response: {pk_response}")
                        return pk_response
                    else:
                        log.warning(f"Could not get Fronters info! Status Code: {r.status}")
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))


    async def get_pk_system_by_pkid(self, pk_sys_id: str) -> Dict:

        try:
            async with aiohttp.ClientSession() as session:
                log.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}'}")
                async with session.get(f'https://api.pluralkit.me/s/{pk_sys_id}') as r:
                    if r.status == 200:  # We received a valid response from the PK API.
                        # TODO: Remove logging once bugs are worked out.
                        log.info(f"Got response for System: {pk_sys_id}")
                        # Convert the JSON response to a dict, Cache the details of the proxied message, and then bail.
                        pk_response = await r.json()
                        # log.info(f"Response: {pk_response}")
                        return pk_response
                    else:
                        log.warning(f"Could not get system info! Status Code: {r.status}")
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))


    async def get_pk_system_by_discord_id(self, discord_member_id: int) -> Dict:

        try:
            async with aiohttp.ClientSession() as session:
                log.warning(f"Scraping: {f'https://api.pluralkit.me/a/{discord_member_id}'}")
                async with session.get(f'https://api.pluralkit.me/a/{discord_member_id}') as r:
                    if r.status == 200:  # We received a valid response from the PK API.
                        # TODO: Remove logging once bugs are worked out.
                        log.info(f"Got response for System: {discord_member_id}")
                        # Convert the JSON response to a dict, Cache the details of the proxied message, and then bail.
                        pk_response = await r.json()
                        # log.info(f"Response: {pk_response}")
                        return pk_response
                    else:
                        log.warning(f"Could not get system info! Status Code: {r.status}")
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))


    async def get_pk_system_members(self, pk_sys_id: str) -> List[Dict]:

        try:
            async with aiohttp.ClientSession() as session:
                log.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}/members'}")
                async with session.get(f'https://api.pluralkit.me/s/{pk_sys_id}/members') as r:
                    if r.status == 200:  # We received a valid response from the PK API.
                        # TODO: Remove logging once bugs are worked out.
                        log.info(f"Got response for Members in System: {pk_sys_id}")
                        # Convert the JSON response to a dict, Cache the details of the proxied message, and then bail.
                        pk_response = await r.json()
                        # log.info(f"Response: {pk_response}")
                        return pk_response
                    elif r.status == 403:
                        # Can not get members with out a valid system token.
                        raise MemberListHidden
                    else:
                        log.warning(f"Could not get member info! Status Code: {r.status}")
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    # async def example_pk_sys_embed(self, ctx: commands.Context):
    #
    #     fields = [
    #         EmbedProxy(
    #             inline=False,
    #             name='Fronter',
    #             value='Luna'
    #         ),
    #         EmbedProxy(
    #             inline=False,
    #             name='Tag',
    #             value='-Amadea-'
    #         ),
    #         EmbedProxy(
    #             inline=False,
    #             name='Linked accounts',
    #             value='Hibiki#8792 (<@!389590659335716867>)'
    #         ),
    #         EmbedProxy(
    #             inline=False,
    #             name='Members (4)',
    #             value='(see `pk;system gxrhr list` or `pk;system gxrhr list full`)'
    #         ),
    #     ]
    #
    #     footer = EmbedProxy(
    #         text='System ID: gxrhr | Created on 2018-07-29 18:07:03 EDT'
    #     )


    @commands.command()
    async def last_nick(self, ctx):
        """The last nick change"""
        if self._last_nick_change is None:
            await ctx.send('No one has changed their nick!')
        else:
            await ctx.send(f'Last nick change: {self._last_nick_change}')


def setup(bot):
    bot.add_cog(AutoRole(bot))


class UnableToParseSystemCard(Exception):
    pass


class MemberListHidden(Exception):
    pass
