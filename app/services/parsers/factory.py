from app.services.parsers.gtfs_parser import GTFSParser
from app.services.parsers.i_parser import IParser


class ParserFactory:
    @staticmethod
    def get_parser(format_type: str) -> IParser:
        format_type = format_type.upper()

        if format_type == "GTFS":
            return GTFSParser()
        else:
            raise ValueError(f"Le format de données '{format_type}' n'est pas supporté.")