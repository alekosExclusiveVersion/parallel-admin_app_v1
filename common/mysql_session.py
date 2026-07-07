"""
MySQL session storage.
Хранение данных авторизации только в памяти.
"""


from dataclasses import dataclass


@dataclass
class MySQLSession:

    user: str = ""
    password: str = ""


session = MySQLSession()