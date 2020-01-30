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

# import db as sqliteDB
import postgresDB as db

import cogs.utils.pluralKit as pk
import cogs.utils.reactMenu as reactMenu
from cogs.utils.paginator import FieldPages
from cogs.utils.autoRoleUtils import parse_csv_roles, ParsedRoles, parse_csv_members, ParsedMembers, get_system_role, GuildSettings
import cogs.utils.autoRoleEmbeds as arcEmbeds

from cogs.utils.dLogger import dLogger
from botExceptions import UnsupportedGuild

if TYPE_CHECKING:
    from discordBot import PNBot

log = logging.getLogger(__name__)
authorized_guilds = None

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

        if authorized_guilds is not None and ctx.guild.id not in authorized_guilds:
            raise UnsupportedGuild()

        return True

    return commands.check(predicate)


class AutoRoleChanger(commands.Cog):
    def __init__(self, bot: 'PNBot'):
        self.pk_id = 466378653216014359
        self.pool = bot.pool
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        author: Union[discord.Member, discord.User] = message.author
        if not author.bot:
            msg = message.content.lower().strip()
            try:
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
            except PluralKitPrivacyError:
                pass  # We can't do much in this case... so just keep going...


    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):

        #Add the new guild to the DB.
        await db.add_guild_setting(self.pool, guild.id, True, True, None, False, False)


    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await db.remove_guild_setting(self.pool, guild.id)

    # async def update_member(self, discord_member: discord.Member = None, ctx: Optional[commands.Context] = None, message: Optional[discord.Message] = None):
    #     if ctx is not None:
    #         discord_member: discord.Member = ctx.author
    #         message: discord.Message = ctx.message
    #
    #     if message is not None:
    #         discord_member: discord.Member = message.author
    #
    #     pk_info = await db.get_system_id_from_linked_account(self.pool, message.author.id)
    #     if pk_info is not None:
    #         pk_id = pk_info['pk_system_id']
    #         fronters = await self.get_fronters(pk_id)
    #         if fronters is not None:
    #             log.info(f"Got fronters: {fronters}")
    #             first_fronter = fronters.members[0]
    #
    #             proto_roles = await db.get_roles_for_member_by_guild(self.pool, first_fronter.hid, message.guild.id)
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

    # async def get_new_roles_and_name_for_all_guilds(self, current_fronters: pk.Fronters, discord_user_id):
    #
    #     settings = await db.get_all_user_settings_from_discord_id(self.pool, discord_user_id)
    #
    #     all_roles = {}
    #     new_name = current_fronters.members[0].proxied_name if len(current_fronters.members) > 0 else None
    #     for setting in settings:
    #         roles = []
    #         for fronter in current_fronters.members:
    #             new_roles = await db.get_roles_for_member_by_guild(self.pool, fronter.hid, setting.guild_id)
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


    async def update_system_members(self, force_member_update: bool = False, force_discord_update: bool = False, db_expiration_age: int = 86400,
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
            stale_members = await db.get_members_by_discord_account_if_ood(self.pool, discord_member.id, db_expiration_age)
            if stale_members is None:
                # It's not soon enough to try to do a full update. Bail for now.
                return
            await self.info(f"DB info is STALE ({round((datetime.utcnow().timestamp() - stale_members[0]['last_update'])/60)} min) for {stale_members[0]['member_name']}")
            system_id = stale_members[0]['pk_sid']

        # We need to get the stored fronters from the DB at this point.
        # This is needed to determine if we need to call the Discord API later.
        stale_fronters = await db.get_fronting_members_by_discord_account(self.pool, discord_member.id)

        # Try to get the system id from the fronters stored in the DB
        # Stored fronters will be none if there is no one fronting or if the system does not exist in the DB.
        if stale_fronters is not None and system_id is None:
            system_id = stale_fronters[0].sid

        # If we STILL don't have a system ID, pull it from the DB directly.
        # (all the previous attempts DB calls still needed to happen, so by trying at each stage we can potentially save a DB call.)
        if system_id is None:
            sys_info = await db.get_system_id_by_discord_account(self.pool, discord_member.id)
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
            await self.info(f"User {discord_member.display_name} has PK permissions enabled! Can not proceed.")
            if stale_members is not None:
                # 'Fake" an update so we don't hammer the PK API
                for stale_member in stale_members:
                    await db.fake_member_update(self.pool, stale_member['pk_mid'])
            raise MemberListHidden

        updated_fronters = await self.get_fronters(system_id)  # TODO: Ask alyssa & astrid about using GET /s/<id>/switches[?before=] first.

        # Update the DB with the new information.
        # TODO: Compare with the stale information and only update what has changed.
        for update_member in updated_members:
            # TODO: When we stop updating all members, we will need to maybe set all members to not fronting THEN set the members that are frontring to fronting.
            #  Alternatively, we could have a fronting table... Then we could just delete the members from the table, and add the current ones....
            fronting = True if update_member in updated_fronters.members else False
            await db.update_member(self.pool, system_id, update_member.hid, update_member.name, fronting=fronting)
        await self.info(f"Updated members for {discord_member.name}")

        # TODO: The below code May be broken and 'fake updating' members when it should not. Fix.
        # Clean up the DB and remove and remove any members that no longer exist (or are private at this point)
        # We are going to go off the stale_member data as this doesn't need to happen EVERY time.
        if stale_members is not None:
            for stale_member in stale_members:
                found = False
                for updated_member in updated_members:
                    if stale_member['pk_mid'] == updated_member.hid:
                        found = True
                        break
                if not found:
                    # await self.warning(f"DELETING member in {discord_member.name}'s system: {stale_member}")
                    # await db.delete_member(self.pool, stale_member['pk_sid'], stale_member['pk_mid'])
                    await self.warning(f"Non-updating Stale member in {discord_member.name}'s system: {stale_member}. Pushing next update forward 24H")
                    await db.fake_member_update(self.pool, stale_member['pk_mid'])

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
        #             await db.delete_member(self.pool, stale_member['pk_sid'], stale_member['pk_mid'])

        # Put the stale_fronters into a better format for logging...
        log_stale_fronters = [fronter.hid for fronter in stale_fronters] if stale_fronters is not None else None
        if force_discord_update or stale_fronters is None or stale_fronters != updated_fronters.members:

            if stale_fronters is None or stale_fronters != updated_fronters.members:
                await self.info(f"Fronters changed!: Prev: {log_stale_fronters}, \n\nCur: {updated_fronters}")
            else:
                await self.info(f"Update Foreced!!!")

            await self.autochange_discord_user_across_discord(discord_member, system_id, updated_fronters)
            #
            # roles = []
            # for fronter in updated_fronters.members:  # FIXME: Chane from 1 to 0                             V
            #     new_roles = await db.get_roles_for_member_by_guild(self.pool, fronter.hid, authorized_guilds[1])  # Force using only authorised guild for now.# discord_member.guild.id)
            #     if new_roles is not None:
            #         new_roles_ids = [discord.Object(id=role['role_id']) for role in new_roles]
            #         roles.extend(new_roles_ids)
            #
            # await self.autochange_discord_user(discord_member, system_id, roles, updated_fronters)
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
        await db.update_system_by_pk_sid(self.pool, updated_system.hid, updated_system.name, updated_system.tag)

        return updated_system


    class UserRoles(NamedTuple):
        guild_id: int
        roles: List[discord.Object]

    async def get_new_roles(self, fronters: pk.Fronters, guild_id: int) -> Optional[UserRoles]:

        if fronters is None:
            return None

        roles = []
        for fronter in fronters.members:
            new_roles = await db.get_roles_for_member_by_guild(self.pool, fronter.hid, guild_id)
            if new_roles is not None:
                new_roles_ids = [discord.Object(id=role['role_id']) for role in new_roles]
                roles.extend(new_roles_ids)

        user_roles = self.UserRoles(guild_id=guild_id, roles=roles)
        return user_roles

    # async def get_new_roles_for_all_guilds(self, fronters: pk.Fronters) -> Optional[List[UserRoles]]:
    #
    #     if fronters is None:
    #         return None
    #
    #     roles = []
    #     for fronter in fronters.members:
    #         roles_for_all_guilds = await db.get_roles_for_member(self.pool, fronter.hid)
    #
    #         for role

    async def autochange_discord_user_across_discord(self, discord_member: Union[discord.Member, discord.User],
                                                     pk_system_id: str, updated_fronters: Optional[pk.Fronters]):

        updated_system = None
        new_name = None
        discord_member_id = discord_member.id
        triggered_guild: discord.Guild = discord_member.guild  # This is the guild the trigger action took place in
        all_user_settings = await db.get_all_user_settings_from_discord_id(self.pool, discord_member.id)

        if all_user_settings is not None:

            if updated_system is None:  # TODO: Only update system if needed.
                updated_system = await self.update_system(system_id=pk_system_id)

            for user_settings_in_guild in all_user_settings:
                system_role = None
                current_guild: discord.Guild = self.bot.get_guild(user_settings_in_guild.guild_id)
                if current_guild is None:
                    continue  # Couldn't get guild... Skip
                current_discord_user:discord.Member = current_guild.get_member(discord_member_id)
                if current_discord_user is None:
                    continue  # Couldn't get member... Skip

                guild_settings = GuildSettings(** await db.get_guild_settings(self.pool, current_guild.id))


                if guild_settings is not None and guild_settings.custom_roles:
                    # Get the current fronter, or None if now one is fronting
                    current_fronter = updated_fronters.members[0] if len(updated_fronters.members) > 0 else None

                    # Get the current fronters favorite color or None if no one is fronting.
                    current_fronters_color = current_fronter.color if current_fronter else None
                    current_fronter_name = current_fronter.name if current_fronter else None

                    # Try to get the system name for the role, use the fronters name as a back up, and system ID as a final resort.
                    system_role_name = updated_system.name or current_fronter_name or updated_system.hid

                    # Get the system role (Or None if they have it disabled)
                    system_role = await get_system_role(self.pool, guild=current_guild, system_role_id=user_settings_in_guild.system_role,
                                                        system_role_enabled=user_settings_in_guild.system_role_enabled,
                                                        system_id=user_settings_in_guild.pk_sid, system_name=system_role_name,
                                                        fronters_favorite_color=current_fronters_color)

                    await current_discord_user.add_roles(system_role)  # Todo: Maybe add this into get_system_role? Also check if they have it first?

                if user_settings_in_guild.role_change:
                    new_roles = await self.get_new_roles(updated_fronters, user_settings_in_guild.guild_id)

                    await self.info(f"Setting {current_discord_user.display_name}'s {len(new_roles)} role(s)")

                    guild_allowed_auto_roles = await db.get_allowable_roles(self.pool, user_settings_in_guild.guild_id)  # discord_member.guild.id)

                    # TODO: I'm fairly sure this is the case already, but make sure that this removes disallowed roles from 'new_roles'
                    # Get the auto roles to set and get the roles we must keep
                    allowed_new_roles = guild_allowed_auto_roles.allowed_intersection(new_roles.roles) if new_roles else []
                    old_roles_to_keep = guild_allowed_auto_roles.disallowed_intersection(current_discord_user.roles)

                    # Use a set to ensure there are no duplicates.
                    account_role_to_set = [system_role] if system_role is not None else []
                    roles_to_set = set(allowed_new_roles + old_roles_to_keep + account_role_to_set)
                    await self.info(f"Applying the following roles: {roles_to_set}")

                    try:
                        await current_discord_user.edit(roles=set(roles_to_set))
                    except discord.errors.Forbidden:
                        await self.info(f"Could not set roles: {roles_to_set} on {current_discord_user.display_name}")

                if user_settings_in_guild.name_change and len(updated_fronters.members) > 0:  # TODO: Add option to set system name as nickname when no one is fronting.

                    system_tag = updated_system.tag
                    max_nickname_length = 32
                    if system_tag:
                        system_tag_length = len(system_tag) + 1  # + 1 due to Space between tag and name.
                        shortened_member_name = updated_fronters.members[0].proxied_name[
                                                :max_nickname_length - system_tag_length]
                        new_name = f"{shortened_member_name} {system_tag}" if system_tag else updated_fronters.members[0].proxied_name[:max_nickname_length]
                    else:
                        new_name = updated_fronters.members[0].proxied_name[:max_nickname_length]

                    await self.info(f"Changing {discord_member.display_name} name to {new_name}'s name")
                    try:
                        await current_discord_user.edit(nick=new_name)
                    except discord.errors.Forbidden:
                        await self.info(f"Forbidden! Could not change {discord_member.display_name}'s name")

    async def autochange_discord_user(self, discord_member: Union[discord.Member, discord.User], pk_system_id: str, new_roles: List[Union[discord.Role, discord.Object]], updated_fronters: Optional[pk.Fronters]):
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

        user_settings = await db.get_user_settings_from_discord_id(self.pool, discord_member.id, guild.id)

        if user_settings is not None:

            if user_settings.role_change:
                await self.info(f"Setting {discord_member.display_name}'s {len(new_roles)} role(s)")

                guild_allowed_auto_roles = await db.get_allowable_roles(self.pool, guild.id)  # discord_member.guild.id)

                # TODO: I'm fairly sure this is the case already, but make sure that this removes disallowed roles from 'new_roles'
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

                # if user_settings.system_tag_override is None:
                updated_system = await self.update_system(system_id=pk_system_id)
                system_tag = updated_system.tag
                # else:
                #     system_tag = user_settings.system_tag_override

                max_nickname_length = 32
                if system_tag:
                    system_tag_length = len(system_tag) + 1  # + 1 due to Space between tag and name.
                    shortened_member_name = updated_fronters.members[0].proxied_name[:max_nickname_length-system_tag_length]
                    new_name = f"{shortened_member_name} {system_tag}" if system_tag else updated_fronters.members[0].proxied_name[:max_nickname_length]
                else:
                    new_name = updated_fronters.members[0].proxied_name[:max_nickname_length]

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
            try:
                await self.update_system_members(discord_member=after, db_expiration_age=60 * 1)
            except PluralKitPrivacyError:
                pass  # Not much that can be done...

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
            f"Auto Role Changer (ARC) now works across any server you add it to!",
            f"Just remember, the bot does obviously have to be configured per server.",
            f"As before, you can still invite ARC into your server in order to let it detect your switches when the appropriate actions are done in other servers. No configurations are necessary for this, just invite it and go!",
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

    # ----- Permission Debug Commands ----- #
    @commands.guild_only()
    @commands.command(name="permcheck", aliases=["permissions", "perm"], brief="Debug ARCs permission settings.",
                      description="Debug ARCs permission settings.\n Useful if you are experiencing problems with ARC")
    async def permcheck(self, ctx: commands.Context):
        zws = "\N{ZERO WIDTH SPACE}"
        dot = "\N{Middle Dot}"

        guild: discord.Guild = ctx.guild
        guild_roles: List[discord.Role] = guild.roles

        # Since we can not rely on me.top_role to work reliably... (Sigh...) Lets make an API call here to ensure we have fresh data.
        # me: Union[discord.User, discord.Member] = guild.me
        me: Union[discord.User, discord.Member] = await guild.fetch_member(self.bot.user.id)
        log.info(f"Bot's Roles:\n{me.roles}")
        log.info(f"Bot's Top Role:\n{me.top_role}")
        bots_highest_role: discord.Role = me.top_role

        # Get all the roles that we are can use by permissions, the roles we cant use due to permissions, the roles we are configured to allow people to set, and the roles of those we cant set.
        roles_settable_by_bot = guild_roles[1:bots_highest_role.position]  # Remove @Everyone and all roles higher or equal to the highest role the bot has.
        roles_not_settable_by_bot = guild_roles[bots_highest_role.position:]

        log.info(f"Settable Roles:\n{roles_settable_by_bot}")
        log.info(f"unSettable Roles:\n{roles_not_settable_by_bot}")

        allowable_roles = await db.get_allowable_roles(self.pool, guild.id)
        assignable_roles = allowable_roles.allowed_intersection(roles_settable_by_bot)

        unassignable_roles = allowable_roles.allowed_intersection(roles_not_settable_by_bot)

        embed = discord.Embed(title="ARC Permissions Diagnostics")

        if len(unassignable_roles):  # len(allowable_roles.role_ids) - len(assignable_roles)) > 0:

            # description.extend([
            #                f"ARC only has permissions to assign **{len(assignable_roles)} out of {len(allowable_roles.role_ids)}** roles that it is configured to allow users to use.\n{zws}\n"
            #                f"Due to how Discord permissions work, ARC can *only* assign roles *lower* than the highest role that ARC possesses (<@&{bots_highest_role.id}>)\n",
            #                f"To enable ARC to give roles higher than that, either the <@&{bots_highest_role.id}> role needs to be dragged above all the roles you wish it to give, or it must be assigned a higher role.\n"
            # ])
            # all_assignable_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles_settable_by_bot])
            # embed.add_field(name=f"All Roles in {guild.name} ARC currently has the permissions to give:", value=all_assignable_roles_msg)

            # assignable_roles_msg = ", ".join([f"<@&{role.id}>" for role in assignable_roles])

            embed.add_field(name="Potential Problems With Automatic Role Changes:", value=f"ARC only has permissions to assign **{len(assignable_roles)} out of {len(allowable_roles.role_ids)}** roles that it is configured to allow users to use.\n{zws}\n"
            f"Due to how Discord permissions work, ARC can *only* assign roles *lower* than the highest role that ARC possesses (<@&{bots_highest_role.id}>)\n\n"
            f"To enable ARC to give roles higher than that, either the <@&{bots_highest_role.id}> role needs to be dragged above all the roles you wish it to give, or it must be assigned a higher role.\n", inline=False)

            unassignable_roles_msg = ", ".join([f"<@&{role.id}>" for role in unassignable_roles])
            if len(unassignable_roles_msg) > 1000:
                unassignable_roles_msg = f"Too many roles to list. {len(unassignable_roles_msg)} Roles."

            embed.add_field(name=f"All roles that ARC is configured to allow using, but is unable to assign due to discord permissions:",
                            value=unassignable_roles_msg, inline=False)

        if len(roles_not_settable_by_bot) > 0:
            # Since there are higher roles than use, there is a chance there are memberes of this guild that we can not assign roles too.
            # Check into this.
            guild_members: List[Union[discord.Member, discord.User]] = guild.members
            higher_members = [member for member in guild_members if member.top_role.position >= me.top_role.position and not member.bot]
            if len(higher_members) > 0:

                embed.add_field(name="Potential Problems With Automatic Name Changes:",
                                value="ARC is unable to automatically change some users nicknames.\n"
                                      f"This is because they have a role higher in the hierarchy than ARC possesses (<@&{bots_highest_role.id}>).\n\n"
                                      f"To fix this, either raise ARCs role, <@&{bots_highest_role.id}>, to be higher than theirs, or give ARC a higher role.\n\n"
                                      f"Please note, that ARC can *never* change the name of the guild owner.\n"
                                      "This is unfortunately a limitation with Discords permission system", inline=False)

                name_msg = ", ".join([f"<@{member.id}>" for member in higher_members])
                if len(name_msg) > 1000:
                    name_msg = f"Too many users to list. {len(name_msg)} Users."

                embed.add_field(name="ARC is unable to automaticly change the following users name:",
                                value=name_msg, inline=False)

        if len(embed.fields) == 0:
            embed.description = f"**No Problems Found!**\n{zws}\nPlease note, that ARC can *never* change the name of the guild owner.\n" \
                f"This is unfortunately a limitation with Discords permission system"
        else:
            embed.description = f"**Potential Problems Found!**\n{zws}"

        await ctx.send(embed=embed)


    @commands.guild_only()
    @commands.command(name="update", aliases=["sw"], brief="Update who is fronting.",
                      description="Cause the bot to check with PK to see who is fronting.\n"
                                  "If the fronter has changed, roles and nicknames will be updated accordingly.")
    async def update_command(self, ctx: commands.Context):
        await self.warning(f"{ctx.author.name} used update")
        msg = await ctx.send("Updating...")
        try:
            await self.update_system_members(force_discord_update=True, ctx=ctx)
        except PluralKitPrivacyError:
            await msg.edit(content=f"Unable to update! ARC is not yet compatible with some PK Privacy settings.")
            return

        if authorized_guilds is None or ctx.guild.id in authorized_guilds:
            user_settings = await db.get_user_settings_from_discord_id(self.pool, ctx.author.id, ctx.guild.id)
            if not user_settings or not user_settings.role_change and not user_settings.name_change:
                await msg.edit(content=f"You do not have roles or name changes enabled in this guild! You can enable them with the **{self.bot.command_prefix}settings** command.\n"
                               f"If your name and/or roles did not update in other guilds, please try again in a minute.")
            else:
                await msg.edit(content="System updated! If your roles and/or name did not update, please try again in a minute.")

    # @is_authorized_guild()
    @commands.guild_only()
    @commands.command(aliases=["list", "List_roles"], brief="See what roles are assigned to your system members.")
    async def list_member_roles(self, ctx: commands.Context):
        member_input = reactMenu.Page("str", name="List Roles",
                                      body="Please enter the name or ID of the System Member below:")
        await member_input.run(self.bot, ctx)
        if member_input is not None:
            member = await db.get_member_fuzzy(self.pool, ctx.author.id, member_input.response.content)
            if member is not None:
                roles = await db.get_roles_for_member_by_guild(self.pool, member['pk_mid'], ctx.guild.id)
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

        members = await db.get_members_by_discord_account_old(self.pool, ctx.author.id)

        if members is None or len(members) == 0:
            await ctx.send(
                f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
            return

        member_roles = []
        for member in members:
            roles = await db.get_roles_for_member_by_guild(self.pool, member['pk_mid'], ctx.guild.id)
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
                # await self.warning(f"role_msgs: {role_msgs}, Member: {member}, roles: {roles}")
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
            self.pool = bot.pool
            self.ctx = ctx
            self.member = None
            self.role = None

            self.allowable_roles: Optional[db.AllowableRoles] = None

        async def run(self):

            self.allowable_roles = await db.get_allowable_roles(self.pool, self.ctx.guild.id)
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

            members = await db.get_members_by_discord_account_old(self.pool, ctx.author.id)  # ctx.author.id)
            if members is None or len(members) == 0:

                await ctx.send(
                    f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
                return

            for role in roles.good_roles:
                for member in members:
                    await db.remove_role_from_member(self.pool, ctx.guild.id, member['pk_mid'], role.id)

            # Construct embed to tell the user of the successes and failures.

            embed = arcEmbeds.removed_roles_from_all_members_embed(roles)
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
                                                     body="Please enter a role or multiple roles separated by commas below:",
                                                     callback=self.remove_role_from_all_members)
                await remove_another_role.run(client, ctx)
            else:
                # await ctx.send("Finished removing roles!")
                await self.ask_to_go_back()

        # --- Remove Roles to member prompts --- #
        async def select_member_for_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                         response: discord.Message):

            member = await db.get_member_fuzzy(self.pool, ctx.author.id, response.content)
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
                await db.remove_role_from_member(self.pool, ctx.guild.id, self.member['pk_mid'], role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = arcEmbeds.removed_roles_from_some_members_embed(self.member, roles)
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
                                                  body="Please enter a role or multiple roles separated by commas below:",
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
            self.pool = bot.pool
            self.ctx = ctx
            self.member = None
            self.role = None

            self.allowable_roles: Optional[db.AllowableRoles] = None

        async def run(self):
            self.allowable_roles = await db.get_allowable_roles(self.pool, self.ctx.guild.id)
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

            # add_roles_from_discord_user = reactMenu.Page("str", name="Apply current roles to a member",
            #                            body="Makes the selected member have the roles currently on your discord account.",
            #                            additional="Please enter a System Member below:",
            #                            callback=self.select_member_for_current_roles)

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

            embed = arcEmbeds.allowable_roles_embed(self.allowable_roles)
            await ctx.send(embed=embed)
            await self.ask_to_go_back()

        async def add_role_to_all_members(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                          response: discord.Message):

            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return

            ask_to_add_more = reactMenu.Page("bool",
                                             name=f"Would you like to add another role to all system members?",
                                             callback=self.add_role_to_all_members_cont)
            role_text = response.content
            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text, self.allowable_roles)
            if roles is None:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            members = await db.get_members_by_discord_account_old(self.pool, ctx.author.id)  # ctx.author.id)
            if members is None or len(members) == 0:
                await ctx.send(
                    f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
                return

            for role in roles.good_roles:
                for member in members:
                    await db.add_role_to_member(self.pool, ctx.guild.id, member['pk_mid'], member['pk_sid'], role.id)

            embed = arcEmbeds.added_roles_to_all_members_embed(roles)
            await ctx.send(embed=embed)

            await ask_to_add_more.run(client, ctx)

        async def add_role_to_all_members_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: bool):
            # await page.remove()
            if response:
                add_another_role = reactMenu.Page("str", name="Add another role",
                                                  body="Please enter a role or multiple roles separated by commas below:",
                                                  callback=self.add_role_to_all_members)
                await add_another_role.run(client, ctx)
            else:
                # await ctx.send("Finished adding roles!")
                await self.ask_to_go_back()

        #
        # async def select_member_for_current_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
        #                                           response: discord.Message):
        #
        #     member = await db.get_member_fuzzy(self.pool, ctx.author.id, response.content)
        #     if member is None:
        #         await ctx.send(f"Could not find {response.content} in your system. Try using the 5 character Plural Kit ID.")
        #     else:
        #         self.member = member
        #
        #         verify_prompt = reactMenu.Page("bool",
        #                                    name=f"Are you sure you want to set all roles that are currently on your discord account onto {member['member_name']}? ",
        #                                    # body="Click ✅ or ❌",
        #                                    callback=self.verify_set_all_roles)
        #         await verify_prompt.run(self.bot, ctx)
        #
        # async def verify_set_all_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
        #                                response: bool):
        #     if response:
        #         # Todo: Implement
        #         await ctx.send(f"Setting all roles")
        #     else:
        #         await ctx.send(f"Canceled!")

        # --- Add Roles to member prompts --- #
        async def select_member_for_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context, response: discord.Message):

            member = await db.get_member_fuzzy(self.pool, ctx.author.id, response.content)
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

        # async def select_members_for_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context, response: discord.Message):
        #
        #     #
        #     # members = await db.get_members_by_discord_account(self.pool, ctx.author.id)
        #
        #     # member = await db.get_member_fuzzy(self.pool, ctx.author.id, response.content)
        #     members = await parse_csv_members(self.pool, ctx.author.id, response.content)
        #     if len(members) == 0:
        #         await ctx.send(f"Could not find {response.content} in your system. Try using the 5 character Plural Kit ID")
        #
        #     else:
        #
        #         self.member = member
        #         add_roles = reactMenu.Page("str",
        #                                    name=f"Add roles to member {member['member_name']}",
        #                                    body="Please enter a role or multiple roles separated by commas below: (Timesout in 300 seconds)",
        #                                    callback=self.add_role,
        #                                    timeout=300)
        #         await add_roles.run(self.bot, ctx)

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
                await db.add_role_to_member(self.pool, ctx.guild.id, self.member['pk_mid'], self.member['pk_sid'], role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = arcEmbeds.added_roles_to_some_members_embed(self.member, roles)
            await ctx.send(embed=embed)

            await ask_to_add_more.run(client, ctx)

        async def add_role_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                            response: bool):
            if response:
                add_another_role = reactMenu.Page("str", name="Add another role",
                                                  body="Please enter a role or multiple roles separated by commas below:",
                                                  callback=self.add_role)
                await add_another_role.run(client, ctx)
            else:
                # await ctx.send("Finished adding roles!")
                await self.ask_to_go_back()

    @is_authorized_guild()
    @commands.guild_only()
    @commands.command(aliases=["config", "setting", "user_setting", "user_settings"],
                      brief="Change user settings such as Auto Name Change and Auto Role Change")
    async def settings(self, ctx: commands.Context):
        settings = self.UserSettingsRolesMenuHandler(self.bot, ctx, self)
        await settings.run()

    class UserSettingsRolesMenuHandler:
        """
        Settings to add:
            System tag?
            Set roles for all fronters or first fronter.
            Update all accounts, just the active account, or a list of accounts?
        """

        def __init__(self, bot, ctx, cog):
            self.bot = bot
            self.pool = bot.pool
            self.ctx = ctx
            self.cog = cog

            self.current_user_settings: Optional[db.UserSettings] = None
            self.system: Optional[db.DBSystem] = None
            self.guild_settings = db.DBGuildSettings = None

        async def run(self):
            self.system = await db.get_system_by_discord_account(self.pool, self.ctx.author.id)
            if self.system is None:
                await self.ctx.send("You do not seem to be registered with this bot. "
                                    f"Please use reg_sys to `{self.bot.command_prefix}register` a new account or update your existing account")
                return
            # self.guild_settings = GuildSettings(** await db.get_guild_settings(self.pool, self.ctx.guild.id))
            # TODO: Change to getting user settigns via PK SID
            self.current_user_settings = await db.get_user_settings_from_discord_id(self.pool, self.ctx.author.id, self.ctx.guild.id)
            if self.current_user_settings is None:
                # Load default user settings in case none exist, then create a UserSettings obj manually
                await db.update_user_setting(self.pool, self.system.pk_sid, self.ctx.guild.id, False, False)
                self.current_user_settings = db.UserSettings({'pk_sid': self.system.pk_sid,
                                                              'guild_id': self.ctx.guild.id,
                                                              'name_change': False,
                                                              'role_change': False,
                                                              'system_role': None,
                                                              'system_role_enabled': False})

            auto_name = "On" if self.current_user_settings.name_change else "Off"
            auto_role = "On" if self.current_user_settings.role_change else "Off"
            system_role = "On" if self.current_user_settings.system_role_enabled else "Off"

            name_change = reactMenu.Page("bool", name="Toggle Auto Name Change",
                                         body=f"Toggles the automatic name change functionality. Currently **{auto_name}**",
                                         additional="Click ✅ to toggle automatic name changes, or click ❌ to cancel",
                                         callback=self.name_change)

            role_change = reactMenu.Page("Bool",
                                         name="Toggle Auto Role Change",
                                         body=f"Toggles the automatic role change functionality. Currently **{auto_role}**",
                                         additional="Click ✅ to toggle automatic role changes, or click ❌ to cancel",
                                         callback=self.role_change)

            system_role_toggle = reactMenu.Page("Bool",
                                         name="Toggle Custom System Role",
                                         body=f"Gives your discord account a dedicated role just for your system that will be automatically linked to your fronters favorite colors. Currently **{system_role}**",
                                         additional="Click ✅ to toggle custom system role, or click ❌ to cancel",
                                         callback=self.system_role_toggle)

            menu = reactMenu.Menu(name="Auto Role User Settings",
                                  body="Please select an option below by sending a message with the number",
                                  pages=[name_change, role_change, system_role_toggle]) #, set_system_tag_override])

            await menu.run(self.ctx)

        async def name_change(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                              response: bool):

            if response:
                new_name_setting = False if self.current_user_settings.name_change else True
                new_name_setting_text = "Off" if self.current_user_settings.name_change else "On"

                await db.update_user_setting(self.pool, self.current_user_settings.pk_sid, ctx.guild.id, name_change=new_name_setting,
                                             role_change=self.current_user_settings.role_change)
                await self.ctx.send(f"Automatic name changes are now **{new_name_setting_text}**")
            else:
                await self.ctx.send(f"Canceled!")

        async def role_change(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                              response: bool):

            if response:
                new_role_setting = False if self.current_user_settings.role_change else True
                new_role_setting_text = "Off" if self.current_user_settings.role_change else "On"

                await db.update_user_setting(self.pool, self.current_user_settings.pk_sid, ctx.guild.id, name_change=self.current_user_settings.name_change,
                                             role_change=new_role_setting)
                await self.ctx.send(f"Automatic role changes are now **{new_role_setting_text}**")
            else:
                await self.ctx.send(f"Canceled!")

        async def system_role_toggle(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                     response: bool):
            self.guild_settings = GuildSettings(** await db.get_guild_settings(self.pool, self.ctx.guild.id))

            if self.guild_settings is None or not self.guild_settings.custom_roles:
                await ctx.send(f"Custom system roles have been disabled in this server and can not be enabled.")
                await db.update_system_role(self.pool, self.system.pk_sid, ctx.guild.id, None, False)
                return

            if response:
                embed = discord.Embed(title="Custom System Role:")
                # Invert the current setting
                system_role_toggle_enabled = False if self.current_user_settings.system_role_enabled else True

                if system_role_toggle_enabled:
                    # Create the channel and
                    try:
                        fronters = await self.cog.get_fronters(self.current_user_settings.pk_sid)
                    except pk.Unauthorized:
                        return

                    current_fronter = fronters.members[0] if len(fronters.members) > 0 else None

                    # Get the current fronters favorite color or None if no one is fronting.
                    current_fronters_color = current_fronter.color if current_fronter else None
                    current_fronter_name = current_fronter.name if current_fronter else None

                    # Try to get the system name for the role, use the fronters name as a back up, and system ID as a final resort.
                    system_role_name = self.system.system_name or current_fronter_name or self.system.hid

                    # Get / Create the system role and update the DB with the new/current
                    system_role = await get_system_role(self.pool, guild=ctx.guild, system_role_id=self.current_user_settings.system_role,
                                                        system_role_enabled=True, system_id=self.system.pk_sid, system_name=system_role_name,
                                                        fronters_favorite_color=current_fronters_color)

                    # TODO: We are possibly updating the DB twice in the case a System role did not exist yet. FIX!
                    await db.update_system_role(self.pool, self.system.pk_sid, ctx.guild.id, system_role.id, True)

                    # give the user the new role
                    author: discord.Member = ctx.author
                    await author.add_roles(system_role)

                    # Write the reponse embed
                    embed.description = f"Your Systems Role <@&{system_role.id}> has been created and assigned to your account."
                else:
                    # Set the enable bit to False and delete the system role.
                    guild: discord.Guild = ctx.guild

                    if self.current_user_settings.system_role is not None:
                        systems_role: discord.Role = guild.get_role(self.current_user_settings.system_role)
                        if systems_role is not None:
                            await systems_role.delete()
                    await db.update_system_role(self.pool, self.system.pk_sid, guild.id, None, system_role_toggle_enabled)

                    embed.description = f"Your Custom System Role has been removed"

                await self.ctx.send(embed=embed)
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
            self.pool = bot.pool
            self.ctx = ctx

            self.allowable_roles: Optional[db.AllowableRoles] = None
            self.guild_settings = None
            self.guild_settings: Optional[GuildSettings] = None

        async def run(self):
            self.allowable_roles = await db.get_allowable_roles(self.pool, self.ctx.guild.id)
            self.guild_settings = GuildSettings(** await db.get_guild_settings(self.pool, self.ctx.guild.id))
            if self.guild_settings is None:
                # Somehow the guild doesnt have settings. Whoops. Add them now
                await db.add_guild_setting(self.pool, self.ctx.guild.id, name_change=True, role_change=True,
                                           log_channel=None, name_logging=False, role_logging=False)
                self.guild_settings = GuildSettings(** await db.get_guild_settings(self.pool, self.ctx.guild.id))

            system_role = "**On**" if self.guild_settings.custom_roles else "**Off**"

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

            toggle_custom_system_roles = reactMenu.Page(page_type="bool",
                                                        name="Toggle Custom System Roles",
                                                        body=f"Allows the members of your server to get a dedicated role just for their system that will be automatically linked whoever is frontings favorite color. This is not recommended for really large servers. Currently **{system_role}**",
                                                        callback=self.toggle_custom_system_roles)

            menu = reactMenu.Menu(name="Auto Role Admin Settings",
                                  body="Please select an option below by sending a message with the number",
                                  pages=[list_allowable_roles, add_allowable_roles, remove_allowable_roles, toggle_custom_system_roles])

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
            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text)
            if roles is None:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            for role in roles.good_roles:
                await db.add_allowable_role(self.pool, ctx.guild.id, role.id)

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
            # Remove all the good roles from the DB
            roles: Optional[ParsedRoles] = await parse_csv_roles(ctx, role_text)
            for role in roles.good_roles:
                await db.remove_allowable_role(self.pool, ctx.guild.id, role.id)

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

        async def toggle_custom_system_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                              response: bool):

            if response:
                new_custom_role_setting = False if self.guild_settings.custom_roles else True
                new_custom_role_setting_text = "Disabled" if self.guild_settings.custom_roles else "Enabled"

                await db.update_custom_role_guild_setting(self.pool, ctx.guild.id, new_custom_role_setting)

                await self.ctx.send(f"Custom System Roles for your servers members are now **{new_custom_role_setting_text}**")
            else:
                await self.ctx.send(f"Canceled!")

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
        await db.add_new_system(self.pool, system_id, system.name, None, system.tag, None)

        # Add default user settings
        await db.update_user_setting(self.pool, system_id, ctx.guild.id, name_change=False, role_change=False)

        await self.info(f"adding linked discord accounts DB: {system.name}({system.hid})")

        for account in pk_info['discord_accounts']:
            await db.add_linked_discord_account(self.pool, system_id, int(account))

        for member in members:
            fronting = True if member in current_fronters.members else False
            await db.add_new_member(self.pool, system_id, member.hid, member.name, fronting=fronting)
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

    @is_authorized_guild()
    @commands.guild_only()
    @commands.command(name="unregister", aliases=["unreg"],
                      brief="Unregisters you from ARC and deletes all your data.",
                      description="Unregisters you from ARC and deletes all your data.")
    async def unregister(self, ctx: commands.Context):
        pk_system_id = await db.get_system_id_by_discord_account(self.pool, ctx.author.id)
        confirmation = reactMenu.Page('str', name="Confirm Deletion", body=f"Type `{pk_system_id['pk_sid']}` to unregister and delete all your data.")
        await confirmation.run(self.bot, ctx)
        if confirmation.response is not None:
            # TODO: Check Type
            if confirmation.response.content.lower() == pk_system_id['pk_sid']:
                await db.remove_system(self.pool, pk_system_id['pk_sid'])
                await ctx.send("You have been removed from the system and all data has been deleted.")
                return
        await ctx.send("Deletion Canceled!")


    @commands.is_owner()
    @commands.command(hidden=True)
    async def debug_settings(self, ctx: commands.Context, member_id: int):  # , guild_id: Optional[int]):

        user_settings = await db.get_user_settings_from_discord_id(self.pool, member_id,
                                                                   ctx.guild.id)  # authorized_guilds[0])
        if not user_settings:
            await ctx.send(f"{member_id} has no settings.")
            return

        auto_name = "On" if user_settings.name_change else "Off"
        auto_role = "On" if user_settings.role_change else "Off"

        msg = f"Auto name: {auto_name}, Auto Roles: {auto_role}"
        await ctx.send(msg)

    @commands.is_owner()
    @commands.command(hidden=True, aliases=["d_as"])
    async def debug_all_settings(self, ctx: commands.Context, discord_id: Optional[int] = None):  # , guild_id: Optional[int]):

        if discord_id is None:
            discord_id = ctx.author.id

        unfindable_guilds = []
        embed_entries = []
        all_user_settings = await db.get_all_user_settings_from_discord_id(self.pool, discord_id)

        for settings_in_guild in all_user_settings:
            guild: Optional[discord.Guild] = self.bot.get_guild(settings_in_guild.guild_id)
            if guild is None:
                unfindable_guilds.append(str(settings_in_guild.guild_id))
                continue

            auto_name = "On" if settings_in_guild.name_change else "Off"
            auto_role = "On" if settings_in_guild.role_change else "Off"
            sys_role_enabled = settings_in_guild.system_role_enabled
            sys_role_id = settings_in_guild.system_role

            sys_role = guild.get_role(sys_role_id) if sys_role_id is not None else None

            header = f"Guild: {guild.name}"
            if not sys_role_enabled:
                sys_role_msg = "Off"
            elif sys_role_enabled and sys_role_id is not None and sys_role is None:
                sys_role_msg = f"On, but unresolvable: {sys_role_id}"
            elif sys_role_enabled and sys_role_id is not None and sys_role is not None:
                sys_role_msg = f"On: Name: {sys_role.name}, ID: {sys_role.id}, Pos: {sys_role.position}, Created: {sys_role.created_at.strftime('%Y-%m-%d, %H:%M:%S %z')}"
            else:
                sys_role_msg = f"Toggle: {sys_role_enabled}, DBID: {sys_role_id}, Role: {sys_role}"

            msg = f"Auto name: {auto_name}\nAuto Roles: {auto_role}\nSystem Role: {sys_role_msg}"
            embed_entries.append((header, msg))

        if len(unfindable_guilds) > 0:
            msg = ', '.join(unfindable_guilds)
            embed_entries.append(("Unresolvable Guilds:", msg))

        page = FieldPages(ctx, entries=embed_entries, per_page=10)
        page.embed.title = f"User Settings Debug.:"
        await page.paginate()


    @commands.is_owner()
    @commands.command(hidden=True, aliases=["d_ase"])
    async def debug_all_settings_everyone(self, ctx: commands.Context):

        unfindable_guilds = []
        embed_entries = []
        all_user_settings = await db.DEBUG_get_every_user_settings(self.pool)

        for settings_in_guild in all_user_settings:
            guild: Optional[discord.Guild] = self.bot.get_guild(settings_in_guild.guild_id)
            if guild is None:
                unfindable_guilds.append(str(settings_in_guild.guild_id))
                continue

            auto_name = "On" if settings_in_guild.name_change else "Off"
            auto_role = "On" if settings_in_guild.role_change else "Off"
            sys_role_enabled = settings_in_guild.system_role_enabled
            sys_role_id = settings_in_guild.system_role

            sys_role = guild.get_role(sys_role_id) if sys_role_id is not None else None

            header = f"Guild: {guild.name}\nUser: {settings_in_guild.pk_sid}"
            if not sys_role_enabled:
                sys_role_msg = "Off"
            elif sys_role_enabled and sys_role_id is not None and sys_role is None:
                sys_role_msg = f"On, but unresolvable: {sys_role_id}"
            elif sys_role_enabled and sys_role_id is not None and sys_role is not None:
                sys_role_msg = f"On: Name: {sys_role.name}, ID: {sys_role.id}, Pos: {sys_role.position}, Created: {sys_role.created_at.strftime('%Y-%m-%d, %H:%M:%S %z')}"
            else:
                sys_role_msg = f"Toggle: {sys_role_enabled}, DBID: {sys_role_id}, Role: {sys_role}"

            msg = f"Auto name: {auto_name}\nAuto Roles: {auto_role}\nSystem Role: {sys_role_msg}"
            embed_entries.append((header, msg))

        if len(unfindable_guilds) > 0:
            msg = ', '.join(set(unfindable_guilds))
            embed_entries.append(("Unresolvable Guilds:", msg))

        page = FieldPages(ctx, entries=embed_entries, per_page=10)
        page.embed.title = f"User Settings Debug.:"
        await page.paginate()




    #
    # @commands.is_owner()
    # @commands.command(hidden=True)
    # async def debug_data(self, ctx: commands.Context, discord_id: int):  # , guild_id: Optional[int]):
    #
    #     unfindable_guilds = []
    #     embed_entries = []
    #     all_user_settings = await db.get_all_user_settings_from_discord_id(self.pool, discord_id)
    #
    #     for settings_in_guild in all_user_settings:
    #         guild: Optional[discord.Guild] = self.bot.get_guild(settings_in_guild.guild_id)
    #         if guild is None:
    #             unfindable_guilds.append(settings_in_guild.guild_id)
    #             continue
    #
    #         auto_name = "On" if settings_in_guild.name_change else "Off"
    #         auto_role = "On" if settings_in_guild.role_change else "Off"
    #         msg = f"For Guild: {guild.name} Auto name: {auto_name}, Auto Roles: {auto_role}"
    #         embed_entries.append(msg)
    #
    #     page = FieldPages(ctx, entries=embed_entries, per_page=10)
    #     page.embed.title = f"User Settings Debug.:"
    #     await page.paginate()

