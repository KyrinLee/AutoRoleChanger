"""

"""
import re
import logging
# from collections import namedtuple

from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import tasks, commands
from postgresDB import AllowableRoles, UserSettings, update_system_role

if TYPE_CHECKING:
    from discordBot import PNBot

log = logging.getLogger(__name__)


class GuildSettings(NamedTuple):
    guild_id: int
    name_change: bool
    role_change: bool
    log_channel: int
    name_logging: bool
    role_logging: bool
    custom_roles: bool


class ParsedRoles(NamedTuple):
    good_roles: List[discord.Role]
    disallowed_roles: List[discord.Role]
    bad_roles: List[str]


async def get_system_role(pool, guild: discord.Guild, system_role_id: Optional[int], system_role_enabled: bool,
                          system_id: str, system_name: str, fronters_favorite_color: Optional[str]) -> Optional[discord.Role]:

    system_role = None
    if system_role_enabled:
        # Try to get the system role from d.py
        if system_role_id is not None:
            system_role: Optional[discord.Role] = guild.get_role(system_role_id)

        # Convert the system members favorite color to a discord.Color
        color = hex_to_color(fronters_favorite_color) if fronters_favorite_color is not None else discord.Color.default()

        # Get the position of the bots managed role
        # I'm sure you can only have one managed role. but just incase lets revers the list and grab the highest role
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
                log.warning(f"Creating new role: {system_name}")
            except discord.Forbidden:
                return None  # Todo do something other than silently fail.
            await update_system_role(pool, system_id, system_role.id, system_role_enabled)

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
    for raw_role in raw_roles:
        try:
            # add identifiable roles to the good list
            # Todo: Try to match up Snowflake like raw roles to the roles in self.allowable_roles and bypass the RoleConverter on success.
            potential_role: discord.Role = await commands.RoleConverter().convert(ctx, raw_role.strip())
            if allowed_roles is None or allowed_roles.is_allowed(potential_role):
                good_roles.append(potential_role)
            else:
                disallowed_roles.append(potential_role)
        except commands.errors.BadArgument:
            # Role could not be found. Add to bad list.
            bad_roles.append(raw_role)

    parsed_roles = ParsedRoles(good_roles=good_roles, bad_roles=bad_roles, disallowed_roles=disallowed_roles)
    return parsed_roles
