"""

"""
import re
import logging
# from collections import namedtuple

from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import tasks, commands
from discord import utils

from fuzzywuzzy import fuzz
from fuzzywuzzy import process

from postgresDB import AllowableRoles, DBMember, get_members_by_discord_account, UserSettings, update_system_role

if TYPE_CHECKING:
    from discordBot import PNBot

log = logging.getLogger(__name__)

#
# class GuildSettings(NamedTuple):
#     guild_id: int
#     name_change: bool
#     role_change: bool
#     log_channel: int
#     name_logging: bool
#     role_logging: bool
#     custom_roles: bool
#

class BadRole(NamedTuple):
    role: str
    best_match: Optional[discord.Role]
    score: Optional[int]

    def __str__(self):
        # if self.best_match is not None:
        #     string = f"{self.role} [Maybe {self.best_match[0]} ({self.best_match[1]})]"
        # else:
        string = f"{self.role}"
        return string


class ParsedRoles(NamedTuple):
    good_roles: List[discord.Role]
    disallowed_roles: List[discord.Role]
    bad_roles: List[BadRole]


async def get_system_role(pool, guild: discord.Guild, system_role_id: Optional[int], system_role_enabled: bool,
                          system_id: str, system_name: str, fronters_favorite_color: Optional[str]) -> Optional[discord.Role]:

    system_role = None
    if system_role_enabled:
        # Try to get the system role from d.py
        if system_role_id is not None:
            system_role: Optional[discord.Role] = guild.get_role(system_role_id)
            if system_role is None:
                log.warning(f"Could not 'get' {system_name}s role in {guild.name}! Falling back to Fetch.")
                guild_roles: List[discord.Role] = await guild.fetch_roles()
                system_role: Optional[discord.Role] = discord.utils.get(guild_roles, id=system_role_id)
                if system_role is None:
                    log.warning(f"Could not 'Fetch' {system_name}s role in {guild.name}! Role must have been deleted, Recreating.")

        # Convert the system members favorite color to a discord.Color
        color = hex_to_color(fronters_favorite_color) if fronters_favorite_color is not None else discord.Color.default()

        # Get the position of the bots managed role
        # I'm sure you can only have one managed role. but just in case lets revers the list and grab the highest role
        bot_roles: List[discord.Role] = guild.me.roles
        bot_roles.reverse()
        managed_role = discord.utils.get(bot_roles, managed=True)
        # just in case that turned up nothing, just the top role as a back up.
        arc_role: discord.Role = managed_role or guild.me.top_role

        # Get/Create the system role.
        if system_role is None:  # if the role got deleted or somehow didn't exist recreate it.
            try:
                system_role = await guild.create_role(name=system_name, color=color)
                await system_role.edit(position=arc_role.position-1)
                log.warning(f"Creating new role for {system_name} in {guild.name} with id:{system_role.id}. DB query results: {system_role_id}")
            except discord.Forbidden:
                return None  # Todo do something other than silently fail.
            await update_system_role(pool=pool, pk_sid=system_id, guild_id=guild.id, system_role=system_role.id, enabled=system_role_enabled)

        else:
            await system_role.edit(name=system_name, color=color, position=arc_role.position-1)

    return system_role


def hex_to_color(hex_color: Optional[str]) -> discord.Color:

    if hex_color is None:
        return discord.Color.default()

    rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    color = discord.Color.from_rgb(r=rgb[0], g=rgb[1], b=rgb[2])
    return color


