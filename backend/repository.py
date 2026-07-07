from pathlib import Path


class Repository:

    def __init__(self):
        self._servers = []

    def load_servers(self, filename="servers.txt"):

        path = Path(filename)

        if not path.exists():
            return []

        with path.open(
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