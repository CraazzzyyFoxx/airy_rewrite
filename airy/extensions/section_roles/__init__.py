import hikari
import lightbulb

from airy.models import AiryPlugin, AirySlashContext, HierarchyRoles, DatabaseSectionRole
from airy.utils import RespondEmbed, FieldPageSource, AiryPages

from airy.services.sectionroles import SectionRolesService

from .menu import MenuView

section_role_plugin = AiryPlugin('SectionRoles')


@section_role_plugin.command()
@lightbulb.add_checks(
    lightbulb.checks.has_guild_permissions(hikari.Permissions.MANAGE_ROLES, hikari.Permissions.MODERATE_MEMBERS),
    lightbulb.checks.bot_has_guild_permissions(hikari.Permissions.MANAGE_ROLES, hikari.Permissions.MODERATE_MEMBERS),
)
@lightbulb.command("sectionrole")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def group_role_(_: AirySlashContext):
    pass


@group_role_.child()
@lightbulb.option('role', 'Sectionrole that will be issued when the condition is triggered ',
                  type=hikari.OptionType.ROLE)
@lightbulb.option('trigger_role', 'The role, on receipt of which the participant is given an sectionrole ',
                  type=hikari.OptionType.ROLE)
@lightbulb.option('hierarchy', 'Hierarchy of roles on the server', choices=HierarchyRoles.to_choices())
@lightbulb.command("create", "Creates role with subrole and when a user has a subrole, he gets a group role",
                   pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def group_role_create(ctx: AirySlashContext, role: hikari.Role, trigger_role: hikari.Role, hierarchy: str):
    resp = await SectionRolesService.create(guild_id=ctx.guild_id,
                                            role_id=role.id,
                                            entries_id=[trigger_role.id],
                                            hierarchy=HierarchyRoles.try_value(hierarchy))

    if resp is None:
        await ctx.respond(embed=RespondEmbed.error("The specified group role already exists",
                                                   description="To edit an existing role use **/rolegroup manage**"),
                          flags=hikari.MessageFlag.EPHEMERAL)

    else:
        description = f'{role.mention} (ID: {role.id}) \n>>> **{1}.** {trigger_role.mention} (ID: {trigger_role.id})'
        await ctx.respond(embed=RespondEmbed.success('Successfully created.', description=description))


@group_role_.child()
@lightbulb.option('role', 'Sectionrole.', type=hikari.OptionType.ROLE)
@lightbulb.command("manage", "Manages the specified sectionrole.", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def group_role_manage(ctx: AirySlashContext, role: hikari.Role):
    view = MenuView(ctx, role)
    await view.initial_send()


@group_role_.child()
@lightbulb.command("list", "List all registered sectonroles on this server.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def group_role_list(ctx: AirySlashContext):
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    models = await DatabaseSectionRole.fetch_all(ctx.guild_id)
    if len(models) == 0:
        return await ctx.respond(embed=RespondEmbed.error("Sectionroles are missing"))
    entries = []
    for model in models:
        entries_description = []
        role = ctx.bot.cache.get_role(model.role_id)
        for index, entry in enumerate(model.entries, 1):
            entry_role = ctx.bot.cache.get_role(entry.entry_id)
            entries_description.append(f"**{index}.** {entry_role.mention} (ID: {entry_role.id})")

        description = f'{role.mention} (ID: {role.id}) \n>>> '
        description += '\n'.join(entries_description)
        entries.append(hikari.EmbedField(name='\u200b', value=description, inline=True))

    source = FieldPageSource(entries, per_page=2)
    source.embed.title = 'Group Roles'
    pages = AiryPages(source=source, ctx=ctx, compact=True)
    await pages.send(ctx.interaction, responded=True)
