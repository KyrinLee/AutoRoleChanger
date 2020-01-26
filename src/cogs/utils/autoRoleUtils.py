"""

"""
import re
import logging
# from collections import namedtuple

from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import tasks, commands
from db import AllowableRoles

if TYPE_CHECKING:
    from discordBot import PNBot

log = logging.getLogger(__name__)


class ParsedRoles(NamedTuple):
    good_roles: List[discord.Role]
    disallowed_roles: List[discord.Role]
    bad_roles: List[str]



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
