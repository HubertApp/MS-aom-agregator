"""
Modèles Pydantic de validation / normalisation des données GTFS.

Rôle : ces classes sont la couche d'entrée du pipeline d'ingestion. Elles ne
sont PAS exposées via GraphQL (ça, c'est le rôle des types Strawberry dans
app/graphql/types/gtfs_data.py) : elles servent uniquement à valider et à
formatter chaque ligne des fichiers .txt d'un flux GTFS avant insertion en base.

Deux mécanismes importants ici :

1. Les alias (`Field(alias="stop_lat")`) portent le nom EXACT de la colonne dans
   le fichier GTFS. Conséquence : on peut passer directement le dict brut sorti
   de `csv.DictReader` à `model_validate()`, sans aucun remapping manuel.
   Le nom du champ Python (`lat`) est celui utilisé au `model_dump()`, donc
   c'est lui qui finit comme nom de clé dans MongoDB.

2. Le namespacing des identifiants (`NamespacedId`). Chaque flux GTFS numérote
   ses objets indépendamment des autres : deux AOM différentes peuvent très bien
   avoir toutes les deux un `stop_id = "1"`. Comme on agrège plusieurs AOM dans
   les mêmes collections Mongo, on préfixe chaque identifiant (et chaque
   référence vers un identifiant) par le `network_id` du réseau en cours
   d'ingestion, ce qui donne des identifiants du type "68f3...c1:1".
   Le `network_id` est transmis à la validation via le contexte :

       Stop.model_validate(row, context={"network_id": "68f3...c1"})
"""

from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationInfo


# --------------------------------------------------------------------------- #
# Validateurs réutilisables
# --------------------------------------------------------------------------- #

def _blank_to_none(v: Any) -> Any:
    """
    Le GTFS étant du CSV, une valeur absente arrive sous la forme d'une chaîne
    vide et non d'un None. Sans ce nettoyage, Pydantic refuserait "" pour un
    champ int/float optionnel.
    """
    if isinstance(v, str) and not v.strip():
        return None
    return v


def _blank_to_zero(v: Any) -> Any:
    """Variante de _blank_to_none pour les coordonnées, qui ne sont pas Optional."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return 0.0
    return v


def _namespace(v: Any, info: ValidationInfo) -> Any:
    """
    Préfixe un identifiant GTFS par le network_id passé dans le contexte de
    validation, afin de le rendre unique à l'échelle de toutes les AOM agrégées.
    Sans network_id dans le contexte, la valeur est laissée telle quelle (utile
    pour les tests unitaires).
    """
    if v is None:
        return None

    v = str(v).strip()
    if not v:
        return None

    network_id = (info.context or {}).get("network_id")
    return f"{network_id}:{v}" if network_id else v


def _namespace_agency(v: Any, info: ValidationInfo) -> Any:
    """
    Cas particulier de `agency_id` : la spec GTFS le rend facultatif quand le
    flux ne contient qu'un seul opérateur, et beaucoup de flux français ne le
    renseignent donc pas. On retombe alors sur "default" — mais namespacé, ce
    qui garantit que le "default" de l'AOM A ne se confond pas avec celui de
    l'AOM B, et que la jointure routes -> agency reste cohérente.
    """
    if v is None or (isinstance(v, str) and not v.strip()):
        v = "default"
    return _namespace(v, info)


# Identifiant obligatoire, namespacé (clé primaire d'une entité GTFS).
NamespacedId = Annotated[str, BeforeValidator(_namespace)]
# Référence facultative vers un identifiant d'une autre entité.
OptionalNamespacedId = Annotated[Optional[str], BeforeValidator(_namespace)]
# Référence vers agency_id, avec repli sur "default".
AgencyRef = Annotated[str, BeforeValidator(_namespace_agency)]

OptStr = Annotated[Optional[str], BeforeValidator(_blank_to_none)]
OptInt = Annotated[Optional[int], BeforeValidator(_blank_to_none)]
OptFloat = Annotated[Optional[float], BeforeValidator(_blank_to_none)]
Coordinate = Annotated[float, BeforeValidator(_blank_to_zero)]


class GTFSBase(BaseModel):
    """
    Configuration commune à tous les modèles GTFS.

    - populate_by_name : accepte aussi bien le nom de colonne GTFS (l'alias) que
      le nom du champ Python, pratique pour instancier un modèle à la main dans
      un test.
    - extra="ignore" : les flux GTFS contiennent souvent des colonnes optionnelles
      ou non standard qu'on ne modélise pas ; on les ignore au lieu d'échouer.
    - validate_default : indispensable pour que les valeurs par défaut (ex.
      agency_id="default") passent elles aussi par le namespacing.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        validate_default=True,
        str_strip_whitespace=True,
    )


