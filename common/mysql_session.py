"""
MySQL session storage.
Хранение данных авторизации только в памяти.
"""


from dataclasses import dataclass


@dataclass
class MySQLSession:

    host: str = ""
    user: str = ""
    password: str = ""


session = MySQLSession()