# app/clients/i_format_tn.py
from abc import ABC, abstractmethod



class IFormatTN(ABC):

    @abstractmethod
    async def download(self, download_dir: str = None, url: str = None) -> None:
        pass

    @abstractmethod
    async def extract(self, extract_dir: str = None, get_dir: str = None) -> None:
        pass

    @abstractmethod
    async def clean(self) -> None:
        pass

    @abstractmethod
    async def delete_file(self, file_name: str = None) -> None:
        pass

    @abstractmethod
    async def delete_all_files(self, dir_to_clean: str = None) -> None:
        pass