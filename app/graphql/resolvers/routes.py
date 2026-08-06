from typing import Optional

import strawberry

from app.graphql.types.gtfs import MAX_PAGE_SIZE, PaginatedRoutes, Route


async def resolve_route(info: strawberry.Info, id: strawberry.ID) -> Optional[Route]:
    document = await info.context["route_loader"].load(str(id))
    return Route.from_document(document) if document else None


async def resolve_routes(
    info: strawberry.Info,
    network_id: Optional[strawberry.ID] = None,
    page: int = 1,
    page_size: int = 25,
) -> PaginatedRoutes:
    if page < 1:
        raise ValueError("'page' doit être supérieur ou égal à 1.")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ValueError(f"'pageSize' doit être compris entre 1 et {MAX_PAGE_SIZE}.")

    documents, total_count = await info.context["route_repository"].list_paginated(
        page=page,
        page_size=page_size,
        network_id=str(network_id) if network_id else None,
    )

    return PaginatedRoutes(
        items=[Route.from_document(document) for document in documents],
        total_count=total_count,
        page=page,
        page_size=page_size,
    )
