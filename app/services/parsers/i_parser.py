from abc import ABC, abstractmethod
from typing import List


class IParser(ABC):
    """
    Contrat commun pour tous les parseurs de données de mobilité.
    """

    @abstractmethod
    async def parse(self, directory_path: str):
        """
        Lit les fichiers dans le dossier fourni et retourne une liste de données standardisées.
        """
        pass