from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IParser(ABC):
    """
    Contrat commun pour tous les parseurs de données de mobilité.
    """

    @abstractmethod
    async def parse(self, directory_path: str, network_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Lit les fichiers dans le dossier fourni et retourne les données
        standardisées, sous la forme d'un dictionnaire
        {nom_de_collection: [document, ...]}.

        Le `network_id` identifie le réseau (AOM) en cours d'ingestion. Il est
        utilisé pour préfixer les identifiants du flux et garantir leur unicité
        une fois les données de plusieurs AOM agrégées dans les mêmes collections.
        """
        pass
