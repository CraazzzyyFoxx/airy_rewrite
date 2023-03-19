import hikari
import lightbulb

from starlette import status as star_status

from airy.models.bot import Airy
from airy.models.plugin import AiryPlugin
from airy.models.context import AirySlashContext
from airy.utils import RespondEmbed, FieldPageSource, AiryPages
from airy.services.sectionrole import SectionRolesService, HierarchyRoles

from .menu import MenuView

section_role_plugin = AiryPlugin('SectionRoles')
section_role_plugin.add_checks(lightbulb.guild_only,
                               lightbulb.checks.has_guild_permissions(hikari.Permissions.MANAGE_ROLES,
                                                                      hikari.Permissions.MODERATE_MEMBERS),
                               lightbulb.checks.bot_has_guild_permissions(hikari.Permissions.MANAGE_ROLES,
                                                                          hikari.Permissions.MODERATE_MEMBERS)
                               )


@section_role_plugin.command()
@lightbulb.command("sectionrole", "sectionrole",
                   app_command_default_member_permissions=(hikari.Permissions.MODERATE_MEMBERS
                                                           | hikari.Permissions.MANAGE_ROLES),
                   app_command_dm_enabled=False
                   )
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def sectionrole_cmd(_: AirySlashContext):
    pass


@sectionrole_cmd.child()
@lightbulb.option('role', 'Sectionrole that will be issued when the condition is triggered',
                  type=hikari.OptionType.ROLE)
@lightbulb.option('trigger_role', 'The role, on receipt of which the participant is given an sectionrole ',
                  type=hikari.OptionType.ROLE)
@lightbulb.option('hierarchy', 'Hierarchy of roles on the server', choices=HierarchyRoles.to_choices())
@lightbulb.command("add", "Adds role with subrole and when a user has a subrole, he gets a group role",
                   pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def sectionrole_create(ctx: AirySlashContext, role: hikari.Role, trigger_role: hikari.Role, hierarchy: str):
    status, model = await SectionRolesService.create(guild_id=ctx.guild_id,
                                                     role_id=role.id,
                                                     entries_id=[trigger_role.id],
                                                     hierarchy=HierarchyRoles.try_value(hierarchy)
                                                     )

    if status == star_status.HTTP_400_BAD_REQUEST:
        embed = RespondEmbed.error("This sectionrole already exists",
                                   description="To edit an existing role use **/sectionrole manage**")
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
    else:
        description = f'{role.mention} (ID: {role.id}) \n>>> **{1}.** {trigger_role.mention} (ID: {trigger_role.id})'
        await ctx.respond(embed=RespondEmbed.success('Successfully created.', description=description))


@sectionrole_cmd.child()
@lightbulb.option('role', 'Sectionrole.', type=hikari.OptionType.ROLE)
@lightbulb.command("manage", "Manages the specified sectionrole.", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def sectionrole_manage(ctx: AirySlashContext, role: hikari.Role):
    status, model = await SectionRolesService.get(ctx.guild_id, role.id)

    if status == star_status.HTTP_400_BAD_REQUEST:
        embed = RespondEmbed.error(
            title="This sectionrole does not exists",
            description=f"Try creating a sectionrole with **/sectionrole add**")
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
    else:
        view = MenuView(ctx, model)
        await view.initial_send()


@sectionrole_cmd.child()
@lightbulb.command("list", "List all registered section roles on this server.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def sectionrole_list(ctx: AirySlashContext):
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    status, models = await SectionRolesService.get_all(ctx.guild_id)

    if star_status.HTTP_404_NOT_FOUND == status:
        return await ctx.respond(embed=RespondEmbed.error("Section roles are missing"))

    entries = []
    for model in models:
        description = [
            f'<@&{model.role_id}> (ID: {model.role_id})',
            f'**Hierarchy**: `{model.hierarchy.name}`',
            '>>> '
        ]

        for index, entry in enumerate(model.entries, 1):
            description.append(f"**{index}.** <@&{entry.entry_id}> (ID: {entry.entry_id})")
        entries.append(hikari.EmbedField(name='\u200b', value="\n".join(description), inline=True))

    source = FieldPageSource(entries, per_page=2)
    source.embed.title = 'Section Roles'
    pages = AiryPages(source=source, ctx=ctx, compact=True)
    await pages.send(ctx.interaction, responded=True)


def load(bot: Airy) -> None:
    bot.add_plugin(section_role_plugin)


def unload(bot: Airy) -> None:
    bot.remove_plugin(section_role_plugin)