async def parse_csv_roles(ctx: commands.Context, role_text: str, allowed_roles: Optional[AllowableRoles] = None) -> Optional[NamedTuple]:
    """ Parse a message containing CSV Roles.
        Returns Named Tuple with Good roles and bad roles.
        Returns None if it can't parse. """
    csv_regex = "(.+?)(?:,|$)"

    if len(role_text) == 0:
        return None

    # Make sure that the string ends in a comma for proper regex detection
    if role_text[-1] != ",":
        role_text += ","

    # Strip out any @ symbols as the RoleConverter can't handle them.
    role_text = role_text.replace("@", "")

    # Pull out the roles from teh CSV
    raw_roles = re.findall(csv_regex, role_text)

    # If we couldn't pull anything, return None.
    if len(raw_roles) == 0:
        return None

    log.info(raw_roles)

    # Loop through all the role strings trying to get discord.Role objects.
    # If we are able to get a discord.Role object, we can assume it's a valid role. and if we can't, it probably isn't
    good_roles = []
    bad_roles = []
    disallowed_roles = []

    guild_roles: List[discord.Role] = ctx.guild.roles[1:]  # Get all the roles from the guild EXCEPT @everyone.
    for raw_role in raw_roles:
        raw_role = raw_role.strip()  # Remove any leading/trailing whitespace
        try:
            # add identifiable roles to the good list
            # Todo: Try to match up Snowflake like raw roles to the roles in self.allowable_roles and bypass the RoleConverter on success.
            potential_role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role)  # Try to match the text to an actual role.
            if allowed_roles is None or allowed_roles.is_allowed(potential_role):
                # Add the role to the good list IF it's on the allowed list, or if there is no allowed list.
                good_roles.append(potential_role)
            else:
                # If we get here, it's because the role exists but is not allowed to be used by users.
                disallowed_roles.append(potential_role)

        except commands.errors.BadArgument:  # This error indicates that the RoleConverter() failed to identify the role.
            # Role could not be found. Try to use fuzzyWuzzy string matching to try to identify the role despite typos.
            match = process.extractOne(raw_role, guild_roles, score_cutoff=0)

            # If we can't match, match will be None. Assign accordingly.
            best_match = match[0] if match else None
            score = match[1] if match else None

            # Check to see if the type is role and if it is on the allowed list.
            if isinstance(best_match, discord.Role) and allowed_roles is not None and allowed_roles.is_allowed(best_match):
                bad_role = BadRole(role=raw_role, best_match=best_match, score=score)  # Add the suggestion since it IS an allowed role.
            else:
                bad_role = BadRole(role=raw_role, best_match=None, score=None)  # Don't recommend roles that Users can't set.

            bad_roles.append(bad_role)

    parsed_roles = ParsedRoles(good_roles=good_roles, bad_roles=bad_roles, disallowed_roles=disallowed_roles)
    return parsed_roles


class InvalidMember(NamedTuple):
    member_name: str
    best_match: Optional[DBMember]
    score: Optional[int]


class ParsedMembers(NamedTuple):
    good_members: List[DBMember]
    invalid_members: List[InvalidMember]


async def parse_csv_members(pool, discord_id: int, member_csv: str) -> Optional[NamedTuple]:

    db_members = await get_members_by_discord_account(pool, discord_id)
    csv_regex = "(.+?)(?:,|$)"

    if len(member_csv) == 0:
        return None

    # Make sure that the string ends in a comma for proper regex detection
    if member_csv[-1] != ",":
        member_csv += ","

    # Pull out the members from teh CSV
    raw_members = re.findall(csv_regex, member_csv)

    # If we couldn't pull anything, return None.
    if len(raw_members) == 0:
        return None

    log.info(raw_members)

    names_and_ids = [m.member_name for m in db_members] + [m.pk_mid for m in db_members]
    valid_members = []
    invalid_members = []

    for raw_member in raw_members:
        raw_member: str = raw_member.strip().lower()

        potential_member = utils.find(lambda m: (m.member_name.lower() == raw_member or m.pk_mid.lower() == raw_member), db_members)
        if potential_member is not None:
            valid_members.append(potential_member)
        else:

            match = process.extractOne(raw_member, names_and_ids, score_cutoff=50)
            # If we can't match, match will be None. Assign accordingly.
            best_match = match[0] if match else None
            score = match[1] if match else None

            # member = None
            # if best_match is not None:
            #     for m in db_members:
            #         member = m.match_mid_or_name(best_match)
            #         if member is not None:
            #             break

            # member = utils.find(lambda m: (m.match_mid_or_name(best_match) is not None), db_members) if best_match is not None else None
            # best_member_match = member or None

            invalid = InvalidMember(member_name=raw_member, best_match=best_match, score=score)  # Add the member

            # invalid = InvalidMember(member_name=raw_member, best_match=None, score=None)  # This shouldnt be needed...

            invalid_members.append(invalid)

    parsed_members = ParsedMembers(good_members=valid_members, invalid_members=invalid_members)
    return parsed_members
