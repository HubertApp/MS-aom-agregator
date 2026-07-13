from typing import List

import strawberry

from app.graphql.inputs.registred_transit_networks import TransitNetworkInput
from app.graphql.inputs.transit_network_datasets import DatasetsInput
from app.graphql.resolvers.registred_transit_networks import resolve_get_registred_transit_network
from app.graphql.resolvers.system import resolve_status
from app.graphql.types.registred_transit_network import TransitNetworks, PaginatedTransitNetworks
from app.graphql.types.gtfs_data import StandardDatasets
from app.graphql.resolvers.transit_network_datasets import resolve_search_datasets


@strawberry.type
class Query:
    search_transit_networks_datasets: List[StandardDatasets] = strawberry.field(resolver=resolve_search_datasets)
    get_registred_transit_networks: PaginatedTransitNetworks = strawberry.field(resolver=resolve_get_registred_transit_network)
    status: str = strawberry.field(resolver=resolve_status)


@strawberry.type
class Mutation:
    pass

schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation
)