# --------------------------------------------------------------------------- #
# agency.txt
# --------------------------------------------------------------------------- #

class Agency(GTFSBase):
    agency_id: AgencyRef = Field(default="default", alias="agency_id")
    name: OptStr = Field(default=None, alias="agency_name")
    url: OptStr = Field(default=None, alias="agency_url")
    timezone: OptStr = Field(default=None, alias="agency_timezone")
    lang: OptStr = Field(default=None, alias="agency_lang")
    phone: OptStr = Field(default=None, alias="agency_phone")
    fare_url: OptStr = Field(default=None, alias="agency_fare_url")
    email: OptStr = Field(default=None, alias="agency_email")


# --------------------------------------------------------------------------- #
# stops.txt
# --------------------------------------------------------------------------- #

class Stop(GTFSBase):
    stop_id: NamespacedId = Field(alias="stop_id")
    code: OptStr = Field(default=None, alias="stop_code")
    name: OptStr = Field(default=None, alias="stop_name")
    description: OptStr = Field(default=None, alias="stop_desc")
    # lat/lon sont recomposés en un point GeoJSON par le parser, pour permettre
    # l'index géospatial (2dsphere) côté MongoDB.
    lat: Coordinate = Field(default=0.0, alias="stop_lat")
    lon: Coordinate = Field(default=0.0, alias="stop_lon")
    zone_id: OptStr = Field(default=None, alias="zone_id")
    url: OptStr = Field(default=None, alias="stop_url")
    # 0 = arrêt/quai, 1 = station, 2 = accès, 3 = noeud générique, 4 = zone d'embarquement
    location_type: OptInt = Field(default=0, alias="location_type")
    # Référence vers un autre stop_id : doit donc être namespacée elle aussi.
    parent_station: OptionalNamespacedId = Field(default=None, alias="parent_station")
    timezone: OptStr = Field(default=None, alias="stop_timezone")
    # 0 = inconnu, 1 = accessible, 2 = non accessible
    wheelchair_boarding: OptInt = Field(default=None, alias="wheelchair_boarding")
    platform_code: OptStr = Field(default=None, alias="platform_code")


# --------------------------------------------------------------------------- #
# routes.txt
# --------------------------------------------------------------------------- #

class Route(GTFSBase):
    route_id: NamespacedId = Field(alias="route_id")
    agency_id: AgencyRef = Field(default="default", alias="agency_id")
    short_name: OptStr = Field(default=None, alias="route_short_name")
    long_name: OptStr = Field(default=None, alias="route_long_name")
    description: OptStr = Field(default=None, alias="route_desc")
    # 0 = tram, 1 = métro, 2 = train, 3 = bus, 4 = ferry... (spec GTFS route_type)
    type: OptInt = Field(default=3, alias="route_type")
    url: OptStr = Field(default=None, alias="route_url")
    color: OptStr = Field(default=None, alias="route_color")
    text_color: OptStr = Field(default=None, alias="route_text_color")
    sort_order: OptInt = Field(default=None, alias="route_sort_order")


# --------------------------------------------------------------------------- #
# trips.txt
# --------------------------------------------------------------------------- #

