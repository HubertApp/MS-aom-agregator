import unicodedata
from typing import Optional


def normalize_for_search(value: Optional[str]) -> str:
    """
    Réduit un nom à sa forme comparable : minuscules, sans accents, sans
    espaces ni ponctuation. « Place du Marché » et « place-du-marche »
    tombent ainsi sur la même chaîne.

    MongoDB ne sait pas ignorer les accents dans une `$regex` : la forme
    normalisée est donc stockée à l'ingestion, et la saisie de l'utilisateur
    passe par cette même fonction au moment de la recherche.
    """
    if not value:
        return ""

    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))

    return "".join(char for char in without_accents.casefold() if char.isalnum())
