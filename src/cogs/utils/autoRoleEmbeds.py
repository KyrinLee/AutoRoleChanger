

from typing import TYPE_CHECKING, List, Optional, Union

import discord

if TYPE_CHECKING:
    from datetime import datetime

    from cogs.utils.autoRoleUtils import ParsedRoles
    from postgresDB import AllowableRoles

# ----- user Add/Remove Roles ----- #

def removed_roles_from_all_members_embed(roles: 'ParsedRoles') -> discord.Embed:

    embed = discord.Embed(title=f"Removed {len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles from all members:")

    if len(roles.good_roles) > 0:
        good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
        embed.add_field(name="Successfully removed:", value=good_roles_msg)

    if len(roles.bad_roles) > 0:
        bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
        suggestion_strs = [f"<@&{role.best_match.id}>" for role in roles.bad_roles if role.best_match is not None]

        suggestion_msg = f"\n\nDid you mean? {', '.join(set(suggestion_strs))}" if len(suggestion_strs) > 0 else ""
        embed.add_field(
            name="Could not find and remove the following (check spelling and capitalization)",
            value=f"{bad_roles_msg}{suggestion_msg}\n\N{ZERO WIDTH SPACE}")

    if len(roles.disallowed_roles) > 0:
        disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])
        embed.add_field(name="These roles are not allowed to be removed by ARC. "
                             "(They *may* still be able to be removed from your account by this servers standard role setting bot or staff):",
                        value=disallowed_roles_msg)

    return embed


def removed_roles_from_some_members_embed(member: discord.Member, roles: 'ParsedRoles') -> discord.Embed:

    embed = discord.Embed(title=f"Removed {len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles from {member['member_name']}:")

    if len(roles.good_roles) > 0:
        good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
        embed.add_field(name="Successfully removed:", value=good_roles_msg)

    if len(roles.bad_roles) > 0:
        bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
        suggestion_strs = [f"<@&{role.best_match.id}>" for role in roles.bad_roles if role.best_match is not None]
        suggestion_msg = f"\n\nDid you mean? {', '.join(set(suggestion_strs))}" if len(suggestion_strs) > 0 else ""
        embed.add_field(
            name="Could not find and remove the following (check spelling and capitalization):",
            value=f"{bad_roles_msg}{suggestion_msg}\n\N{ZERO WIDTH SPACE}")

    if len(roles.disallowed_roles) > 0:
        disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])
        embed.add_field(name="These roles are not allowed to be removed by ARC. "
                             "(They *may* still be able to be removed from your account by this servers standard role setting bot or staff):",
                        value=disallowed_roles_msg)
    return embed


def allowable_roles_embed(allowable_roles: Optional['AllowableRoles']) -> discord.Embed:
    embed = discord.Embed()
    embed.set_author(name=f"Auto changeable roles")

    if allowable_roles is not None:
        roles_msg = ", ".join([f"<@&{role_id}>" for role_id in allowable_roles.role_ids])
    else:
        roles_msg = "No roles are configured!"

    embed.description = roles_msg


def added_roles_to_all_members_embed(roles: 'ParsedRoles') -> discord.Embed:

    embed = discord.Embed(title=f"Added {len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles to all members:")

    if len(roles.good_roles) > 0:
        good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
        embed.add_field(name="Successfully added:", value=good_roles_msg)

    if len(roles.bad_roles) > 0:
        bad_roles_msg = ", ".join([f"`{role}`" for role in roles.bad_roles])
        suggestion_strs = [f"<@&{role.best_match.id}>" for role in roles.bad_roles if role.best_match is not None]
        suggestion_msg = f"\n\nDid you mean? {', '.join(set(suggestion_strs))}" if len(suggestion_strs) > 0 else ""
        embed.add_field(
            name="Could not find and add the following (check spelling and capitalization):",
            value=f"{bad_roles_msg}{suggestion_msg}\n\N{ZERO WIDTH SPACE}")

    if len(roles.disallowed_roles) > 0:
        disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])
        embed.add_field(name="These roles are not allowed to be set by ARC. "
                             "(They *may* still be able to be statically applied to your account by this servers standard role setting bot or staff):",
                        value=disallowed_roles_msg)
    return embed


def added_roles_to_some_members_embed(member: discord.Member, roles: 'ParsedRoles') -> discord.Embed:

    embed = discord.Embed(title=f"{len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles added to {member['member_name']}:")

    if len(roles.good_roles) > 0:
        good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
        embed.add_field(name="Successfully added:", value=good_roles_msg)

    if len(roles.bad_roles) > 0:
        bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
        suggestion_strs = [f"<@&{role.best_match.id}>" for role in roles.bad_roles if role.best_match is not None]
        suggestion_msg = f"\n\nDid you mean? {', '.join(set(suggestion_strs))}" if len(suggestion_strs) > 0 else ""
        embed.add_field(
            name="Could not find and add the following (check spelling and capitalization):",
            value=f"{bad_roles_msg}{suggestion_msg}\n\N{ZERO WIDTH SPACE}")

    if len(roles.disallowed_roles) > 0:
        disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])
        embed.add_field(name="These roles are not allowed to be set by ARC. "
                             "(They *may* still be able to be statically applied to your account by this servers standard role setting bot or staff):",
                        value=disallowed_roles_msg)

    return embed





