from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse, JSONResponse
from tortoise.contrib.pydantic import pydantic_model_creator

from airy.services.sectionrole import SectionRolesService, DatabaseSectionRole, HierarchyRoles




async def sectionrole_get(request: Request):
    guild_id = request.path_params["guild_id"]
    role_id = request.path_params["role_id"]
    status, model = await SectionRolesService.get(guild_id, role_id)
    if model:
        sc_role = await SectionRole.from_tortoise_orm(model)
        resp = JSONResponse(sc_role.json(), status_code=status)
    else:
        resp = JSONResponse({}, status_code=status)

    return resp


async def sectionrole_get_all(request: Request):
    guild_id = request.path_params["guild_id"]
    status, models = await SectionRolesService.get_all(guild_id)
    if models:
        sc_roles = [(await SectionRole.from_tortoise_orm(model)).dict() for model in models]
        resp = JSONResponse(sc_roles, status_code=status)
    else:
        resp = JSONResponse({}, status_code=status)

    return resp

