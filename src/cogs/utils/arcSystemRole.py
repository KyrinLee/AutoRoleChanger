"""

"""

from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple
import logging

import discord

from postgresDB import AllowableRoles, DBMember, get_members_by_discord_account, UserSettings, update_system_role

log = logging.getLogger(__name__)



async def create_system_role():
    pass

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

