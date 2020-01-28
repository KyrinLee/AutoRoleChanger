import postgresDB as pdb
import db
import logging

log = logging.getLogger(__name__)


async def add_new_system(pool):

    # test w/ Token
    await pdb.add_new_system(pool, pk_sid="abcde", system_name="Test System", current_fronter="hhhhh", pk_system_tag="- Test -", pk_token="aBcDeFgHiJkLmNoPqRsTuVwXyZ")

    # test w/o token
    await pdb.add_new_system(pool, pk_sid="zyxwv", system_name="No tokens here", current_fronter="asdfg", pk_system_tag="- pfft -")

    # test duplicate system
    await pdb.add_new_system(pool, pk_sid="zyxwv", system_name="dup row", current_fronter="dup row", pk_system_tag="dup row")


async def add_linked_dis_account(pool):

    await pdb.add_linked_discord_account(pool, "abcde", 123456789)

    await pdb.add_linked_discord_account(pool, "abcde", 987654321)

    await pdb.add_linked_discord_account(pool, "zyxwv", 555555555)


# FIXME: BREAKING CHANGE! DICTIONARY ENTRIES CHANGED!!!
async def get_system_id_by_discord_account(pool):

    system_id = await pdb.get_system_id_by_discord_account(pool, dis_uid=123456789)

    log.info(system_id)


async def update_system_by_pk_sid(pool):

    await pdb.update_system_by_pk_sid(pool, pk_sid="abcde", system_name="Updated System", system_tag="-Test updated-")

    # No exceptions when UPDATE nonexistant roes.
    await pdb.update_system_by_pk_sid(pool, pk_sid="ujnhy", system_name="nonexistant System", system_tag="-Test nonexistant-")


async def add_new_member(pool):

    await pdb.add_new_member(pool, pk_sid="abcde", pk_mid="hhhhh", member_name="catgirl", fronting=True)
    await pdb.add_new_member(pool, pk_sid="abcde", pk_mid="abcda", member_name="test Mem 2", fronting=False)

    await pdb.add_new_member(pool, pk_sid="zyxwv", pk_mid="zyxwa", member_name="S2M1", fronting=False)
    await pdb.add_new_member(pool, pk_sid="zyxwv", pk_mid="zyxwa", member_name="Dup Test", fronting=False)

    await pdb.add_new_member(pool, pk_sid="zyxwv", pk_mid="zyxwb", member_name="Member for delete test", fronting=True)


async def delete_member(pool):
    # await add_new_member(pool)

    await pdb.delete_member(pool, pk_sid="zyxwv", pk_mid="zyxwb")


async def update_member(pool):

    # await pdb.update_member(pool, pk_sid="abcde", pk_mid="abcdb", member_name="Upsertd Mem", fronting=False)
    await pdb.update_member(pool, pk_sid="abcde", pk_mid="abcda", member_name="Updated Mem", fronting=True)


async def get_members_by_discord_account(pool):

    members = await pdb.get_members_by_discord_account(pool, discord_user_id=123456789)

    log.info(members)


async def get_fronting_members_by_discord_account(pool):

    fronting_members = await pdb.get_fronting_members_by_discord_account(pool, discord_user_id=123456789)

    log.info(fronting_members)


async def get_member_by_mid_and_discord_account(pool):

    member = await pdb.get_member_by_mid_and_discord_account(pool, pk_mid="hhhhh", discord_user_id=123456789)

    log.info(member)


async def get_member_by_name_and_discord_account(pool):

    member = await pdb.get_member_by_name_and_discord_account(pool, member_name="cat", discord_user_id=123456789)

    log.info(member)


async def get_member_fuzzy(pool):

    member = await pdb.get_member_fuzzy(pool, discord_user_id=123456789, search_value="hhhhh")

    log.info(member)


async def add_role_to_member(pool):

    await pdb.add_role_to_member(pool, guild_id=111, pk_mid="abcda", pk_sid="abcde", role_id=12345)
    await pdb.add_role_to_member(pool, guild_id=111, pk_mid="abcda", pk_sid="abcde", role_id=12341)
    await pdb.add_role_to_member(pool, guild_id=111, pk_mid="abcda", pk_sid="abcde", role_id=12342)
    await pdb.add_role_to_member(pool, guild_id=111, pk_mid="abcda", pk_sid="abcde", role_id=12343)
    await pdb.add_role_to_member(pool, guild_id=111, pk_mid="abcda", pk_sid="abcde", role_id=12344)
    await pdb.add_role_to_member(pool, guild_id=111, pk_mid="abcda", pk_sid="abcde", role_id=12340)

    await pdb.add_role_to_member(pool, guild_id=111, pk_mid="hhhhh", pk_sid="abcde", role_id=56789)
    await pdb.add_role_to_member(pool, guild_id=111, pk_mid="hhhhh", pk_sid="abcde", role_id=12345)


async def remove_role_from_member(pool):
    await pdb.remove_role_from_member(pool, guild_id=111, pk_mid="abcda", role_id=12345)
    await pdb.remove_role_from_member(pool, guild_id=111, pk_mid="abcda", role_id=12346)


async def get_roles_for_member_by_guild(pool):

    member_roles = await pdb.get_roles_for_member_by_guild(pool, guild_id=121, pk_mid="abcda")

    log.info(member_roles)


async def add_allowable_role(pool):

    # await pdb.add_allowable_role(pool, guild_id=110, role_id=12345)
    await pdb.add_allowable_role(pool, guild_id=111, role_id=12345)
    await pdb.add_allowable_role(pool, guild_id=111, role_id=12346)
    await pdb.add_allowable_role(pool, guild_id=111, role_id=12347)


async def get_allowable_roles(pool):
    roles = await pdb.get_allowable_roles(pool, guild_id=1110)

    log.info(roles)


async def remove_allowable_role(pool):

    await pdb.remove_allowable_role(pool, guild_id=111, role_id=12347)


async def update_user_setting(pool):

    # await pdb.update_user_setting(pool, pk_sid="abcde", guild_id=111, name_change=False, role_change=False)
    # await pdb.update_user_setting(pool, pk_sid="abcde", guild_id=999, name_change=False, role_change=False)

    await pdb.update_user_setting(pool, pk_sid="abcde", guild_id=999, name_change=True, role_change=False)


async def test_db_functions(pool):

    user_settings = await pdb.get_user_settings_from_discord_id(pool, discord_user_id=123456789, guild_id=909)

    log.info(user_settings)


#
# async def test_db_functions(pool):
#     pass
#
#
# async def test_db_functions(pool):
#     pass
