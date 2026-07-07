from pathlib import Path

from common.config import config


class Repository:

    def __init__(self):

        self._servers = []

        self.server_file = Path(
            config.advanced.servers_file
        )

    def load_servers(self):

        if not self.server_file.exists():
            return []

        with self.server_file.open(
            "r",
            encoding="utf-8",
        ) as file:

            self._servers = [
                line.strip()
                for line in file
                if line.strip()
            ]

        return self._servers


    @property
    def servers(self):

        return self._servers