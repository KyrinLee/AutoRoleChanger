"""

"""

import asyncio
import logging
import re
from typing import Optional, Dict, List

import discord
from discord.ext import tasks, commands

import aiohttp
import cogs.utils.pluralKit as pk
import cogs.utils.reactMenu as reactMenu

import utils
import db

log = logging.getLogger(__name__)


class AutoRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.pk_id = 466378653216014359
        self.db = bot.db
        self.bot = bot
        self._last_nick_change: Optional[discord.Member] = None


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.content.lower().strip().startswith("pk;sw"):
            log.info("switch detected!")
            await asyncio.sleep(30)  # Pause to let API catch up
            # pk_info = await self.get_pk_system_by_discord_id(message.author.id)
            # await self.update_system(message=message)
            await self.update_only_fronters(message=message)
        else:
            await self.update_system(message=message, time_override=60*60)  # Update from any message once an hour (The default time)


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


    async def update_system(self, discord_member: discord.Member = None, ctx: Optional[commands.Context] = None, message: Optional[discord.Message] = None, time_override = 86400):
        if ctx is not None:
            discord_member: discord.Member = ctx.author
            message: discord.Message = ctx.message

        if message is not None:
            discord_member: discord.Member = message.author

        members = await db.get_members_by_discord_account_if_ood(self.db, discord_member.id, time_override)
        if members is not None:
            # log.info(f"updating {members}")

            system_id = members[0]['pk_sid']
            log.info(f"updating {system_id}")

            updated_members = await self.get_system_members(system_id)

            previous_fronters = await db.get_fronting_members_by_pk_sid(self.db, system_id)
            current_fronters = await self.get_fronters(system_id)
            for member in updated_members:
                fronting = True if member in current_fronters.members else False
                await db.update_member(self.db, system_id, member.hid, member.name, fronting=fronting)

            if previous_fronters != current_fronters.members:
                roles = []
                log.info(f"Fronters changed!: Prev: {previous_fronters}, Cur: {current_fronters}")
                for fronter in current_fronters.members:
                    new_roles = await db.get_roles_for_member_by_guild(self.db, fronter.hid, discord_member.guild.id)
                    new_roles_ids = [discord.Object(id=role['role_id']) for role in new_roles]
                    roles.extend(new_roles_ids)

                await self.autochange_discord_user(discord_member, roles, current_fronters.members[0].proxied_name)


    async def update_only_fronters(self, discord_member: discord.Member = None, ctx: Optional[commands.Context] = None, message: Optional[discord.Message] = None):
        if ctx is not None:
            discord_member: discord.Member = ctx.author
            message: discord.Message = ctx.message

        if message is not None:
            discord_member: discord.Member = message.author

        previous_fronters = await db.get_fronting_members_by_discord_account(self.db, discord_member.id)

        if previous_fronters is not None:
            system_id = previous_fronters[0].sid
        else:  # No one was in front. Get system_id from discord id
            sys_info = await db.get_system_id_from_linked_account(self.db, discord_member.id)
            if sys_info is None:
                return  # No registered account exists.
            system_id = sys_info['pk_system_id']

        current_fronters = await self.get_fronters(system_id)
        for member in current_fronters.members:
            fronting = True
            await db.update_member(self.db, system_id, member.hid, member.name, fronting=fronting)

        if previous_fronters != current_fronters.members:
            roles = []
            log.info(f"Fronters changed!: Prev: {previous_fronters}, Cur: {current_fronters}")
            for fronter in current_fronters.members:
                new_roles = await db.get_roles_for_member_by_guild(self.db, fronter.hid, discord_member.guild.id)
                new_roles_ids = [discord.Object(id=role['role_id']) for role in new_roles]
                roles.extend(new_roles_ids)

            await self.autochange_discord_user(discord_member, roles, current_fronters.members[0].proxied_name)


    async def autochange_discord_user(self, discord_member: discord.Member, new_roles: List[discord.Role], new_name: Optional[str]):
        """Applies the new roles and name to the selected discord user"""

        user_settings = await db.get_user_settings_from_discord_id(self.db, discord_member.id, discord_member.guild.id)

        if user_settings.role_change:
            log.info(f"Setting {new_name}'s {len(new_roles)} role(s) on {discord_member.display_name}")
            guild_allowed_auto_roles = await db.get_allowable_roles(self.db, discord_member.guild.id)

            # Get the auto roles to set and get the roles we must keep
            allowed_new_roles = guild_allowed_auto_roles.allowed_intersection(new_roles)
            old_roles_to_keep = guild_allowed_auto_roles.disallowed_intersection(discord_member.roles)

            # Use a set to ensure there are no duplicates.
            roles_to_set = set(allowed_new_roles + old_roles_to_keep)
            log.info(f"Applying the following roles: {roles_to_set}")
            try:
                await discord_member.edit(roles=set(roles_to_set))
            except discord.errors.Forbidden:
                log.info(f"Could not set roles: {roles_to_set} on {discord_member.display_name}")

        if user_settings.name_change:
            log.info(f"Changing {discord_member.display_name} name to {new_name}'s name")
            try:
                await discord_member.edit(nick=new_name)
            except discord.errors.Forbidden:
                log.info(f"Could not change {discord_member.display_name}'s name")


    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        event_type_nick = "guild_member_nickname"  # nickname
        event_type_update = "guild_member_update"  # Everything else. Currently unused.

        if before.nick != after.nick:
            log.info(f"{after.nick} changed their nickname from {before.nick}")
            # Update in nickname change if 5 minutes have passed since the last update.
            await self.update_only_fronters(after)


    @commands.command()
    async def sw(self, ctx: commands.Context):
        await self.update_system(ctx=ctx, time_override=1)
        await ctx.send("System updated!")


    @commands.command()
    async def update(self, ctx: commands.Context):
        await self.update_system(ctx=ctx, time_override=1)
        await ctx.send("System updated! If your roles and name did not update, please try again in a minute.")


    @commands.command()
    async def list_roles(self, ctx: commands.Context):
        member_input = reactMenu.Page(reactMenu.ResponseType(1), name="List Roles",
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
                await ctx.send(f"Could not find {member_input.response.content} in your system.")


    @commands.command()
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

            remove_roles = reactMenu.Page(reactMenu.ResponseType(1), name="Remove roles from a member",
                                          body="Remove any number of roles from one system member",
                                          additional="Please enter a System Member below:",
                                          callback=self.select_member_for_role)

            remove_roles_to_all_members = reactMenu.Page(reactMenu.ResponseType(1),
                                                         name="Remove roles from all your system members",
                                                         body="Remove any number of roles from all members in your system",
                                                         additional="Please enter a role or multiple roles separated by commas below: (Timesout in 300 seconds)",
                                                         callback=self.remove_role_from_all_members)

            menu = reactMenu.Menu(name="AutoRole Settings",
                                  body="Please select an option below by sending a message with the number or name",
                                  pages=[remove_roles, remove_roles_to_all_members])

            await menu.run(self.bot, self.ctx)


        async def remove_role_from_all_members(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: discord.Message):
            csv_regex = "(.+?)(?:,|$)"
            role_text = response.content
            if len(role_text) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            # Make sure that the string ends in a comma for proper regex detection
            if role_text[-1] != ",":
                role_text += ","

            # Separate the roles using regex
            raw_roles = re.findall(csv_regex, role_text)
            if len(raw_roles) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            good_roles = []
            bad_roles = []
            for raw_role in raw_roles:
                # raw_role: str
                try:
                    # Make sure the role exists and is on the allowed list.
                    potential_role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
                    allowed = False
                    for allowed_role_id in self.allowable_roles.role_ids:
                        if allowed_role_id == potential_role.id:
                            allowed = True
                            break

                    if not allowed:  # if its not allowed, put it on the bad list.
                        bad_roles.append(raw_role)
                    else:
                        good_roles.append(potential_role)

                except commands.errors.BadArgument:
                    # Role could not be found. Add to bad list.
                    bad_roles.append(raw_role)

            members = await db.get_members_by_discord_account(self.db, ctx.author.id)  # ctx.author.id)
            if len(members) == 0:  # FIXME: This will change to None at some point

                await ctx.send(
                    f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
                return

            for role in good_roles:
                for member in members:
                    await db.remove_role_from_member(self.db, ctx.guild.id, member['pk_mid'], role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed()
            embed.set_author(name=f"Roles added to all members:")

            if len(good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in good_roles])
                embed.add_field(name="Successfully added:", value=good_roles_msg)

            if len(bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in bad_roles])
                embed.add_field(
                    name="Could not find and remove the following (check spelling and capitalization)\n"
                         "It is possible they are not on the list of allowed Auto Changeable roles",
                    value=bad_roles_msg)

            await ctx.send(embed=embed)

            ask_to_remove_more = reactMenu.Page(reactMenu.ResponseType(2),
                                             name=f"Would you like to remove more roles from all system members?\n",
                                             body="Click ✅ or ❌",
                                             callback=self.remove_role_from_all_members_cont)
            await ask_to_remove_more.run(client, ctx)


        async def remove_role_from_all_members_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                                    response: bool):
            if response:
                remove_another_role = reactMenu.Page(reactMenu.ResponseType(1), name="Remove another role",
                                                     body="Please enter a role.",
                                                     callback=self.remove_role_from_all_members)
                await remove_another_role.run(client, ctx)
            else:
                await ctx.send("Finished removing roles!")

        # --- Remove Roles to member prompts --- #
        async def select_member_for_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                         response: discord.Message):

            member = await db.get_member_fuzzy(self.db, ctx.author.id, response.content)
            if member is None:
                await ctx.send(f"Could not find {response.content} in your system.")
            else:
                self.member = member
                remove_roles = reactMenu.Page(reactMenu.ResponseType(1),
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

            csv_regex = "(.+?)(?:,|$)"
            role_text = response.content
            if len(role_text) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            # Make sure that the string ends in a comma for proper regex detection
            if role_text[-1] != ",":
                role_text += ","

            # log.info(role_text)
            raw_roles = re.findall(csv_regex, role_text)
            if len(raw_roles) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return
            # log.info(raw_roles)
            good_roles = []
            bad_roles = []
            for raw_role in raw_roles:
                # raw_role: str
                try:
                    # Make sure the role exists and is on the allowed list.
                    potential_role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
                    allowed = False
                    for allowed_role_id in self.allowable_roles.role_ids:
                        if allowed_role_id == potential_role.id:
                            allowed = True
                            break

                    if not allowed:  # if its not allowed, put it on the bad list.
                        bad_roles.append(raw_role)
                    else:
                        good_roles.append(potential_role)

                except commands.errors.BadArgument:
                    # Role could not be found. Add to bad list.
                    bad_roles.append(raw_role)

            for role in good_roles:
                await db.remove_role_from_member(self.db, ctx.guild.id, self.member['pk_mid'], role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed()
            embed.set_author(name=f"Roles added to all members:")

            if len(good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in good_roles])
                embed.add_field(name="Successfully added:", value=good_roles_msg)

            if len(bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in bad_roles])
                embed.add_field(
                    name="Could not find and add the following (check spelling and capitalization):",
                    value=bad_roles_msg)

            await ctx.send(embed=embed)

            ask_to_remove_more = reactMenu.Page(reactMenu.ResponseType(2),
                                             name=f"Would you like to remove another role from {self.member['member_name']}?",
                                             body="Click ✅ or ❌",
                                             callback=self.remove_role_cont)
            await ask_to_remove_more.run(client, ctx)


        async def remove_role_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                   response: bool):
            if response:
                remove_another_role = reactMenu.Page(reactMenu.ResponseType(1), name="Remove another role",
                                                  body="Please enter a role.",
                                                  callback=self.remove_role)
                await remove_another_role.run(client, ctx)
            else:
                await ctx.send("Finished removing roles!")

    class RemoveRolesMenuHandler:

        def __init__(self, bot, ctx):
            self.bot = bot
            self.db = bot.db
            self.ctx = ctx
            self.member = None
            self.role = None


        async def run(self):

            remove_roles = reactMenu.Page(reactMenu.ResponseType(1), name="Remove roles from a member",
                                          body="Remove any number of roles from one system member",
                                          additional="Please enter a System Member below:",
                                          callback=self.select_member_for_role)

            remove_roles_to_all_members = reactMenu.Page(reactMenu.ResponseType(1),
                                                         name="Remove roles from all your system members",
                                                         body="Remove any number of roles from all members in your system",
                                                         additional="Please enter a role below:",
                                                         callback=self.remove_role_from_all_members)

            menu = reactMenu.Menu(name="AutoRole Settings",
                                  body="Please select an option below by sending a message with the number or name",
                                  pages=[remove_roles, remove_roles_to_all_members])

            await menu.run(self.bot, self.ctx)


        async def remove_role_from_all_members(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: discord.Message):
            try:
                role: discord.Role = await commands.RoleConverter().convert(ctx, response.content)
                members = await db.get_members_by_discord_account(self.db, ctx.author.id)  # ctx.author.id)
                if len(members) == 0:  # FIXME: This will change to None at some point
                    await ctx.send(
                        f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
                    return

                for member in members:
                    await db.remove_role_from_member(self.db, ctx.guild.id, member['pk_mid'], role.id)

                await ctx.send(f"Removed **{role.name}** from all registered system members!")

            except commands.errors.BadArgument:
                await ctx.send(f"**{response.content}** is not a valid role!")

            ask_to_remove_more = reactMenu.Page(reactMenu.ResponseType(2),
                                             name=f"Would you like to remove another role from all system members?\n",
                                             body="**CAUTION!!! THIS CAN NOT BE UNDONE!!!**\nClick ✅ or ❌",
                                             callback=self.remove_role_from_all_members_cont)
            await ask_to_remove_more.run(client, ctx)


        async def remove_role_from_all_members_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                                    response: bool):
            if response:
                remove_another_role = reactMenu.Page(reactMenu.ResponseType(1), name="Remove another role",
                                                     body="Please enter a role.",
                                                     callback=self.remove_role_from_all_members)
                await remove_another_role.run(client, ctx)
            else:
                await ctx.send("Finished removing roles!")

        # --- Remove Roles to member prompts --- #
        async def select_member_for_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                         response: discord.Message):

            member = await db.get_member_fuzzy(self.db, ctx.author.id, response.content)
            if member is None:
                await ctx.send(f"Could not find {response.content} in your system.")
            else:
                self.member = member
                remove_roles = reactMenu.Page(reactMenu.ResponseType(1),
                                              name=f"Remove roles from member {member['member_name']}",
                                              body="Please enter a role below:",
                                              callback=self.remove_role)
                await remove_roles.run(self.bot, ctx)


        async def remove_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                              response: discord.Message):
            try:
                role: discord.Role = await commands.RoleConverter().convert(ctx, response.content)

                await db.remove_role_from_member(self.db, ctx.guild.id, self.member['pk_mid'], role.id)
                await ctx.send(f"Removed the role **{role.name}** from **{self.member['member_name']}**")

            except commands.errors.BadArgument:
                await ctx.send(f"**{response.content}** is not a valid role!")

            ask_to_remove_more = reactMenu.Page(reactMenu.ResponseType(2),
                                             name=f"Would you like to remove another role from {self.member['member_name']}?",
                                             body="Click ✅ or ❌",
                                             callback=self.remove_role_cont)
            await ask_to_remove_more.run(client, ctx)


        async def remove_role_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                   response: bool):
            if response:
                remove_another_role = reactMenu.Page(reactMenu.ResponseType(1), name="Remove another role",
                                                  body="Please enter a role.",
                                                  callback=self.remove_role)
                await remove_another_role.run(client, ctx)
            else:
                await ctx.send("Finished removing roles!")


    @commands.command()
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

            list_allowable_roles = reactMenu.Page(reactMenu.ResponseType(4), name="List roles",
                                                  body="List all Auto changeable roles.",
                                                  callback=self.list_allowable_roles)

            add_roles = reactMenu.Page(reactMenu.ResponseType(1), name="Add roles to a member",
                                       body="Add any number of roles to one system member",
                                       additional="Please enter a System Member below:",
                                       callback=self.select_member_for_role)

            add_roles_from_discord_user = reactMenu.Page(reactMenu.ResponseType(1), name="Apply current roles to a member",
                                       body="Makes the selected member have the roles currently on your discord account.",
                                       additional="Please enter a System Member below:",
                                       callback=self.select_member_for_current_roles)

            add_roles_to_all_members = reactMenu.Page(reactMenu.ResponseType(1),
                                     name="Add roles to all your members",
                                     body="Add any number of roles to all members in your system",
                                     additional="Please enter a role or multiple roles separated by commas below: (Timesout in 300 seconds)",
                                     callback=self.add_role_to_all_members,
                                                      timeout=300)

            menu = reactMenu.Menu(name="AutoRole Settings",
                                  body="Please select an option below by sending a message with the number or name",
                                  pages=[list_allowable_roles, add_roles, add_roles_to_all_members])#, add_roles_from_discord_user])

            await menu.run(self.bot, self.ctx)


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


        async def add_role_to_all_members(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                          response: discord.Message):
            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return

            ask_to_add_more = reactMenu.Page(reactMenu.ResponseType(2),
                                             name=f"Would you like to add another role to all system members?",
                                             body="Click ✅ or ❌",
                                             callback=self.add_role_to_all_members_cont)

            csv_regex = "(.+?)(?:,|$)"
            role_text = response.content
            if len(role_text) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            # Make sure that the string ends in a comma for proper regex detection
            if role_text[-1] != ",":
                role_text += ","

            # log.info(role_text)
            raw_roles = re.findall(csv_regex, role_text)
            if len(raw_roles) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return
            # log.info(raw_roles)
            good_roles = []
            bad_roles = []
            for raw_role in raw_roles:
                # raw_role: str
                try:
                    # Make sure the role exists and is on the allowed list.
                    potential_role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
                    allowed = False
                    for allowed_role_id in self.allowable_roles.role_ids:
                        if allowed_role_id == potential_role.id:
                            allowed = True
                            break

                    if not allowed:  # if its not allowed, put it on the bad list.
                        bad_roles.append(raw_role)
                    else:
                        good_roles.append(potential_role)

                except commands.errors.BadArgument:
                    # Role could not be found. Add to bad list.
                    bad_roles.append(raw_role)

            members = await db.get_members_by_discord_account(self.db, ctx.author.id)  # ctx.author.id)
            if len(members) == 0:  # FIXME: This will change to None at some point
                await ctx.send(
                    f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
                return
            for role in good_roles:
                for member in members:
                    await db.add_role_to_member(self.db, ctx.guild.id, member['pk_mid'], role.id)

                # await ctx.send(f"Added **{role.name}** to all registered system members!")

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed()
            embed.set_author(name=f"Roles added to all members:")

            if len(good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in good_roles])
                embed.add_field(name="Successfully added:", value=good_roles_msg)

            if len(bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in bad_roles])
                embed.add_field(
                    name="Could not find and add the following (check spelling and capitalization):",
                    value=bad_roles_msg)

            await ctx.send(embed=embed)

            await ask_to_add_more.run(client, ctx)


        async def add_role_to_all_members_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: bool):
            if response:
                add_another_role = reactMenu.Page(reactMenu.ResponseType(1), name="Add another role",
                                                  body="Please enter a role.",
                                                  callback=self.add_role_to_all_members)
                await add_another_role.run(client, ctx)
            else:
                await ctx.send("Finished adding roles!")

        async def select_member_for_current_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                                  response: discord.Message):

            member = await db.get_member_fuzzy(self.db, ctx.author.id, response.content)
            if member is None:
                await ctx.send(f"Could not find {response.content} in your system.")
            else:
                self.member = member

                verify_prompt = reactMenu.Page(reactMenu.ResponseType(2),
                                           name=f"Are you sure you want to set all roles that are currently on your discord account onto {member['member_name']}? ",
                                           body="Click ✅ or ❌",
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
                await ctx.send(f"Could not find {response.content} in your system.")
            else:
                self.member = member
                add_roles = reactMenu.Page(reactMenu.ResponseType(1),
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

            ask_to_add_more = reactMenu.Page(reactMenu.ResponseType(2),
                                             name=f"Would you like to add another role to {self.member['member_name']}?",
                                             body="Click ✅ or ❌",
                                             callback=self.add_role_cont)

            csv_regex = "(.+?)(?:,|$)"
            role_text = response.content
            if len(role_text) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            # Make sure that the string ends in a comma for proper regex detection
            if role_text[-1] != ",":
                role_text += ","

            # log.info(role_text)
            raw_roles = re.findall(csv_regex, role_text)
            if len(raw_roles) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return
            # log.info(raw_roles)
            good_roles = []
            bad_roles = []
            for raw_role in raw_roles:
                # raw_role: str
                try:
                    # Make sure the role exists and is on the allowed list.
                    potential_role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
                    allowed = False
                    for allowed_role_id in self.allowable_roles.role_ids:
                        if allowed_role_id == potential_role.id:
                            allowed = True
                            break

                    if not allowed:  # if its not allowed, put it on the bad list.
                        bad_roles.append(raw_role)
                    else:
                        good_roles.append(potential_role)

                except commands.errors.BadArgument:
                    # Role could not be found. Add to bad list.
                    bad_roles.append(raw_role)

            for role in good_roles:
                await db.add_role_to_member(self.db, ctx.guild.id, self.member['pk_mid'], role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed()
            embed.set_author(name=f"Roles added to all members:")

            if len(good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in good_roles])
                embed.add_field(name="Successfully added:", value=good_roles_msg)

            if len(bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in bad_roles])
                embed.add_field(
                    name="Could not find and add the following (check spelling and capitalization):",
                    value=bad_roles_msg)

            await ctx.send(embed=embed)

            await ask_to_add_more.run(client, ctx)


        async def add_role_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                            response: bool):
            if response:
                add_another_role = reactMenu.Page(reactMenu.ResponseType(1), name="Add another role",
                                                  body="Please enter a role.",
                                                  callback=self.add_role)
                await add_another_role.run(client, ctx)
            else:
                await ctx.send("Finished adding roles!")

    class AddRolesMenuHandler:

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

            list_allowable_roles = reactMenu.Page(reactMenu.ResponseType(4), name="List roles",
                                                  body="List all Auto changeable roles.",
                                                  callback=self.list_allowable_roles)

            add_roles = reactMenu.Page(reactMenu.ResponseType(1), name="Add roles to a member",
                                       body="Add any number of roles to one system member",
                                       additional="Please enter a System Member below:",
                                       callback=self.select_member_for_role)

            add_roles_from_discord_user = reactMenu.Page(reactMenu.ResponseType(1), name="Apply current roles to a member",
                                       body="Makes the selected member have the roles currently on your discord account.",
                                       additional="Please enter a System Member below:",
                                       callback=self.select_member_for_current_roles)

            add_roles_to_all_members = reactMenu.Page(reactMenu.ResponseType(1),
                                     name="Add roles to all your members",
                                     body="Add any number of roles to all members in your system",
                                     additional="Please enter a role below:",
                                     callback=self.add_role_to_all_members)

            menu = reactMenu.Menu(name="AutoRole Settings",
                                  body="Please select an option below by sending a message with the number or name",
                                  pages=[list_allowable_roles, add_roles, add_roles_to_all_members])#, add_roles_from_discord_user])

            await menu.run(self.bot, self.ctx)


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


        async def add_role_to_all_members(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                          response: discord.Message):
            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return

            ask_to_add_more = reactMenu.Page(reactMenu.ResponseType(2),
                                             name=f"Would you like to add another role to all system members?",
                                             body="Click ✅ or ❌",
                                             callback=self.add_role_to_all_members_cont)
            try:
                role: discord.Role = await commands.RoleConverter().convert(ctx, response.content)
                # self.role = role

                allowed = False
                for allowed_role_id in self.allowable_roles.role_ids:
                    if allowed_role_id == role.id:
                        allowed = True
                        break
                if not allowed:
                    await ctx.send(f"This role `{role.name}` is not auto changeable and can not be set.")
                    await ask_to_add_more.run(client, ctx)
                    return

                members = await db.get_members_by_discord_account(self.db, ctx.author.id)  # ctx.author.id)
                if len(members) == 0:  # FIXME: This will change to None at some point
                    await ctx.send(
                        f"You do not have a Plural Kit account registered. Use `{self.bot.command_prefix}register` to register your system.")
                    return

                for member in members:
                    await db.add_role_to_member(self.db, ctx.guild.id, member['pk_mid'], role.id)

                await ctx.send(f"Added **{role.name}** to all registered system members!")

            except commands.errors.BadArgument:
                await ctx.send(f"**{response.content}** is not a valid role!")


            await ask_to_add_more.run(client, ctx)


        async def add_role_to_all_members_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                            response: bool):
            if response:
                add_another_role = reactMenu.Page(reactMenu.ResponseType(1), name="Add another role",
                                                  body="Please enter a role.",
                                                  callback=self.add_role_to_all_members)
                await add_another_role.run(client, ctx)
            else:
                await ctx.send("Finished adding roles!")

        async def select_member_for_current_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                                  response: discord.Message):

            member = await db.get_member_fuzzy(self.db, ctx.author.id, response.content)
            if member is None:
                await ctx.send(f"Could not find {response.content} in your system.")
            else:
                self.member = member

                verify_prompt = reactMenu.Page(reactMenu.ResponseType(2),
                                           name=f"Are you sure you want to set all roles that are currently on your discord account onto {member['member_name']}? ",
                                           body="Click ✅ or ❌",
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
                await ctx.send(f"Could not find {response.content} in your system.")
            else:
                self.member = member
                add_roles = reactMenu.Page(reactMenu.ResponseType(1),
                                           name=f"Add roles to member {member['member_name']}",
                                           body="Please enter a role below:",
                                           callback=self.add_role)
                await add_roles.run(self.bot, ctx)


        async def add_role(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                           response: discord.Message):

            if self.allowable_roles is None:
                await self.ctx.send("There are no Auto changeable roles set up for this guild!")
                return

            ask_to_add_more = reactMenu.Page(reactMenu.ResponseType(2),
                                             name=f"Would you like to add another role to {self.member['member_name']}?",
                                             body="Click ✅ or ❌",
                                             callback=self.add_role_cont)

            try:
                role: discord.Role = await commands.RoleConverter().convert(ctx, response.content)

                allowed = False
                for allowed_role_id in self.allowable_roles.role_ids:
                    if allowed_role_id == role.id:
                        allowed = True
                        break
                if not allowed:
                    await ctx.send(f"This role ({role.name}) is not Auto changeable and can not be set.")
                    await ask_to_add_more.run(client, ctx)
                    return

                role_added = await db.add_role_to_member(self.db, ctx.guild.id, self.member['pk_mid'], role.id)
                if role_added:
                    await ctx.send(f"Added the role **{role.name}** to **{self.member['member_name']}**")
                else:
                    await ctx.send(f"**{self.member['member_name']}** already had the role **{role.name}**")
            except commands.errors.BadArgument:
                await ctx.send(f"**{response.content}** is not a valid role!")

            await ask_to_add_more.run(client, ctx)


        async def add_role_cont(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                            response: bool):
            if response:
                add_another_role = reactMenu.Page(reactMenu.ResponseType(1), name="Add another role",
                                                  body="Please enter a role.",
                                                  callback=self.add_role)
                await add_another_role.run(client, ctx)
            else:
                await ctx.send("Finished adding roles!")


    @commands.command()
    async def settings(self, ctx: commands.Context):
        settings = self.UserSettingsRolesMenuHandler(self.bot, ctx)
        await settings.run()


    class UserSettingsRolesMenuHandler:
        """
        Settings to add:
            System tag?
            Set roles for all fronters or first fronter.
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

            # TODO: Get current settings
            auto_name = "On" if self.current_user_settings.name_change else "Off"
            auto_role = "On" if self.current_user_settings.role_change else "Off"

            name_change = reactMenu.Page(reactMenu.ResponseType(2), name="Toggle Auto Name Change",
                                         body=f"Toggles the automatic name change functionality. Currently **{auto_name}**",
                                         additional="Click ✅ to toggle automatic name changes, or click ❌ to cancel",
                                         callback=self.name_change)

            role_change = reactMenu.Page(reactMenu.ResponseType(2),
                                         name="Toggle Auto Role Change",
                                         body=f"Toggles the automatic role change functionality. Currently **{auto_role}**",
                                         additional="Click ✅ to toggle automatic role changes, or click ❌ to cancel",
                                         callback=self.role_change)

            menu = reactMenu.Menu(name="AutoRole User Settings",
                                  body="Please select an option below by sending a message with the number or name",
                                  pages=[name_change, role_change])  # , add_roles_from_discord_user])

            await menu.run(self.bot, self.ctx)


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


    @commands.command()
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

            list_allowable_roles = reactMenu.Page(reactMenu.ResponseType(4), name="List usable roles.",
                                                  body="Displays a list of all the roles users are allowed to use",
                                                  callback=self.list_allowable_roles)

            add_allowable_roles = reactMenu.Page(reactMenu.ResponseType(1),
                                                 name="Add more roles",
                                                 body="Add more roles that users are allowed to set",
                                                 additional="Please enter a role or multiple roles separated by commas below: (Times out in 300 seconds)",
                                                 callback=self.add_allowable_roles, timeout=300)

            remove_allowable_roles = reactMenu.Page(reactMenu.ResponseType(1),
                                                    name="Remove roles",
                                                    body="Remove roles from that which users are allowed to set",
                                                    additional="Please enter a role or multiple roles separated by commas below: (Times out in 300 seconds)",
                                                    callback=self.remove_allowable_roles, timeout=300)

            menu = reactMenu.Menu(name="AutoRole Admin Settings",
                                  body="Please select an option below by sending a message with the number or name",
                                  pages=[list_allowable_roles, add_allowable_roles, remove_allowable_roles])

            await menu.run(self.bot, self.ctx)


        async def list_allowable_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context):
            """Sends embed with all the allowable roles."""

            embed = discord.Embed()
            embed.set_author(name=f"Roles that users may use.")

            if self.allowable_roles is not None:
                roles_msg = "\n".join([f"<@&{role_id}>" for role_id in self.allowable_roles.role_ids])
            else:
                roles_msg = "No roles are configured!"

            embed.description = roles_msg
            await ctx.send(embed=embed)


        async def add_allowable_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: discord.Message):
            """Add more roles to the list of usable roles"""
            csv_regex = "(.+?)(?:,|$)"
            role_text = response.content
            if len(role_text) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            # Make sure that the string ends in a comma for proper regex detection
            if role_text[-1] != ",":
                role_text += ","
            log.info(role_text)
            raw_roles = re.findall(csv_regex, role_text)
            if len(raw_roles) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return
            log.info(raw_roles)
            good_roles = []
            bad_roles = []
            for raw_role in raw_roles:
                raw_role: str
                try:
                    # add identifiable roles to the good list
                    # Todo: Try to match up Snowflake like raw roles to the roles in self.allowable_roles and bypass the RoleConverter on success.
                    role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
                    good_roles.append(role)
                except commands.errors.BadArgument:
                    # Role could not be found. Add to bad list.
                    bad_roles.append(raw_role)

            # Add all the good roles to the DB
            for role in good_roles:
                await db.add_allowable_role(self.db, ctx.guild.id, role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed()
            embed.set_author(name=f"Roles Added to list:")

            if len(good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in good_roles])
                embed.add_field(name="Successfully added:", value=good_roles_msg)

            if len(bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in bad_roles])
                embed.add_field(name="Could not find and add the following (check spelling and capitalization):", value=bad_roles_msg)

            await ctx.send(embed=embed)

        async def remove_allowable_roles(self, page: reactMenu.Page, client: commands.bot, ctx: commands.Context,
                                               response: discord.Message):
            """Remove roles from the list of usable roles"""
            csv_regex = "(.+?)(?:,|$)"
            role_text = response.content
            if len(role_text) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            # Make sure that the string ends in a comma for proper regex detection
            if role_text[-1] != ",":
                role_text += ","

            raw_roles = re.findall(csv_regex, role_text)
            if len(raw_roles) == 0:
                await ctx.send("ERROR!!! Could not parse roles!")
                return

            good_roles = []
            bad_roles = []
            for raw_role in raw_roles:
                try:
                    # add identifiable roles to the good list
                    # Todo: Try to match up Snowflake like raw roles to the roles in self.allowable_roles and bypass the RoleConverter on success.
                    role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
                    good_roles.append(role)
                except commands.errors.BadArgument:
                    # Role could not be found. Add to bad list.
                    bad_roles.append(raw_role)

            # Remove all the good roles from the DB
            for role in good_roles:
                await db.remove_allowable_role(self.db, ctx.guild.id, role.id)

            # Construct embed to tell the user of the successes and failures.
            embed = discord.Embed()
            embed.set_author(name=f"Roles removed from the list:")

            if len(good_roles) > 0:
                good_roles_msg = ", ".join([f"<@&{role.id}>" for role in good_roles])
                embed.add_field(name="Successfully removed:", value=good_roles_msg)

            if len(bad_roles) > 0:
                bad_roles_msg = ", ".join([f"{role}" for role in bad_roles])
                embed.add_field(name="Could not find and remove the following (check spelling and capitalization):", value=bad_roles_msg)

            await ctx.send(embed=embed)


    @commands.command()
    async def register(self, ctx: commands.Context):
        """Allows you to link your PK account to this bot."""
        # TODO: Add ability to update current registration (Mainly discord accounts)
        await ctx.send(f"To register your Plural Kit account, please use the command `pk;s` to have Plural Kit send you system card")

        def check_for_pk_response(m: discord.Message):
            # log.info(f"Got Message: {m}, Embeds: {len(m.embeds)}")
            return m.author.id == self.pk_id and len(m.embeds) == 1

        try:
            pk_msg: discord.Message = await self.bot.wait_for('message', timeout=30.0, check=check_for_pk_response)
        except asyncio.TimeoutError:
            await ctx.send("Command timed out!")
            return None

        log.info(f"Got PK Embed: {pk_msg.embeds}")
        pk_info = self.parse_system_card(pk_msg.embeds[0])
        system_id = pk_info['system_id']

        # Verify that this card belongs to the system that used the register command.
        verification_system = await self.get_system_by_discord_id(ctx.author.id)
        if verification_system.hid != system_id:
            await ctx.send("Error!!! I seem to have gotten mixed up. Someone else may have used pk;s before you did! Please try to use the register again.")
            return

        system = await self.get_system(system_id)
        try:
            members = await self.get_system_members(system_id)
        except MemberListHidden:
            # await ctx.send(f"Your Plural Kit setting require that I get additional information for in order to operate properly.\n"
            #                f"Sending you a DM for further configuration.")
            # await self.prompt_for_pk_token(ctx)
            await ctx.send("Unfortunately this bot does not yet support the new Plural Kit privacy settings.\n")
            return

        current_fronters = await self.get_fronters(system_id)
        log.info(f"adding new system to DB: {system.name}")
        await db.add_new_system(self.db, system_id, system.name, current_fronters.members[0].hid, None)

        # Add default user settings
        await db.update_user_setting(self.db, system_id, ctx.guild.id, name_change=False, role_change=False)

        log.info(f"adding linked discord accounts DB: {system.name}")

        for account in pk_info['discord_accounts']:
            await db.add_linked_discord_account(self.db, system_id, int(account))

        for member in members:
            log.info(f"adding new member to DB: {member.name}")
            fronting = True if member in current_fronters.members else False
            await db.add_new_member(self.db, system_id, member.hid, member.name, fronting=fronting)
        await ctx.send(f"Your system and {len(members)} members of your system have been registered successfully!\n"
                       f"Hidden members are not yet supported.\n\n"
                       f"Auto name and role changing is currently **Off**. You may change these settings by using the **{self.bot.command_prefix}settings** command\n"
                       f"You may set up your system members roles by using the **{self.bot.command_prefix}add_role** command\n"
                       f"You can see the list of roles by a system member has using the **{self.bot.command_prefix}list_roles** command\n")



    # async def send_help(self, ctx):
    #     await ctx.send(f"Your system and {len(members)} members of your system have been registered successfully!\n"
    #                    f"Any hidden members may now be registered manually.\n\n"
    #                    f"Auto name and role changing is currently **Off**. You may set these settings by using the **{self.bot.command_prefix}settings** command\n"
    #                    f"You may set up your system members roles by using the **{self.bot.command_prefix}add_role** command\n"
    #                    f"You can see the list of roles by a system memeber has using the **{self.bot.command_prefix}list_roles** command\n")


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
                log.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}/fronters'}")
                fronters = await pk.Fronters.get_by_hid(session, pk_sys_id)
                return fronters
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    async def get_system(self, pk_sys_id: str) -> pk.System:
        try:
            async with aiohttp.ClientSession() as session:
                log.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}'}")
                system = await pk.System.get_by_hid(session, pk_sys_id)
                return system
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    async def get_system_by_discord_id(self, discord_user_id: int) -> pk.System:
        try:
            async with aiohttp.ClientSession() as session:
                log.warning(f"Scraping: {f'https://api.pluralkit.me/a/{discord_user_id}'}")
                system = await pk.System.get_by_account(session, discord_user_id)
                return system
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))

    async def get_system_members(self, pk_sys_id: str) -> pk.Members:
        try:
            async with aiohttp.ClientSession() as session:
                log.warning(f"Scraping: {f'https://api.pluralkit.me/s/{pk_sys_id}/members'}")
                try:
                    members = await pk.Members.get_by_hid(session, pk_sys_id)
                    return members
                except pk.NeedsAuthorization:
                    raise MemberListHidden
        except aiohttp.ClientError as e:
            log.warning(
                "Could not connect to PK server with out errors. \n{}".format(e))


    # @commands.command()
    # async def update(self, ctx: commands.Context, time_override:int):
    #     await self.update_systems_information(time_override)
    #
    #
    # # --- Tasks --- #
    # # noinspection PyCallingNonCallable
    # @tasks.loop(minutes=5)
    # async def update_systems(self):
    #     log.info(f"Attempting to update systems")
    #     older_than = 60 * 5  # In seconds
    #     await self.update_systems_information(older_than)



def setup(bot):
    bot.add_cog(AutoRole(bot))


class UnableToParseSystemCard(Exception):
    pass


class MemberListHidden(Exception):
    pass