# ----- Plural Kit API Call Functions ----- #

    async def get_fronters(self, pk_sys_id: str) -> pk.Fronters:
        try:
            async with aiohttp.ClientSession() as session:
                await self.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}/fronters'}")
                try:
                    fronters = await pk.Fronters.get_by_hid(session, pk_sys_id)
                    return fronters
                except pk.Unauthorized:
                    raise FrontersHidden
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
                except pk.Unauthorized:
                    raise MemberListHidden
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    async def info(self, msg):
        """Info Logger"""
        # func = inspect.currentframe().f_back.f_code
        # log.info(f"[{func.co_name}:{func.co_firstlineno}] {msg}")
        log.info(f"{msg}")
        # await self.bot.dLog.info(msg, header=f"[{__name__}]")

    async def warning(self, msg):
        log.warning(msg)
        # func = inspect.currentframe().f_back.f_code
        # log.info(f"[{func.co_name}:{func.co_firstlineno}] {msg}")
        await self.bot.dLog.warning(msg, header=f"[{__name__}]")


def setup(bot):
    bot.add_cog(AutoRoleChanger(bot))


class UnableToParseSystemCard(Exception):
    pass


class PluralKitPrivacyError(Exception):
    pass


class MemberListHidden(PluralKitPrivacyError):
    pass


class FrontersHidden(PluralKitPrivacyError):
    pass


