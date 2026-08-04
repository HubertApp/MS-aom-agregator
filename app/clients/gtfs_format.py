import asyncio
import os
import shutil
import zipfile

import httpx
import aiofiles

from app.clients.i_format_tn import IFormatTN


class GTFSFormat(IFormatTN):
    """
    Implémentation de IFormatTN pour la gestion des fichiers GTFS. Leur téléchargement, jusqu'a leur suppression
    """

    def __init__(self):
        self._downloaded_file_path: str | None = None

    async def download(self, download_dir: str = None, url: str = None) -> None:
        if not download_dir or not url:
            raise ValueError("Les paramètres 'download_dir' et 'url' sont requis.")

        os.makedirs(download_dir, exist_ok=True)

        zip_name = f"gtfs_{os.urandom(4).hex()}.zip"
        self._downloaded_file_path = os.path.join(download_dir, zip_name)

        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                async with aiofiles.open(self._downloaded_file_path, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        await f.write(chunk)

    async def extract(self, extract_dir: str = None, get_dir: str = None) -> None:
        if not extract_dir:
            raise ValueError("Le paramètre 'extract_dir' est requis.")

        source_file = get_dir or self._downloaded_file_path

        if not source_file or not os.path.exists(source_file):
            raise FileNotFoundError(f"Le fichier ZIP source est introuvable : {source_file}")

        await asyncio.to_thread(self._extract_zip_sync, source_file, extract_dir)

    def _extract_zip_sync(self, zip_path: str, extract_dir: str) -> None:
        """Méthode utilitaire synchrone pour l'extraction."""
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

    async def clean(self) -> None:
        """Nettoie spécifiquement le fichier ZIP téléchargé par cette instance."""
        if self._downloaded_file_path:
            await self.delete_file(self._downloaded_file_path)
            self._downloaded_file_path = None

    async def delete_file(self, file_name: str = None) -> None:
        if not file_name:
            raise ValueError("Le paramètre 'file_name' est requis.")

        if os.path.exists(file_name):
            await asyncio.to_thread(os.remove, file_name)

    async def delete_all_files(self, dir_to_clean: str = None) -> None:
        if not dir_to_clean:
            raise ValueError("Le paramètre 'dir_to_clean' est requis.")

        if os.path.exists(dir_to_clean):
            await asyncio.to_thread(shutil.rmtree, dir_to_clean)
            os.makedirs(dir_to_clean, exist_ok=True)