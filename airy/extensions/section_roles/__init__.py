import hikari
import lightbulb

from airy.models import AiryPlugin, AirySlashContext, errors
from airy.utils import RespondEmbed, FieldPageSource, AiryPages, to_str_permissions, PermissionsErrorEmbed

from airy.services.sectionrole import SectionRolesService, HierarchyRoles, DatabaseSectionRole

from .menu import MenuView
from ...models.bot import Airy

section_role_plugin = AiryPlugin('SectionRoles')
section_role_plugin.add_checks(lightbulb.guild_only)


@section_role_plugin.command()
@lightbulb.add_checks(
    lightbulb.checks.has_guild_permissions(hikari.Permissions.MANAGE_ROLES, hikari.Permissions.MODERATE_MEMBERS),
    lightbulb.checks.bot_has_guild_permissions(hikari.Permissions.MANAGE_ROLES, hikari.Permissions.MODERATE_MEMBERS),
)
@lightbulb.command("sectionrole", "sectionrole",
                   app_command_default_member_permissions=(hikari.Permissions.MODERATE_MEMBERS
                                                           | hikari.Permissions.MANAGE_ROLES),
                   app_command_dm_enabled=False
                   )
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def sectionrole_cmd(_: AirySlashContext):
    pass


@sectionrole_cmd.set_error_handler()
async def sectionrole__error_handler(event: lightbulb.CommandErrorEvent):
    error = event.exception.original  # type: ignore
    if isinstance(error, errors.RoleAlreadyExists):
        embed = RespondEmbed.error("This sectionrole already exists",
                                   description="To edit an existing role use **/sectionrole manage**")
        await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
    elif isinstance(error, errors.RoleDoesNotExist):
        embed = RespondEmbed.error(
            title="This sectionrole does not exists",
            description=f"Try creating a sectionrole with **/sectionrole add**")
        await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)

    if isinstance(error, (hikari.NotFoundError, hikari.ForbiddenError)):
        perms = await check_bot_permissions(event.app, event.context.guild_id)  # type: ignore
        if perms:
            description = to_str_permissions(perms)
            embed = PermissionsErrorEmbed(description=description)
            await event.context.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)


@sectionrole_cmd.child()
@lightbulb.option('role', 'Sectionrole that will be issued when the condition is triggered',
                  type=hikari.OptionType.ROLE)
@lightbulb.option('trigger_role', 'The role, on receipt of which the participant is given an sectionrole ',
                  type=hikari.OptionType.ROLE)
@lightbulb.option('hierarchy', 'Hierarchy of roles on the server', choices=HierarchyRoles.to_choices())
@lightbulb.command("add", "Adds role with subrole and when a user has a subrole, he gets a group role",
                   pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def sectionrole__create(ctx: AirySlashContext, role: hikari.Role, trigger_role: hikari.Role, hierarchy: str):
    await SectionRolesService.create(guild_id=ctx.guild_id,
                                     role_id=role.id,
                                     entries_id=[trigger_role.id],
                                     hierarchy=HierarchyRoles.try_value(hierarchy))

    description = f'{role.mention} (ID: {role.id}) \n>>> **{1}.** {trigger_role.mention} (ID: {trigger_role.id})'
    await ctx.respond(embed=RespondEmbed.success('Successfully created.', description=description))


@sectionrole_cmd.child()
@lightbulb.option('role', 'Sectionrole.', type=hikari.OptionType.ROLE)
@lightbulb.command("manage", "Manages the specified sectionrole.", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def sectionrole__manage(ctx: AirySlashContext, role: hikari.Role):
    view = MenuView(ctx, role)
    await view.initial_send()


@sectionrole_cmd.child()
@lightbulb.command("list", "List all registered sectonroles on this server.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def sectionrole__list(ctx: AirySlashContext):
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

        description = f'{role.mention} (ID: {role.id}) \n **Hierarchy**: `{model.hierarchy.name}` \n>>> '
        description += '\n'.join(entries_description)
        entries.append(hikari.EmbedField(name='\u200b', value=description, inline=True))

    source = FieldPageSource(entries, per_page=2)
    source.embed.title = 'SectionRoles'
    pages = AiryPages(source=source, ctx=ctx, compact=True)
    await pages.send(ctx.interaction, responded=True)


def load(bot: Airy) -> None:
    bot.add_plugin(section_role_plugin)


def unload(bot: Airy) -> None:
    bot.remove_plugin(section_role_plugin)
