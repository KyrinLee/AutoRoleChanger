"""

"""

import asyncio
import logging
import inspect
import re
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple
from collections import namedtuple
from datetime import datetime, timedelta

import discord
from discord.ext import tasks, commands

import aiohttp
import db

import cogs.utils.pluralKit as pk
import cogs.utils.reactMenu as reactMenu
from cogs.utils.paginator import FieldPages
from cogs.utils.autoRoleUtils import parse_csv_roles, ParsedRoles

from cogs.utils.dLogger import dLogger
from botExceptions import UnsupportedGuild

if TYPE_CHECKING:
    from discordBot import PNBot

log = logging.getLogger(__name__)
authorized_guilds = [433446063022538753, 624361300327268363]

"""
TODO:
    Add System Tag support. Make it a user setting.
    Add proper alt account support. 
"""

# Unicode Characters:
"\N{ZERO WIDTH NON-JOINER}"  # \u200c
"\N{ZERO WIDTH SPACE}"  # \u200b Mentioned on d.py discord


def is_authorized_guild():
    async def predicate(ctx):

        if ctx.guild is None:  # Double check that we are not in a DM.
            raise commands.NoPrivateMessage()

        if ctx.guild.id not in authorized_guilds:
            raise UnsupportedGuild()

        return True

    return commands.check(predicate)