class Trip(GTFSBase):
    trip_id: NamespacedId = Field(alias="trip_id")
    route_id: NamespacedId = Field(alias="route_id")
    service_id: NamespacedId = Field(alias="service_id")
    headsign: OptStr = Field(default=None, alias="trip_headsign")
    short_name: OptStr = Field(default=None, alias="trip_short_name")
    direction_id: OptInt = Field(default=0, alias="direction_id")
    # block_id est un identifiant textuel dans la spec, pas un entier.
    block_id: OptStr = Field(default=None, alias="block_id")
    # Optionnel dans la spec : un trajet n'est pas obligé d'avoir un tracé.
    shape_id: OptionalNamespacedId = Field(default=None, alias="shape_id")
    # 0/1/2 dans la spec, donc un int et non un booléen.
    wheelchair_accessible: OptInt = Field(default=0, alias="wheelchair_accessible")
    bikes_allowed: OptInt = Field(default=0, alias="bikes_allowed")


# --------------------------------------------------------------------------- #
# stop_times.txt
# --------------------------------------------------------------------------- #

class StopTime(GTFSBase):
    trip_id: NamespacedId = Field(alias="trip_id")
    stop_id: NamespacedId = Field(alias="stop_id")
    # Horaires GTFS bruts : ils peuvent dépasser 24:00:00 (ex. "25:30:00" pour un
    # passage après minuit rattaché au service de la veille). Ni `time` ni
    # `datetime` ne savent représenter ça, on les conserve donc en chaîne.
    arrival_time: OptStr = Field(default=None, alias="arrival_time")
    departure_time: OptStr = Field(default=None, alias="departure_time")
    stop_sequence: OptInt = Field(default=0, alias="stop_sequence")
    stop_headsign: OptStr = Field(default=None, alias="stop_headsign")
    pickup_type: OptInt = Field(default=0, alias="pickup_type")
    drop_off_type: OptInt = Field(default=0, alias="drop_off_type")
    shape_dist_traveled: OptFloat = Field(default=None, alias="shape_dist_traveled")
    timepoint: OptInt = Field(default=None, alias="timepoint")


# --------------------------------------------------------------------------- #
# calendar.txt
# --------------------------------------------------------------------------- #

class Calendar(GTFSBase):
    service_id: NamespacedId = Field(alias="service_id")
    # 0 ou 1 dans la spec ; on garde l'int pour rester aligné sur le type
    # Strawberry exposé en GraphQL.
    monday: OptInt = Field(default=0, alias="monday")
    tuesday: OptInt = Field(default=0, alias="tuesday")
    wednesday: OptInt = Field(default=0, alias="wednesday")
    thursday: OptInt = Field(default=0, alias="thursday")
    friday: OptInt = Field(default=0, alias="friday")
    saturday: OptInt = Field(default=0, alias="saturday")
    sunday: OptInt = Field(default=0, alias="sunday")
    # Dates au format YYYYMMDD : conservées en chaîne, comme dans le flux.
    start_date: OptStr = Field(default=None, alias="start_date")
    end_date: OptStr = Field(default=None, alias="end_date")


# --------------------------------------------------------------------------- #
# calendar_dates.txt
# --------------------------------------------------------------------------- #

class CalendarDate(GTFSBase):
    service_id: NamespacedId = Field(alias="service_id")
    date: OptStr = Field(default=None, alias="date")
    # 1 = service ajouté ce jour-là, 2 = service retiré ce jour-là
    exception_type: OptInt = Field(default=None, alias="exception_type")


# --------------------------------------------------------------------------- #
# shapes.txt
# --------------------------------------------------------------------------- #

class Shape(GTFSBase):
    shape_id: NamespacedId = Field(alias="shape_id")
    pt_lat: Coordinate = Field(default=0.0, alias="shape_pt_lat")
    pt_lon: Coordinate = Field(default=0.0, alias="shape_pt_lon")
    pt_sequence: OptInt = Field(default=0, alias="shape_pt_sequence")
    shape_dist_traveled: OptFloat = Field(default=None, alias="shape_dist_traveled")


# --------------------------------------------------------------------------- #
# transfers.txt
# --------------------------------------------------------------------------- #

class Transfer(GTFSBase):
    from_stop_id: NamespacedId = Field(alias="from_stop_id")
    to_stop_id: NamespacedId = Field(alias="to_stop_id")
    transfer_type: OptInt = Field(default=0, alias="transfer_type")
    # Durée minimale de correspondance, exprimée en secondes dans la spec.
    min_transfer_time: OptInt = Field(default=None, alias="min_transfer_time")
