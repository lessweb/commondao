from dataclasses import dataclass


@dataclass
class RawSql:
    sql: str


@dataclass
class TableId:
    tablename: str