class AutoRoleChanger(commands.Cog):
    def __init__(self, bot: 'PNBot'):
        self.pk_id = 466378653216014359
        self.db = bot.db
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        author: Union[discord.Member, discord.User] = message.author
        if not author.bot:
            msg = message.content.lower().strip()
            if msg.startswith("pk;sw") or msg.startswith("pk!sw"):
                await self.info(F"PluralKit switch command detected! Checking for new fronters in 30 seconds. System: {message.author.display_name}")
                await asyncio.sleep(30)  # Pause to let API catch up
                await self.info(f"Now checking fronters for {message.author.display_name}, attempting to call: update_only_fronters")
                # pk_info = await self.get_pk_system_by_discord_id(message.author.id)
                # await self.update_system(message=message)
                # await self.update_only_fronters(message=message)
                await self.update_system_members(force_member_update=True, message=message)
            else:
                # await self.info(f"Message received from {message.author.display_name}, attempting to call: update_system")

                # Once an hour, make sure that the entire systems info is updated.
                # This done based off the last updated time in the DB
                # await self.update_members(message=message, time_override=60 * 60)
                await self.update_system_members(db_expiration_age=60*60, message=message)# Update from any message once an hour (The default time)

    # async def update_member(self, discord_member: discord.Member = None, ctx: Optional[commands.Context] = None, message: Optional[discord.Message] = None):
    #     if ctx is not None:
    #         discord_member: discord.Member = ctx.author
    #         message: discord.Message = ctx.message
    #
    #     if message is not None:
    #         discord_member: discord.Member = message.author
    #
    #     pk_info = await db.get_system_id_from_linked_account(self.db, message.author.id)
    #     if pk_info is not None:
    #         pk_id = pk_info['pk_system_id']
    #         fronters = await self.get_fronters(pk_id)
    #         if fronters is not None:
    #             log.info(f"Got fronters: {fronters}")
    #             first_fronter = fronters.members[0]
    #
    #             proto_roles = await db.get_roles_for_member_by_guild(self.db, first_fronter.hid, message.guild.id)
    #             roles = []
    #             for proto_role in proto_roles:
    #                 roles.append(discord.Object(id=proto_role['role_id']))
    #
    #             log.info(f"Setting {first_fronter.proxied_name}'s {len(roles)} role(s) on {discord_member.display_name}")
    #             await discord_member.edit(roles=roles)
    #
    #             try:
    #                 await discord_member.edit(nick=first_fronter.proxied_name)
    #             except Exception:
    #                 pass


    # async def update_members(self, discord_member: discord.Member = None, ctx: Optional[commands.Context] = None,
    #                          message: Optional[discord.Message] = None, time_override=86400):
    #     """ This method updates the DB with every member of a system (not just the fronting members).
    #         It is designed to be called fairly often.
    #
    #         It checks the last DB update time for the system,
    #             and only hits the members & fronters API endpoints IF the records are older than time_override.
    #         This helps to ensure that the PK API is not abused.
    #         It then checks the fronters reported by PK against the fronters in the Database.
    #             If they are different, it calls the Discord APIs to change name and roles.
    #
    #         Min resource usage:
    #             One DB Call.
    #         Max resource usage:
    #             4 DB Calls.
    #             2 PK API Calls.
    #     """
    #     if ctx is not None:
    #         discord_member: discord.Member = ctx.author
    #         message: discord.Message = ctx.message
    #
    #     if message is not None:
    #         discord_member: discord.Member = message.author
    #
    #     members = await db.get_members_by_discord_account_if_ood(self.db, discord_member.id, time_override)
    #     if members is not None and len(members) > 0:
    #
    #         system_id = members[0]['pk_sid']
    #         await self.info(f"updating {system_id}")
    #
    #         updated_members = await self.get_system_members(system_id)
    #
    #         previous_fronters = await db.get_fronting_members_by_pk_sid(self.db, system_id)
    #         current_fronters = await self.get_fronters(system_id)
    #         for member in updated_members:
    #             fronting = True if member in current_fronters.members else False
    #             await db.update_member(self.db, system_id, member.hid, member.name, fronting=fronting)
    #
    #         if previous_fronters != current_fronters.members:
    #             await self.info(f"Fronters changed!: Prev: {previous_fronters},\n Cur: {current_fronters}")
    #
    #             roles = []
    #             for fronter in current_fronters.members:
    #                 new_roles = await db.get_roles_for_member_by_guild(self.db, fronter.hid, authorized_guilds[0])  # Force using only authorised guild for now. #discord_member.guild.id)
    #                 if new_roles is not None:
    #                     new_roles_ids = [discord.Object(id=role['role_id']) for role in new_roles]
    #                     roles.extend(new_roles_ids)
    #
    #             new_name = current_fronters.members[0].proxied_name if len(current_fronters.members) > 0 else None
    #             await self.autochange_discord_user(discord_member, roles, new_name)


    # async def get_new_roles_and_name_for_all_guilds(self, current_fronters: pk.Fronters, discord_user_id):
    #
    #     settings = await db.get_all_user_settings_from_discord_id(self.db, discord_user_id)
    #
    #     all_roles = {}
    #     new_name = current_fronters.members[0].proxied_name if len(current_fronters.members) > 0 else None
    #     for setting in settings:
    #         roles = []
    #         for fronter in current_fronters.members:
    #             new_roles = await db.get_roles_for_member_by_guild(self.db, fronter.hid, setting.guild_id)
    #             new_roles_ids = [discord.Object(id=role['role_id']) for role in new_roles]
    #             roles.extend(new_roles_ids)
    #
    #         guild: discord.Guild = await self.bot.get_guild(setting.guild_id)
    #
    #         if guild is not None:
    #             discord_member = await guild.get_member(discord_user_id)
    #             if discord_member is not None:
    #                 await self.autochange_discord_user(discord_member, roles, new_name)
    #
    #         # all_roles[setting.guild_id] = roles
    #
    #     # await self.autochange_discord_user(discord_member, roles, current_fronters.members[0].proxied_name)


    # async def update_only_fronters(self, discord_member: discord.Member = None, ctx: Optional[commands.Context] = None,
    #                                message: Optional[discord.Message] = None, force_update=False):
    #     """ This method updates updates the DB with only the members of the system that are fronting.
    #         It is designed to be called ONLY when we are reasonably sure that there has been a switch.
    #
    #         It checks the last DB update time for the system,
    #             and only hits the members & fronters API endpoints IF the records are older than time_override.
    #         This helps to ensure that the PK API is not abused.
    #         It then checks the fronters reported by PK against the fronters in the Database.
    #             If they are different, it calls the Discord APIs to change name and roles.
    #
    #         Min resource usage:
    #             One DB Call.
    #         Max resource usage:
    #             4 DB Calls.
    #             2 PK API Calls.
    #     """
    #     if ctx is not None:
    #         discord_member: discord.Member = ctx.author
    #         message: discord.Message = ctx.message
    #
    #     if message is not None:
    #         discord_member: discord.Member = message.author
    #
    #     previous_fronters = await db.get_fronting_members_by_discord_account(self.db, discord_member.id)
    #
    #     if previous_fronters is not None:
    #         system_id = previous_fronters[0].sid
    #     else:  # No one was in front. Get system_id from discord id
    #         sys_info = await db.get_system_id_by_discord_account(self.db, discord_member.id)
    #         if sys_info is None:
    #             return  # No registered account exists.
    #         system_id = sys_info['pk_system_id']
    #
    #     # FIXME: This incorrectly will leave the previous fronters still marked as in front.
    #     current_fronters = await self.get_fronters(system_id)
    #     for member in current_fronters.members:
    #         fronting = True
    #         await db.update_member(self.db, system_id, member.hid, member.name, fronting=fronting)
    #
    #     if previous_fronters != current_fronters.members or force_update:
    #         await self.info(f"Fronters changed!: Prev: {previous_fronters}, \nCur: {current_fronters}")
    #
    #         roles = []
    #         for fronter in current_fronters.members:
    #             new_roles = await db.get_roles_for_member_by_guild(self.db, fronter.hid, authorized_guilds[0])  # Force using only authorised guild for now.# discord_member.guild.id)
    #             if new_roles is not None:
    #                 new_roles_ids = [discord.Object(id=role['role_id']) for role in new_roles]
    #                 roles.extend(new_roles_ids)
    #
    #         new_name = current_fronters.members[0].proxied_name if len(current_fronters.members) > 0 else None
    #         await self.autochange_discord_user(discord_member, roles, new_name)


    async def update_system_members(self, force_member_update: bool = False, force_discord_update: bool = False, db_expiration_age:int = 86400,
                                    discord_member: discord.Member = None, ctx: Optional[commands.Context] = None,
                                    message: Optional[discord.Message] = None):

        # Assign the proper variables from ctx/message.
        if ctx is not None:
            discord_member: discord.Member = ctx.author
            message: discord.Message = ctx.message

        if message is not None:
            discord_member: discord.Member = message.author

        # We will try several methods to get the PK System ID. Set it to None for now, so we can know to stop trying...
        stale_members = system_id = None
        if not force_member_update and not force_discord_update:
            # Try to get any members that are past the expiration age.
            # This is only to see if enough time has passed.
            # If it has, we might as well get the PK System ID from the returned data.
            # TODO: Find a better way of determining when to update?
            stale_members = await db.get_members_by_discord_account_if_ood(self.db, discord_member.id, db_expiration_age)
            if stale_members is None:
                # It's not soon enough to try to do a full update. Bail for now.
                return
            await self.info(f"DB info is STALE ({round((datetime.utcnow().timestamp() - stale_members[0]['last_update'])/60)} min) for {stale_members[0]['member_name']}")
            system_id = stale_members[0]['pk_sid']

        # We need to get the stored fronters from the DB at this point.
        # This is needed to determine if we need to call the Discord API later.
        stale_fronters = await db.get_fronting_members_by_discord_account(self.db, discord_member.id)

        # Try to get the system id from the fronters stored in the DB
        # Stored fronters will be none if there is no one fronting or if the system does not exist in the DB.
        if stale_fronters is not None and system_id is None:
            system_id = stale_fronters[0].sid

        # If we STILL don't have a system ID, pull it from the DB directly.
        # (all the previous attempts DB calls still needed to happen, so by trying at each stage we can potentially save a DB call.)
        if system_id is None:
            sys_info = await db.get_system_id_by_discord_account(self.db, discord_member.id)
            if sys_info is None:
                return  # No registered account exists. Bail.
            system_id = sys_info['pk_system_id']

        # We definitely have a system_id at this point, start calling the PK API.
        # Get Fresh members and fronters
        # TODO: Do not get a full update of members on EVERY update...
        #  The only time that we need upto date info on all system members is when commands are being used to ensure proper lookup of members..
        try:
            updated_members = await self.get_system_members(system_id)
        except MemberListHidden:
            # TODO: Instead of silently failing, try to DM the discord account to alert them to the problem, then unregister the user.
            return

        updated_fronters = await self.get_fronters(system_id)  # TODO: Ask alyssa & astrid about using GET /s/<id>/switches[?before=] first.

        # Update the DB with the new information.
        # TODO: Compare with the stale information and only update what has changed.
        for update_member in updated_members:
            # TODO: When we stop updating all members, we will need to maybe set all members to not fronting THEN set the members that are frontring to fronting.
            #  Alternatively, we could have a fronting table... Then we could just delete the members from the table, and add the current ones....
            fronting = True if update_member in updated_fronters.members else False
            await db.update_member(self.db, system_id, update_member.hid, update_member.name, fronting=fronting)
        await self.info(f"Updated members for {discord_member.name}")

        # TODO: The below code seems to be broken and deletes members when it should not. Fix.
        # Clean up the DB and remove and remove any members that no longer exist (or are private at this point)
        # We are going to go off the stale_member data as this doesn't need to happen EVERY time.
        # if stale_members is not None:
        #     for stale_member in stale_members:
        #
        #         found = False
        #         for updated_member in updated_members:
        #             if stale_member == updated_member:
        #                 found = True
        #                 break
        #         if not found:
        #             await self.warning(f"DELETING member in {discord_member.name}'s system: {stale_member}")
        #             await db.delete_member(self.db, stale_member['pk_sid'], stale_member['pk_mid'])

        # Put the stale_fronters into a better format for logging...
        log_stale_fronters = [fronter.hid for fronter in stale_fronters] if stale_fronters is not None else None
        if force_discord_update or stale_fronters is None or stale_fronters != updated_fronters.members:

            await self.info(f"Fronters changed!: Prev: {log_stale_fronters}, \n\nCur: {updated_fronters}")

            roles = []
            for fronter in updated_fronters.members:
                new_roles = await db.get_roles_for_member_by_guild(self.db, fronter.hid, authorized_guilds[0])  # Force using only authorised guild for now.# discord_member.guild.id)
                if new_roles is not None:
                    new_roles_ids = [discord.Object(id=role['role_id']) for role in new_roles]
                    roles.extend(new_roles_ids)

            await self.autochange_discord_user(discord_member, system_id, roles, updated_fronters)
        else:
            await self.info(f"Not updating roles: force_discord_update:{force_discord_update}, "
                            f"\nstale_fronters: {log_stale_fronters} "
                            f"\nupdated_fronters.members: {updated_fronters.members}"
                            f"\nComparison: {stale_fronters != updated_fronters.members}")

    async def update_system(self, discord_id: Optional[int] = None, system_id: Optional[str] = None) -> pk.System:

        # TODO: See if a system tag override is set and if so don't call PK API
        # TODO: Implement Caching.
        if system_id:
            updated_system = await self.get_system(system_id)
        elif discord_id:
            updated_system = await self.get_system_by_discord_id(discord_id)
        else:
            raise SyntaxError("Either the discord_id &/or system id MUST be passed.")

        # Update the db
        await db.update_system_by_pk_sid(self.db, updated_system.hid, updated_system.name, updated_system.tag)

        return updated_system

    async def autochange_discord_user(self,  discord_member: Union[discord.Member, discord.User], pk_system_id: str, new_roles: List[Union[discord.Role, discord.Object]], updated_fronters: Optional[pk.Fronters]):
        """Applies the new roles and name to the selected discord user"""

        # guild: discord.Guild = discord_member.guild

        if discord_member.guild.id in authorized_guilds:
            guild: discord.Guild = discord_member.guild
        else:
            guild: discord.Guild = self.bot.get_guild(authorized_guilds[0])
            if guild is None:
                await self.info(f"Can not set roles/name! User was not in the authorized guild!")
                return

            member_id = discord_member.id
            discord_member = guild.get_member(member_id)
            if discord_member is None:
                await self.info(f"Can not set roles/name! Unable to get discord_member {member_id} in autochange_discord_user")
                return

        user_settings = await db.get_user_settings_from_discord_id(self.db, discord_member.id, guild.id)  # discord_member.guild.id)

        if user_settings.role_change:
            await self.info(f"Setting {discord_member.display_name}'s {len(new_roles)} role(s)")

            guild_allowed_auto_roles = await db.get_allowable_roles(self.db, guild.id)  # discord_member.guild.id)

            # Get the auto roles to set and get the roles we must keep
            allowed_new_roles = guild_allowed_auto_roles.allowed_intersection(new_roles)
            old_roles_to_keep = guild_allowed_auto_roles.disallowed_intersection(discord_member.roles)

            # Use a set to ensure there are no duplicates.
            roles_to_set = set(allowed_new_roles + old_roles_to_keep)
            await self.info(f"Applying the following roles: {roles_to_set}")

            try:
                await discord_member.edit(roles=set(roles_to_set))
            except discord.errors.Forbidden:
                await self.info(f"Could not set roles: {roles_to_set} on {discord_member.display_name}")

        if user_settings.name_change and len(updated_fronters.members) > 0:  # TODO: Add option to set system name as nickname when no one is fronting.

            if user_settings.system_tag_override is None:
                updated_system = await self.update_system(system_id=pk_system_id)
                system_tag = updated_system.tag
            else:
                system_tag = user_settings.system_tag_override

            new_name = f"{updated_fronters.members[0].proxied_name} {system_tag}" if system_tag else updated_fronters.members[0].proxied_name

            await self.info(f"Changing {discord_member.display_name} name to {new_name}'s name")
            try:
                await discord_member.edit(nick=new_name)
            except discord.errors.Forbidden:
                await self.info(f"Forbidden! Could not change {discord_member.display_name}'s name")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        event_type_nick = "guild_member_nickname"  # nickname
        event_type_update = "guild_member_update"  # Everything else. Currently unused.

        if before.nick != after.nick:
            await self.info(f"{after.nick} changed their nickname from {before.nick}, attempting to call: update_only_fronters")

            # Update in nickname change if 5 minutes have passed since the last update.

            # We have very low threshold here so that way we don't get in the users way too much
            # The limit IS needed however, if not only to prevent abuse,
            # but to prevent update_system_members from being called twice when WE update the name
            await self.update_system_members(discord_member=after, db_expiration_age=60 * 1)

    @commands.is_owner()
    @commands.command(name="crash")
    async def crash(self, ctx):
        assert 1 == 0

    # ----- Help & About Commands ----- #

    @commands.command(name="help", hidden=False, usage="['command' | more]")
    async def _help(self, ctx, *args):

        if args:
            await ctx.send_help(*args)
        else:
            # await ctx.send(embed=embeds.about_message())
            # await self.help_screen(ctx)
            get_started = [
                f"To get started using Auto Role Changer first take a look at the get started page by using **{self.bot.command_prefix}get_started**",
                f"Then register your system using **{self.bot.command_prefix}register**",
            ]

            important_notes = [
                f"Please note that Role and Name changing is _off_ by default and must be turned on after you have registered for them to work."
            ]

            tips = [
                f"Most commands have shorter aliases. You can find them by using **{self.bot.command_prefix}help <command name>**"
            ]

            embed = discord.Embed(title="Auto Role Changer Help")
            # embed.description = "\n".join(get_started)
            embed.add_field(name="Getting Started", value="\n".join(get_started), inline=False)
            embed.add_field(name="Important Notes", value="\n".join(important_notes), inline=False)
            embed.add_field(name="Tips", value="\n".join(tips), inline=False)
            await ctx.send(embed=embed)
            await ctx.send_help()

    @commands.command(name="get_started")
    async def getting_started(self, ctx):
        role_and_name_settings = "Off"
        embed = discord.Embed(title="Auto Role Changer Getting Started")
        # embed.add_field(name="Current Settings:", value=f"Auto name and role changing is currently **{role_and_name_settings}**. No roles are set")
        zws = "\N{ZERO WIDTH SPACE}"
        dot = "\N{Middle Dot}"
        started = [
            f"First you must register your system by using the **{self.bot.command_prefix}register** command.\n",
            f"You should then change your auto name and role changing settings by using the **{self.bot.command_prefix}settings** command.\n",
            f"You may set up your system members roles by using the **{self.bot.command_prefix}add_role** command.\n",
            f"You can see the list of roles a system member has using the **{self.bot.command_prefix}list_roles** command.\n",
            f"If you need to remove any roles, use the **{self.bot.command_prefix}remove_role** command.\n",
            f"Take a look at the rest of the commands with the **{self.bot.command_prefix}help** command.\n{zws}"
        ]

        when_does_it_work = [
            f"Currently Auto Role Changer check to see if you have switched for the following reasons:\n",
            f"\N{bullet} 30 seconds after using a Plural Kit switch command in a server with Auto Role Changer. (The 30 second delay is to allow account for lag in the Plural Kit API)",
            f"\N{bullet} After a nickname change in a server with Auto Role Changer.",
            f"\N{bullet} Once an hour, but only if you have been talking in the server.",
            f"\N{bullet} When the **{self.bot.command_prefix}update** command has been used.\n{zws}"
        ]

        where_does_it_work = [
            f"Currently, Roles and Nicknames are only changed on Plural Nest, however feel free to invite Auto Role Changer to your personal/public server.",
            # f"This will give you the immediate benefit of those actions described above working for you in other servers.",
            f"This will give you the benefit of letting Auto Role Changer be able to detect your switches when the appropriate actions are done in other servers.",
            f"In the future, Auto Role Changer will be able to change your roles and Nickname in other servers as well!\n",
        ]

        embed.add_field(name="How to get started:",
                        value=f"\n{zws}".join(started),
                        inline=False)
        embed.add_field(name="When does the Auto Role Changer change your roles and/or name?",
                        value=f"\n{zws}".join(when_does_it_work),
                        inline=False)
        embed.add_field(name="Where does Auto Role Changer change your roles and/or name?",
                        value=f"\n{zws}".join(where_does_it_work),
                        inline=False)

        await ctx.send(embed=embed)


    @commands.guild_only()
    @commands.command(name="update", aliases=["sw"], brief="Update who is fronting.",
                      description="Cause the bot to check with PK to see who is fronting.\n"
                                  "If the fronter has changed, roles and nicknames will be updated accordingly.")
    async def update_command(self, ctx: commands.Context):

        # await self.update_members(ctx=ctx, time_override=1)
        # await self.update_only_fronters(ctx=ctx, force_update=True)  # TODO: Update update_system so both do not ahve to be called.
        await self.update_system_members(force_discord_update=True, ctx=ctx)
        if ctx.guild.id in authorized_guilds:
            user_settings = await db.get_user_settings_from_discord_id(self.db, ctx.author.id, ctx.guild.id)
            if not user_settings.role_change and not user_settings.name_change:
                await ctx.send(f"You do not have roles or name changes enabled! You can enable them with the **{self.bot.command_prefix}settings** command.")
            elif user_settings.role_change and user_settings.name_change:
                await ctx.send("System updated! If your roles and name did not update, please try again in a minute.")
            elif user_settings.role_change:
                await ctx.send("System updated! If your roles did not update, please try again in a minute.")
            elif user_settings.name_change:
                await ctx.send("System updated! If your name did not update, please try again in a minute.")


    # @is_authorized_guild()
    @commands.guild_only()
    @commands.command(aliases=["list", "List_roles"], brief="See what roles are assigned to your system members.")
    async def list_member_roles(self, ctx: commands.Context):
        member_input = reactMenu.Page("str", name="List Roles",
                                      body="Please enter the name or ID of the System Member below:")
        await member_input.run(self.bot, ctx)
        if member_input is not None:
            member = await db.get_member_fuzzy(self.db, ctx.author.id, member_input.response.content)
            if member is not None:
                roles = await db.get_roles_for_member_by_guild(self.db, member['pk_mid'], ctx.guild.id)
                if roles is not None:
                    embed = discord.Embed()
                    embed.set_author(name=f"{member['member_name']}'s roles:")
                    roles_msg = "\n".join([f"<@&{role['role_id']}>" for role in roles])
                    embed.description = roles_msg
                    await ctx.send(embed=embed)
                else:
                    await ctx.send(f"{member['member_name']} has no roles!")
            else:
                await ctx.send(f"Could not find {member_input.response.content} in your system. Try using the 5 character Plural Kit ID.")

    # @is_authorized_guild()
    @commands.guild_only()
    @commands.command(aliases=["list_all", "list_all_roles"], brief="See what roles are assigned to all of your system members.")
    async def list_all_member_roles(self, ctx: commands.Context):

        members = await db.get_members_by_discord_account(self.db, ctx.author.id)

        if members is None or len(members) == 0:
            await ctx.send(
                f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
            return

        # largest_embed = 0
        member_roles = []
        for member in members:
            roles = await db.get_roles_for_member_by_guild(self.db, member['pk_mid'], ctx.guild.id)
            if roles is not None:
                role_msgs = []
                role_strs = []
                role_strs_len = 0
                for role in roles:
                    role_str = f"<@&{role['role_id']}>"
                    if role_strs_len + len(role_str) + 2 <= 900:
                        role_strs_len += len(role_str)
                        role_strs.append(role_str)
                    else:
                        role_strs_len = len(role_str)
                        role_msgs.append(", ".join(role_strs))
                        role_strs.clear()
                        role_strs.append(role_str)

                if len(role_strs) > 0:
                    role_msgs.append(", ".join(role_strs))
            else:
                role_msgs = ["No Roles!"]

            if len(role_msgs) > 1:
                role_fields = 1
                for msg in role_msgs:
                    member_roles.append((f"{member['member_name']} ({role_fields}/{len(role_msgs)})", msg))
                    role_fields += 1
            else:
                await self.warning(f"role_msgs: {role_msgs}, Member: {member}, roles: {roles}")
                member_roles.append((f"{member['member_name']}", role_msgs[0]))

        page = FieldPages(ctx, entries=member_roles, per_page=6)
        page.embed.title = f"Roles:"
        await page.paginate()

    @commands.guild_only()
    @commands.command(aliases=["remove_roles", "remove", "rm"], brief="Remove roles from system members.",
                      description="Lets you remove roles from one or multiple system members.")
    async def remove_role(self, ctx: commands.Context):
        settings = self.CSVRemoveRolesMenuHandler(self.bot, ctx)
        await settings.run()

    class CSVRemoveRolesMenuHandler:

        def __init__(self, bot, ctx):
            self.bot = bot
            self.db = bot.db
            self.ctx = ctx
            self.member = None
            self.role = None

            self.allowable_roles: Optional[db.AllowableRoles] = None

        async def run(self):

            self.allowable_roles = await db.get_allowable_roles(self.db, self.ctx.guild.id)
            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return

            remove_roles = reactMenu.Page("str", name="Remove roles from a member",
                                          body="Remove any number of roles from one system member",
                                          additional="Please enter a System Member below:",
                                          callback=self.select_member_for_role)

            remove_roles_to_all_members = reactMenu.Page("str",
                                                         name="Remove roles from all your system members",
                                                         body="Remove any number of roles from all members in your system",
                                                         additional="Please enter a role or multiple roles separated by commas below: (Timesout in 300 seconds)",
                                                         callback=self.remove_role_from_all_members)

            menu = reactMenu.Menu(name="Remove Roles",
                                  body="Please select an option below by sending a message with the number.",
                                  pages=[remove_roles, remove_roles_to_all_members])

            await menu.run(self.ctx)

        async def ask_to_go_back(self):
            back_to_menu = reactMenu.Page("bool", name=f"Would you like to go back to the menu?")
            await back_to_menu.run(self.bot, self.ctx)
            if back_to_menu.response:
                await self.run()

        async def remove_role_from_all_members(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: discord.Message):
            role_text = response.content
            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text, self.allowable_roles)
            if roles is None:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            members = await db.get_members_by_discord_account(self.db, ctx.author.id)  # ctx.author.id)
            if members is None or len(members) == 0:

                await ctx.send(
                    f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
                return

            for role in roles.good_roles:
                for member in members:
                    await db.remove_role_from_member(self.db, ctx.guild.id, member['pk_mid'], role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed()
            embed = discord.Embed(title=f"Removed {len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles from all members:")

            if len(roles.good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
                embed.add_field(name="Successfully removed:", value=good_roles_msg)

            if len(roles.bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
                embed.add_field(
                    name="Could not find and remove the following (check spelling and capitalization)",
                    value=bad_roles_msg)

            if len(roles.disallowed_roles) > 0:
                disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])
                embed.add_field(name="These roles are not allowed to be removed by ARC. "
                                     "(They *may* still be able to be removed from your account by this servers standard role setting bot or staff):",
                                value=disallowed_roles_msg)

            await ctx.send(embed=embed)

            ask_to_remove_more = reactMenu.Page("bool",
                                             name=f"Would you like to remove more roles from all system members?\n",
                                             # body="Click ✅ or ❌",
                                             callback=self.remove_role_from_all_members_cont)
            await ask_to_remove_more.run(client, ctx)

        async def remove_role_from_all_members_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                                    response: bool):
            if response:
                remove_another_role = reactMenu.Page("str", name="Remove another role",
                                                     body="Please enter a role.",
                                                     callback=self.remove_role_from_all_members)
                await remove_another_role.run(client, ctx)
            else:
                # await ctx.send("Finished removing roles!")
                await self.ask_to_go_back()

        # --- Remove Roles to member prompts --- #
        async def select_member_for_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                         response: discord.Message):

            member = await db.get_member_fuzzy(self.db, ctx.author.id, response.content)
            if member is None:
                await ctx.send(f"Could not find {response.content} in your system. Try using the 5 character Plural Kit ID.")
            else:
                self.member = member
                remove_roles = reactMenu.Page("str",
                                              name=f"Remove roles from member {member['member_name']}",
                                              body="Please enter a role or multiple roles separated by commas below: (Timesout in 300 seconds)",
                                              callback=self.remove_role,
                                              timeout=300)
                await remove_roles.run(self.bot, ctx)

        async def remove_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                              response: discord.Message):

            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return

            role_text = response.content
            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text, self.allowable_roles)
            if roles is None:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            for role in roles.good_roles:
                await db.remove_role_from_member(self.db, ctx.guild.id, self.member['pk_mid'], role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed(title=f"Removed {len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles from {self.member['member_name']}:")

            if len(roles.good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
                embed.add_field(name="Successfully removed:", value=good_roles_msg)

            if len(roles.bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
                embed.add_field(
                    name="Could not find and remove the following (check spelling and capitalization):",
                    value=bad_roles_msg)

            if len(roles.disallowed_roles) > 0:
                disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])
                embed.add_field(name="These roles are not allowed to be removed by ARC. "
                                     "(They *may* still be able to be removed from your account by this servers standard role setting bot or staff):", value=disallowed_roles_msg)

            await ctx.send(embed=embed)

            ask_to_remove_more = reactMenu.Page("bool",
                                             name=f"Would you like to remove another role from {self.member['member_name']}?",
                                             # body="Click ✅ or ❌",
                                             callback=self.remove_role_cont)
            await ask_to_remove_more.run(client, ctx)


        async def remove_role_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                   response: bool):
            if response:
                remove_another_role = reactMenu.Page("str", name="Remove another role",
                                                  body="Please enter a role.",
                                                  callback=self.remove_role)
                await remove_another_role.run(client, ctx)
            else:
                # await ctx.send("Finished removing roles!")
                await self.ask_to_go_back()

    @is_authorized_guild()
    @commands.guild_only()
    @commands.command(aliases=["add_roles", "add"], brief="Add roles from system members & See list of roles.",
                      description="Lets you add roles to one or multiple system members.\n"
                                  "Also lets you see the list of assignable roles.")
    async def add_role(self, ctx: commands.Context):
        settings = self.CSVAddRolesMenuHandler(self.bot, ctx)
        await settings.run()

    class CSVAddRolesMenuHandler:

        def __init__(self, bot, ctx):
            self.bot = bot
            self.db = bot.db
            self.ctx = ctx
            self.member = None
            self.role = None

            self.allowable_roles: Optional[db.AllowableRoles] = None

        async def run(self):
            self.allowable_roles = await db.get_allowable_roles(self.db, self.ctx.guild.id)
            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return

            list_allowable_roles = reactMenu.Page("custom", name="List roles",
                                                  body="List all Auto changeable roles.",
                                                  callback=self.list_allowable_roles)

            add_roles = reactMenu.Page("str", name="Add roles to a member",
                                       body="Add any number of roles to one system member",
                                       additional="Please enter a System Member below:",
                                       callback=self.select_member_for_role)

            add_roles_from_discord_user = reactMenu.Page("str", name="Apply current roles to a member",
                                       body="Makes the selected member have the roles currently on your discord account.",
                                       additional="Please enter a System Member below:",
                                       callback=self.select_member_for_current_roles)

            add_roles_to_all_members = reactMenu.Page("str",
                                     name="Add roles to all your members",
                                     body="Add any number of roles to all members in your system",
                                     additional="Please enter a role or multiple roles separated by commas below: (Timesout in 300 seconds)",
                                     callback=self.add_role_to_all_members,
                                                      timeout=300)

            menu = reactMenu.Menu(name="Add Role",
                                  body="Please select an option below by sending a message with the number",
                                  pages=[list_allowable_roles, add_roles, add_roles_to_all_members])#, add_roles_from_discord_user])

            await menu.run(self.ctx)

        async def ask_to_go_back(self):
            back_to_menu = reactMenu.Page("bool", name=f"Would you like to go back to the menu?")
            await back_to_menu.run(self.bot, self.ctx)
            if back_to_menu.response:
                await self.run()

        async def list_allowable_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context):
            """Sends embed with all the allowable roles."""

            embed = discord.Embed()
            embed.set_author(name=f"Auto changeable roles")

            if self.allowable_roles is not None:
                roles_msg = ", ".join([f"<@&{role_id}>" for role_id in self.allowable_roles.role_ids])
            else:
                roles_msg = "No roles are configured!"

            embed.description = roles_msg
            await ctx.send(embed=embed)
            await self.ask_to_go_back()


        async def add_role_to_all_members(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                          response: discord.Message):

            # await page.remove()
            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return


            ask_to_add_more = reactMenu.Page("bool",
                                             name=f"Would you like to add another role to all system members?",
                                             # body="Click ✅ or ❌",
                                             callback=self.add_role_to_all_members_cont)
            role_text = response.content
            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text, self.allowable_roles)
            if roles is None:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            members = await db.get_members_by_discord_account(self.db, ctx.author.id)  # ctx.author.id)
            if members is None or len(members) == 0:
                await ctx.send(
                    f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
                return

            for role in roles.good_roles:
                for member in members:
                    await db.add_role_to_member(self.db, ctx.guild.id, member['pk_mid'], member['pk_sid'], role.id)

                # await ctx.send(f"Added **{role.name}** to all registered system members!")

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed(
                title=f"Added {len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles to all members:")

            if len(roles.good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
                embed.add_field(name="Successfully added:", value=good_roles_msg)

            if len(roles.bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
                embed.add_field(
                    name="Could not find and add the following (check spelling and capitalization):",
                    value=bad_roles_msg)

            if len(roles.disallowed_roles) > 0:
                disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])
                embed.add_field(name="These roles are not allowed to be set by ARC. "
                                     "(They *may* still be able to be statically applied to your account by this servers standard role setting bot or staff):", value=disallowed_roles_msg)

            await ctx.send(embed=embed)

            await ask_to_add_more.run(client, ctx)

        async def add_role_to_all_members_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: bool):
            # await page.remove()
            if response:
                add_another_role = reactMenu.Page("str", name="Add another role",
                                                  body="Please enter a role.",
                                                  callback=self.add_role_to_all_members)
                await add_another_role.run(client, ctx)
            else:
                # await ctx.send("Finished adding roles!")
                await self.ask_to_go_back()


        async def select_member_for_current_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                                  response: discord.Message):

            member = await db.get_member_fuzzy(self.db, ctx.author.id, response.content)
            if member is None:
                await ctx.send(f"Could not find {response.content} in your system. Try using the 5 character Plural Kit ID.")
            else:
                self.member = member

                verify_prompt = reactMenu.Page("bool",
                                           name=f"Are you sure you want to set all roles that are currently on your discord account onto {member['member_name']}? ",
                                           # body="Click ✅ or ❌",
                                           callback=self.verify_set_all_roles)
                await verify_prompt.run(self.bot, ctx)

        async def verify_set_all_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                       response: bool):
            if response:
                # Todo: Implement
                await ctx.send(f"Setting all roles")
            else:
                await ctx.send(f"Canceled!")

        # --- Add Roles to member prompts --- #
        async def select_member_for_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context, response: discord.Message):

            member = await db.get_member_fuzzy(self.db, ctx.author.id, response.content)
            if member is None:
                await ctx.send(f"Could not find {response.content} in your system. Try using the 5 character Plural Kit ID")
            else:
                self.member = member
                add_roles = reactMenu.Page("str",
                                           name=f"Add roles to member {member['member_name']}",
                                           body="Please enter a role or multiple roles separated by commas below: (Timesout in 300 seconds)",
                                           callback=self.add_role,
                                           timeout=300)
                await add_roles.run(self.bot, ctx)

        async def add_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                           response: discord.Message):

            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return

            ask_to_add_more = reactMenu.Page("bool",
                                             name=f"Would you like to add another role to {self.member['member_name']}?",
                                             # body="Click ✅ or ❌",
                                             callback=self.add_role_cont)

            role_text = response.content
            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text, self.allowable_roles)
            if roles is None:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            for role in roles.good_roles:
                await db.add_role_to_member(self.db, ctx.guild.id, self.member['pk_mid'], self.member['pk_sid'], role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed(
                title=f"{len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles added to {self.member['member_name']}:")

            if len(roles.good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
                embed.add_field(name="Successfully added:", value=good_roles_msg)

            if len(roles.bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
                embed.add_field(
                    name="Could not find and add the following (check spelling and capitalization):",
                    value=bad_roles_msg)

            if len(roles.disallowed_roles) > 0:
                disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])
                embed.add_field(name="These roles are not allowed to be set by ARC. "
                                     "(They *may* still be able to be statically applied to your account by this servers standard role setting bot or staff):", value=disallowed_roles_msg)

            await ctx.send(embed=embed)

            await ask_to_add_more.run(client, ctx)

        async def add_role_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                            response: bool):
            if response:
                add_another_role = reactMenu.Page("str", name="Add another role",
                                                  body="Please enter a role.",
                                                  callback=self.add_role)
                await add_another_role.run(client, ctx)
            else:
                # await ctx.send("Finished adding roles!")
                await self.ask_to_go_back()

    @commands.is_owner()
    @commands.command(hidden=True)
    async def debug_settings(self, ctx: commands.Context, member_id: int):

        user_settings = await db.get_user_settings_from_discord_id(self.db, member_id, authorized_guilds[0])
        if not user_settings:
            await ctx.send(f"{member_id} has no settings.")
            return

        auto_name = "On" if user_settings.name_change else "Off"
        auto_role = "On" if user_settings.role_change else "Off"
        system_tag_override = user_settings.system_tag_override or "Not Set"

        msg = f"Auto name: {auto_name}, Auto Roles: {auto_role}, tag override: {system_tag_override}"
        await ctx.send(msg)

    @is_authorized_guild()
    @commands.guild_only()
    @commands.command(aliases=["config", "setting", "user_setting", "user_settings"],
                      brief="Change user settings such as Auto Name Change and Auto Role Change")
    async def settings(self, ctx: commands.Context):
        settings = self.UserSettingsRolesMenuHandler(self.bot, ctx)
        await settings.run()

    class UserSettingsRolesMenuHandler:
        """
        Settings to add:
            System tag?
            Set roles for all fronters or first fronter.
            Update all accounts, just the active account, or a list of accounts?
        """

        def __init__(self, bot, ctx):
            self.bot = bot
            self.db = bot.db
            self.ctx = ctx

            self.current_user_settings: Optional[db.UserSettings] = None

        async def run(self):
            self.current_user_settings = await db.get_user_settings_from_discord_id(self.db, self.ctx.author.id, self.ctx.guild.id)
            if self.current_user_settings is None:
                await self.ctx.send("You do not seem to be registered with this bot. "
                                    f"Please use reg_sys to `{self.bot.command_prefix}register` a new account or update your existing account")
                return

            auto_name = "On" if self.current_user_settings.name_change else "Off"
            auto_role = "On" if self.current_user_settings.role_change else "Off"
            system_tag_override = self.current_user_settings.system_tag_override or "Not Set"

            name_change = reactMenu.Page("bool", name="Toggle Auto Name Change",
                                         body=f"Toggles the automatic name change functionality. Currently **{auto_name}**",
                                         additional="Click ✅ to toggle automatic name changes, or click ❌ to cancel",
                                         callback=self.name_change)

            role_change = reactMenu.Page("Bool",
                                         name="Toggle Auto Role Change",
                                         body=f"Toggles the automatic role change functionality. Currently **{auto_role}**",
                                         additional="Click ✅ to toggle automatic role changes, or click ❌ to cancel",
                                         callback=self.role_change)

            # set_system_tag_override = reactMenu.Page("Bool",
            #                              name="Set/Remove an alternative system tag",
            #                              body=f"Toggles the automatic role change functionality. Currently **{auto_role}**",
            #                              additional="Click ✅ to toggle automatic role changes, or click ❌ to cancel",
            #                              callback=self.set_system_tag_override)

            menu = reactMenu.Menu(name="Auto Role User Settings",
                                  body="Please select an option below by sending a message with the number",
                                  pages=[name_change, role_change]) #, set_system_tag_override])

            await menu.run(self.ctx)

        async def name_change(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                              response: bool):

            if response:
                new_name_setting = False if self.current_user_settings.name_change else True
                new_name_setting_text = "Off" if self.current_user_settings.name_change else "On"

                await db.update_user_setting(self.db, self.current_user_settings.pk_sid, ctx.guild.id, name_change=new_name_setting,
                                             role_change=self.current_user_settings.role_change)
                await self.ctx.send(f"Automatic name changes are now **{new_name_setting_text}**")
            else:
                await self.ctx.send(f"Canceled!")

        async def role_change(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                              response: bool):

            if response:
                new_role_setting = False if self.current_user_settings.role_change else True
                new_role_setting_text = "Off" if self.current_user_settings.role_change else "On"

                await db.update_user_setting(self.db, self.current_user_settings.pk_sid, ctx.guild.id, name_change=self.current_user_settings.name_change,
                                             role_change=new_role_setting)
                await self.ctx.send(f"Automatic role changes are now **{new_role_setting_text}**")
            else:
                await self.ctx.send(f"Canceled!")


    @is_authorized_guild()
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command(aliases=["admin_config", "admin_setting", "guild_setting", "guild_settings", "guild_config"],
                      brief="Set guild settings, such as which roles are assignable.",
                      description="Lets you set which roles are assignable by the users and in the future more.")
    async def admin_settings(self, ctx: commands.Context):
        settings = self.AdminSettingsRolesMenuHandler(self.bot, ctx)
        await settings.run()

    class AdminSettingsRolesMenuHandler:

        def __init__(self, bot, ctx):
            self.bot = bot
            self.db = bot.db
            self.ctx = ctx

            self.allowable_roles: Optional[db.AllowableRoles] = None

        async def run(self):
            self.allowable_roles = await db.get_allowable_roles(self.db, self.ctx.guild.id)

            list_allowable_roles = reactMenu.Page(page_type="custom", name="List usable roles.",
                                                  body="Displays a list of all the roles users are allowed to use",
                                                  callback=self.list_allowable_roles)

            add_allowable_roles = reactMenu.Page(page_type="str",
                                                 name="Add more roles",
                                                 body="Add more roles that users are allowed to set",
                                                 additional="Please enter a role or multiple roles separated by commas below: (Times out in 300 seconds)",
                                                 callback=self.add_allowable_roles, timeout=300)

            remove_allowable_roles = reactMenu.Page(page_type="str",
                                                    name="Remove roles",
                                                    body="Remove roles from that which users are allowed to set",
                                                    additional="Please enter a role or multiple roles separated by commas below: (Times out in 300 seconds)",
                                                    callback=self.remove_allowable_roles, timeout=300)

            menu = reactMenu.Menu(name="Auto Role Admin Settings",
                                  body="Please select an option below by sending a message with the number",
                                  pages=[list_allowable_roles, add_allowable_roles, remove_allowable_roles])

            await menu.run(self.ctx)

        async def list_allowable_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context):
            """Sends embed with all the allowable roles."""

            embed = discord.Embed()
            embed.set_author(name=f"Roles that users may use.")

            if self.allowable_roles is not None:
                roles_msg = ", ".join([f"<@&{role_id}>" for role_id in self.allowable_roles.role_ids])
            else:
                roles_msg = "No roles are configured!"

            embed.description = roles_msg
            await ctx.send(embed=embed)

        async def add_allowable_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: discord.Message):
            """Add more roles to the list of usable roles"""

            role_text = response.content

            # csv_regex = "(.+?)(?:,|$)"
            # if len(role_text) == 0:
            #     await ctx.send("ERROR!!! Could not parse roles!")
            #     return
            #
            # # Make sure that the string ends in a comma for proper regex detection
            # if role_text[-1] != ",":
            #     role_text += ","
            # log.info(role_text)
            # raw_roles = re.findall(csv_regex, role_text)
            # if len(raw_roles) == 0:
            #     await ctx.send("ERROR!!! Could not parse roles!")
            #     return
            # log.info(raw_roles)
            # good_roles = []
            # bad_roles = []
            # for raw_role in raw_roles:
            #     raw_role: str
            #     try:
            #         # add identifiable roles to the good list
            #         # Todo: Try to match up Snowflake like raw roles to the roles in self.allowable_roles and bypass the RoleConverter on success.
            #         role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
            #         good_roles.append(role)
            #     except commands.errors.BadArgument:
            #         # Role could not be found. Add to bad list.
            #         bad_roles.append(raw_role)

            # Add all the good roles to the DB

            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text)
            if roles is None:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            for role in roles.good_roles:
                await db.add_allowable_role(self.db, ctx.guild.id, role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed(title=f"{len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles)} roles added to the allowed list:")

            if len(roles.good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
                embed.add_field(name="Successfully added:", value=good_roles_msg)

            if len(roles.bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
                embed.add_field(name="Could not find and add the following (check spelling and capitalization):", value=bad_roles_msg)

            await ctx.send(embed=embed)

        async def remove_allowable_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: discord.Message):
            """Remove roles from the list of usable roles"""

            role_text = response.content
            #
            # csv_regex = "(.+?)(?:,|$)"
            # if len(role_text) == 0:
            #     await ctx.send("ERROR!!! Could not parse roles!")
            #     return
            #
            # # Make sure that the string ends in a comma for proper regex detection
            # if role_text[-1] != ",":
            #     role_text += ","
            #
            # raw_roles = re.findall(csv_regex, role_text)
            # if len(raw_roles) == 0:
            #     await ctx.send("ERROR!!! Could not parse roles!")
            #     return
            #
            # good_roles = []
            # bad_roles = []
            # for raw_role in raw_roles:
            #     try:
            #         # add identifiable roles to the good list
            #         # Todo: Try to match up Snowflake like raw roles to the roles in self.allowable_roles and bypass the RoleConverter on success.
            #         role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
            #         good_roles.append(role)
            #     except commands.errors.BadArgument:
            #         # Role could not be found. Add to bad list.
            #         bad_roles.append(raw_role)

            # Remove all the good roles from the DB
            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text)
            for role in roles.good_roles:
                await db.remove_allowable_role(self.db, ctx.guild.id, role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed(
                title=f"{len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles)} roles removed from the allowed list:")

            if len(roles.good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
                embed.add_field(name="Successfully removed:", value=good_roles_msg)

            if len(roles.bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
                embed.add_field(name="Could not find and remove the following (check spelling and capitalization):", value=bad_roles_msg)

            await ctx.send(embed=embed)

    @is_authorized_guild()
    @commands.guild_only()
    @commands.command(name="register", aliases=["reg"],
                      brief="<- Start here! Register and link up your PK account.",
                      description="Lets you register with this bot and link up your PK account.")
    async def register(self, ctx: commands.Context):
        """Allows you to link your PK account to this bot."""
        # TODO: Add ability to update current registration (Mainly discord accounts)

        await ctx.send(f"To register your Plural Kit account, please use the command `pk;s` to have Plural Kit send your system card")

        def check_for_pk_response(m: discord.Message):
            # log.info(f"Got Message: {m}, Embeds: {len(m.embeds)}")
            return m.author.id == self.pk_id and len(m.embeds) == 1

        try:
            pk_msg: discord.Message = await self.bot.wait_for('message', timeout=30.0, check=check_for_pk_response)
        except asyncio.TimeoutError:
            await ctx.send("Command timed out!")
            return None

        await self.info(f"Got PK Embed: {pk_msg.embeds}")
        pk_info = self.parse_system_card(pk_msg.embeds[0])
        system_id = pk_info['system_id']

        # Verify that this card belongs to the system that used the register command.
        verification_system = await self.get_system_by_discord_id(ctx.author.id)
        if verification_system.hid != system_id:
            await ctx.send("Error!!! I seem to have gotten mixed up. Someone else may have used pk;s before you did! Please try to use the register again.")
            return
        log.info(f"{system_id}")
        system = await self.get_system(system_id)
        await self.info(f"{system}")
        try:
            members = await self.get_system_members(system_id)
            log.info(f"{members}")
        except MemberListHidden:
            # await ctx.send(f"Your Plural Kit setting require that I get additional information for in order to operate properly.\n"
            #                f"Sending you a DM for further configuration.")
            # await self.prompt_for_pk_token(ctx)
            await ctx.send("Unfortunately this bot does not yet support the new Plural Kit privacy settings.\n")
            return

        current_fronters = await self.get_fronters(system_id)
        await self.info(f"{current_fronters}")
        await self.info(f"adding new system to DB: {system.name} ({system.hid})")
        await db.add_new_system(self.db, system_id, system.name, None, system.tag, None)

        # Add default user settings
        await db.update_user_setting(self.db, system_id, ctx.guild.id, name_change=False, role_change=False)

        await self.info(f"adding linked discord accounts DB: {system.name}({system.hid})")

        for account in pk_info['discord_accounts']:
            await db.add_linked_discord_account(self.db, system_id, int(account))

        for member in members:
            fronting = True if member in current_fronters.members else False
            await db.add_new_member(self.db, system_id, member.hid, member.name, fronting=fronting)
        # await self.info(f"adding the following members to the db: {members}")
        await ctx.invoke(self.getting_started)
        await ctx.send(f"Your system and {len(members)} members of your system have been registered successfully!\n"
                       f"Hidden members are not yet supported.\n\n"
                       f"Auto name and role changing is currently **Off**. You may change these settings by using the **{self.bot.command_prefix}settings** command\n")


        # await self.getting_started(ctx)


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

    async def get_fronters(self, pk_sys_id: str) -> pk.Fronters:
        try:
            async with aiohttp.ClientSession() as session:
                await self.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}/fronters'}")
                fronters = await pk.Fronters.get_by_hid(session, pk_sys_id)
                return fronters
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    async def get_system(self, pk_sys_id: str) -> pk.System:
        try:
            async with aiohttp.ClientSession() as session:
                await self.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}'}")
                system = await pk.System.get_by_hid(session, pk_sys_id)
                return system
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    async def get_system_by_discord_id(self, discord_user_id: int) -> pk.System:
        try:
            async with aiohttp.ClientSession() as session:
                await self.warning(f"Scraping: {f'https://api.pluralkit.me/a/{discord_user_id}'}")
                system = await pk.System.get_by_account(session, discord_user_id)
                return system
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    async def get_system_members(self, pk_sys_id: str) -> pk.Members:
        try:
            async with aiohttp.ClientSession() as session:
                await self.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}/members'}")
                try:
                    members = await pk.Members.get_by_hid(session, pk_sys_id)
                    return members
                except pk.NeedsAuthorization:
                    raise MemberListHidden
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    async def info(self, msg):
        """Info Logger"""
        func = inspect.currentframe().f_back.f_code
        log.info(f"[{func.co_name}:{func.co_firstlineno}] {msg}")
        await self.bot.dLog.info(msg, header=f"[{__name__}]")

    async def warning(self, msg):
        # log.warning(msg)
        func = inspect.currentframe().f_back.f_code
        log.info(f"[{func.co_name}:{func.co_firstlineno}] {msg}")
        await self.bot.dLog.warning(msg, header=f"[{__name__}]")


def setup(bot):
    bot.add_cog(AutoRoleChanger(bot))


class UnableToParseSystemCard(Exception):
    pass


class MemberListHidden(Exception):
    pass


