import inspect
import logging
import re
import typing
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from re import Match
from types import MappingProxyType
from typing import Any, Mapping, Optional, Type, Union

import aiomysql  # type: ignore
import orjson
from aiomysql import DictCursor
from pydantic import BaseModel

from .annotation import RawSql, TableId
from .error import (
    EmptyPrimaryKeyError,
    NotFoundError,
    NotTableError,
    TooManyResultError,
)

RowValueNotNull = Union[
    str,
    int,
    # For NULL values in the database, it will return Python's None.
    float,
    # For MySQL fields of type DECIMAL and NUMERIC, it will return a decimal.Decimal object. e.g. "SELECT CAST(1234.56 AS DECIMAL(10,2)) AS dec_val"
    Decimal,
    # For fields of type BINARY, VARBINARY, or BLOB, it might return a bytes object.
    bytes,
    # For fields of type DATETIME or TIMESTAMP, it returns a Python datetime.datetime object.
    datetime,
    date,
    time,
    # e.g. "SELECT TIMEDIFF('12:00:00', '11:30:00') AS time_diff"
    timedelta,
]
RowDict = Mapping[str, RowValueNotNull | None]
# e.g. "... WHERE id in :ids" ids=[1, 2, 3] or (1, 2, 3)
QueryDict = Mapping[str, RowValueNotNull | None | list | tuple]


def is_row_dict(data: Mapping, /) -> typing.TypeGuard[RowDict]:
    """
    Check if the provided mapping meets the requirements for the RowDict type.
    This function acts as a type guard to determine if the input mapping object can be safely treated as a RowDict type. It checks whether each value in the mapping is either None or matches the RowValueNotNull type (str, int, float, Decimal, bytes, datetime, date, time, timedelta).

    Args:
        data (Mapping): The mapping object to check. The use of the positional-only parameter (/) indicates that it must be passed as a positional argument.

    Returns:
        TypeGuard[RowDict]: Returns True if all values meet the type requirements for RowDict; otherwise, returns False. When this function returns True, mypy will treat data as a RowDict type.

    Example:
    ```python
    from typing import Dict, Any, cast
    from decimal import Decimal
    from datetime import datetime

    # An example of a valid RowDict
    valid_data: Dict = {
        "id": 1,
        "name": "John",
        "price": Decimal("19.99"),
        "created_at": datetime.now(),
        "description": None
    }

    # An example of an invalid RowDict (contains a list)
    invalid_data: Dict = {
        "id": 1,
        "tags": ["a", "b", "c"]  # Lists are not valid RowDict value types
    }

    # Using assert with type guard
    assert is_row_dict(valid_data)
    # After the assertion, mypy will know valid_data is a RowDict type
    name: str = valid_data["name"]  # Type check passes
    await db.update_by_key('tbl_user', key={'id': 1}, data=valid_data)  # Type check passes
    assert is_row_dict(invalid_data)  # Type check fails
    ```
    """
    for value in data.values():
        if value is None:
            continue
        elif isinstance(value, (str, int, float, Decimal, bytes, datetime, date, time, timedelta)):
            continue
        else:
            return False
    return True


def is_list_type(tp) -> typing.TypeGuard[Type[list]]:
    return tp is list or typing.get_origin(tp) is list


def is_query_dict(data: Mapping, /) -> typing.TypeGuard[QueryDict]:
    """
    Check if the provided mapping meets the requirements for a QueryDict type.
    This function acts as a type guard to determine whether the input mapping can safely be considered a QueryDict type. It checks if each value in the mapping is either None or matches the RowValueNotNull types (str, int, float, Decimal, bytes, datetime, date, time, timedelta) or is a list/tuple.
    In the context of database queries, a QueryDict is used to provide values for parameterized queries, especially those with list or tuple parameters (like SQL IN clauses).

    Args:
        data (Mapping): The mapping object to check. The use of a positional-only parameter (/) indicates it must be passed as a positional argument.

    Returns:
        TypeGuard[QueryDict]: Returns True if all values satisfy the QueryDict type requirements; otherwise, returns False. When this function returns True, mypy will treat data as a QueryDict type.

    Example:
    ```
    from typing import Dict, Any, cast
    from decimal import Decimal
    from datetime import datetime

    # Valid QueryDict example
    valid_query: Dict = {
        "id": 1,
        "name": "John",
        "price": Decimal("19.99"),
        "created_at": datetime.now(),
        "tags": ["premium", "new"],  # Lists are valid QueryDict value types
        "status_codes": (200, 201)   # Tuples are also valid
    }

    # Using assertions and type guards
    assert is_query_dict(valid_query)
    # After the assertion, mypy will know valid_query is a QueryDict type
    await db.execute_query("SELECT * FROM products WHERE id = :id AND status IN :status_codes", valid_query)  # Type check passes

    # Invalid QueryDict example (contains a dictionary value)
    invalid_query: Dict = {
        "id": 1,
        "metadata": {"key": "value"}  # Dictionaries are not valid QueryDict value types
    }
    assert is_query_dict(invalid_query)  # Type check fails
    ```
    """
    for value in data.values():
        if value is None:
            continue
        elif isinstance(value, (str, int, float, Decimal, bytes, datetime, date, time, timedelta, list, tuple)):
            continue
        else:
            return False
    return True


T = typing.TypeVar('T')


@dataclass
class Paged(typing.Generic[T]):
    items: list[T]
    offset: Optional[int] = None
    size: Optional[int] = None
    total: Optional[int] = None


def script(*segs) -> str:
    return ' '.join(seg or '' for seg in segs)


def join(*segs) -> str:
    filtered = [seg for seg in segs if seg]
    return ','.join(filtered)


def and_(*segs) -> str:
    filtered = [seg for seg in segs if seg]
    ret = ' and '.join(filtered).strip()
    return f'({ret})' if ret else ''


def where(*segs) -> str:
    sql = and_(*segs)
    return f'where {sql} ' if sql else ''


M = typing.TypeVar("M", bound=BaseModel)


def get_table_meta(model: Type[M]) -> tuple[str, TableId]:
    model_fields = model.model_fields
    for field_name, info in model_fields.items():
        for metadata in info.metadata:
            if isinstance(metadata, TableId):
                return field_name, metadata
    raise NotTableError(f'Model {model.__name__} is not configured as a table entity. Add TableId annotation to define the table mapping.')


def dump_entity_to_row(entity: BaseModel, *, exclude_unset: bool, exclude_none: bool) -> RowDict:
    data = entity.model_dump(exclude_unset=exclude_unset, exclude_none=exclude_none)
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            result[key] = orjson.dumps(value).decode()
        elif isinstance(value, Enum):
            result[key] = value.value
        else:
            result[key] = value
    return result


def validate_row(row: RowDict, model: Type[M]) -> M:
    data: dict[str, Any] = {}
    model_fields = model.model_fields
    for row_key, row_value in row.items():
        if row_key not in model_fields:
            continue
        # If the DB column type is JSON, but aiomysql will return it as a Python str
        if isinstance(row_value, str):
            tp = model_fields[row_key].annotation
            if (inspect.isclass(tp) and issubclass(tp, str)) or tp == Union[str, None]:
                data[row_key] = row_value
            else:
                # Here, since we're converting a str value to a non-str type, any leading or trailing whitespace is definitely unnecessary.
                row_value = row_value.strip()
                if (row_value.startswith('[') and row_value.endswith(']')) or (
                        row_value.startswith('{') and row_value.endswith('}')):
                    data[row_key] = orjson.loads(row_value)
                else:
                    data[row_key] = row_value
        else:
            data[row_key] = row_value
    return model.model_validate(data)


class RegexCollect:
    words: list[str]
    text_areas: list[tuple[int, int]]

    def __init__(self):
        self.words = []
        self.text_areas = []

    def collect_text_areas(self, sql: str):
        pattern = r"'.*?'|\".*?\""
        matches = re.finditer(pattern, sql, flags=re.DOTALL)
        for match in matches:
            self.text_areas.append((match.start(), match.end()))

    def repl(self, m: Match):
        word = m.group()
        in_text_area = any(start <= m.start() < end for start, end in self.text_areas)
        if in_text_area:
            return word
        self.words.append(word[2:])
        return word[0] + '%s'

    def build(self, sql: str, params: typing.Mapping[str, typing.Any]) -> tuple:
        self.collect_text_areas(sql)
        pattern = r"[^:]:[a-zA-Z][\w.]*"
        pg_sql = re.sub(pattern, self.repl, sql)
        pg_params = []
        for k in self.words:
            if k not in params:
                raise ValueError(f"No corresponding value is found for :{k} in params")
            pg_params.append(params[k])
        return pg_sql, tuple(pg_params)


class Commondao:
    def __init__(self, conn, cursor):
        self.conn = conn
        self.cur = cursor

    async def commit(self):
        await self.conn.commit()

    def lastrowid(self) -> int:
        return self.cur.lastrowid

    async def execute_query(self, sql: str, data: typing.Mapping[str, typing.Any] = MappingProxyType({})) -> list:
        """
        Execute a query and return the result.

        This method executes a parameterized SQL query and returns all matching rows.
        It uses named parameter placeholders in the SQL string with a colon prefix (e.g., :param_name).

        Args:
            sql (str): The SQL query string with named parameter placeholders.
                      Use :param_name format for parameters (e.g., "SELECT * FROM users WHERE id = :user_id").
            data (Mapping[str, Any], optional): A dictionary mapping parameter names to their values.
                                              Keys should match the parameter names in the SQL (without the colon).
                                              Defaults to empty mapping.

        Returns:
            list: A list of rows returned by the query. Each row is typically a dictionary-like object.
                 Returns an empty list if no rows match the query.

        Examples:
            # Simple query without parameters
            result = await db.execute_query("SELECT * FROM users")

            # Query with single parameter
            result = await db.execute_query(
                "SELECT * FROM users WHERE id = :user_id",
                {"user_id": 123}
            )

            # Query with multiple parameters
            result = await db.execute_query(
                "SELECT * FROM users WHERE name = :name AND age > :min_age",
                {"name": "John", "min_age": 18}
            )

            # Query with IN clause (using list parameter)
            result = await db.execute_query(
                "SELECT * FROM users WHERE id IN :user_ids",
                {"user_ids": [1, 2, 3, 4]}
            )
        """
        cursor = self.cur
        logging.debug(sql)
        pg_sql, pg_params = RegexCollect().build(sql, data)
        logging.debug('execute query: %s => %s', pg_sql, pg_params)
        await cursor.execute(pg_sql, pg_params)
        return await cursor.fetchall() or []

    async def execute_mutation(self, sql: str, data: typing.Mapping[str, typing.Any] = MappingProxyType({})) -> int:
        """
        Execute a mutation (INSERT, UPDATE, DELETE) and return the number of affected rows.

        This method executes a parameterized SQL mutation statement and returns the count of affected rows.
        It uses named parameter placeholders in the SQL string with a colon prefix (e.g., :param_name).

        Args:
            sql (str): The SQL mutation statement with named parameter placeholders.
                      Use :param_name format for parameters (e.g., "UPDATE users SET name = :name WHERE id = :id").
            data (Mapping[str, Any], optional): A dictionary mapping parameter names to their values.
                                              Keys should match the parameter names in the SQL (without the colon).
                                              Defaults to empty mapping.

        Returns:
            int: The number of rows affected by the mutation. Returns 0 if no rows were affected.

        Examples:
            # INSERT statement
            affected = await db.execute_mutation(
                "INSERT INTO users (name, email, age) VALUES (:name, :email, :age)",
                {"name": "John", "email": "john@example.com", "age": 25}
            )

            # UPDATE statement
            affected = await db.execute_mutation(
                "UPDATE users SET email = :new_email WHERE id = :user_id",
                {"new_email": "newemail@example.com", "user_id": 123}
            )

            # DELETE statement
            affected = await db.execute_mutation(
                "DELETE FROM users WHERE age < :min_age",
                {"min_age": 18}
            )

            # Multiple parameter UPDATE
            affected = await db.execute_mutation(
                "UPDATE users SET name = :name, age = :age WHERE id = :id",
                {"name": "Jane", "age": 30, "id": 456}
            )

            # Bulk INSERT with multiple executions
            for user_data in user_list:
                affected = await db.execute_mutation(
                    "INSERT INTO users (name, email) VALUES (:name, :email)",
                    user_data
                )
        """
        cursor = self.cur
        logging.debug(sql)
        pg_sql, pg_params = RegexCollect().build(sql, data)
        logging.debug('execute mutation: %s => %s', pg_sql, pg_params)
        await cursor.execute(pg_sql, pg_params)
        logging.debug('execute result rowcount: %s', cursor.rowcount)
        return cursor.rowcount

    async def insert(self, entity: BaseModel, *, ignore=False, exclude_unset: bool = True, exclude_none: bool = False) -> int:
        """
        Insert a new row into the specified table.

        :param ignore: If True, uses INSERT IGNORE to skip rows that would cause
                    duplicate key errors. If False (default), uses regular INSERT.
        :return: The number of rows affected by the insertion (typically 1 for success,
                0 for INSERT IGNORE when a duplicate is skipped)

        Note: RawSql metadata is not supported in insert()
        """
        _, table_meta = get_table_meta(entity.__class__)
        data = dump_entity_to_row(entity, exclude_unset=exclude_unset, exclude_none=exclude_none)
        sql = script(
            ('insert into' if not ignore else 'insert ignore into'),
            table_meta.tablename,
            '(',
            join(*[f'`{key}`' for key in data.keys()]),
            ') values (',
            join(*[f':{key}' for key in data.keys()]),
            ')',
        )
        return await self.execute_mutation(sql, data)

    async def update_by_id(self, entity: BaseModel, *, exclude_unset: bool = True, exclude_none: bool = False) -> int:
        pk, table_meta = get_table_meta(entity.__class__)
        data = dump_entity_to_row(entity, exclude_unset=exclude_unset, exclude_none=exclude_none)
        pk_value = data.get(pk)
        if not pk_value:
            raise EmptyPrimaryKeyError(f'Primary key "{pk}" cannot be empty for {entity.__class__.__name__} instance. Provide a valid primary key value.')
        del data[pk]  # type: ignore
        if not data:
            return 0
        sql = script(
            'update',
            table_meta.tablename,
            'set',
            join(*[f'`{k}`=:{k}' for k in data.keys()], ),
            'where',
            f'`{pk}`=:{pk}',
        )
        return await self.execute_mutation(sql, {**data, **{pk: pk_value}})

    async def update_by_key(self, entity: BaseModel, *, key: QueryDict, exclude_unset: bool = True, exclude_none: bool = False) -> int:
        _, table_meta = get_table_meta(entity.__class__)
        data = dump_entity_to_row(entity, exclude_unset=exclude_unset, exclude_none=exclude_none)
        if not data:
            return 0
        sql = script(
            'update',
            table_meta.tablename,
            'set',
            join(*[f'`{k}`=:{k}' for k in data.keys()], ),
            'where',
            and_(*[f'`{k}`=:{k}' for k in key.keys()]),
        )
        return await self.execute_mutation(sql, {**data, **key})

    async def delete_by_id(self, entity_class: Type[M], entity_id: Union[int, str]) -> int:
        pk, _ = get_table_meta(entity_class)
        assert entity_id is not None, f'Primary key {pk} value is None in {entity_class.__name__}'
        return await self.delete_by_key(entity_class, key={pk: entity_id})

    async def delete_by_key(self, entity_class: Type[M], *, key: QueryDict) -> int:
        _, table_meta = get_table_meta(entity_class)
        sql = script(
            'delete from',
            table_meta.tablename,
            'where',
            and_(*[f'`{k}`=:{k}' for k in key.keys()]),
        )
        return await self.execute_mutation(sql, key)

    async def get_by_id(self, entity_class: Type[M], entity_id: Union[int, str]) -> Optional[M]:
        pk, _ = get_table_meta(entity_class)
        assert entity_id is not None, f'Primary key {pk} value is None in {entity_class.__name__}'
        return await self.get_by_key(entity_class, key={pk: entity_id})

    async def get_by_id_or_fail(self, entity_class: Type[M], entity_id: Union[int, str]) -> M:
        pk, _ = get_table_meta(entity_class)
        assert entity_id is not None, f'Primary key {pk} value is None in {entity_class.__name__}'
        return await self.get_by_key_or_fail(entity_class, key={pk: entity_id})

    async def get_by_key(self, entity_class: Type[M], *, key: QueryDict) -> Optional[M]:
        _, table_meta = get_table_meta(entity_class)
        sql = script('select * from', table_meta.tablename,
                     where(and_(*[f'`{k}`=:{k}' for k in key.keys()])),
                     'limit 1')
        rows = await self.execute_query(sql, key)
        if not rows:
            return None
        return validate_row(rows[0], entity_class)

    async def get_by_key_or_fail(self, entity_class: Type[M], *, key: QueryDict) -> M:
        _, table_meta = get_table_meta(entity_class)
        sql = script('select * from', table_meta.tablename,
                     where(and_(*[f'`{k}`=:{k}' for k in key.keys()])),
                     'limit 1')
        rows = await self.execute_query(sql, key)
        if not rows:
            raise NotFoundError(f'No {entity_class.__name__} instance found matching the query criteria: {key}')
        return validate_row(rows[0], entity_class)

    # async def select_one(self, sql, select: Type[U], data: QueryDict = MappingProxyType({})) -> Optional[U]:
    async def select_one(self, sql, select: Type[M], data: QueryDict = MappingProxyType({})) -> Optional[M]:
        """
        Execute a SELECT query and return the first row as a validated Pydantic model instance.

        This method transforms a simplified SQL query (starting with 'select * from') into a proper
        SELECT statement with explicit column selection based on the provided Pydantic model fields.
        It supports both regular column selection and raw SQL expressions through RawSql metadata.

        Args:
            sql (str): SQL query string that must start with 'select * from'. The '*' will be
                    replaced with explicit column names based on the select model fields.
                    Example: "select * from users where age > :min_age"
            select (Type[U]): Pydantic model class that defines the expected structure of the
                            returned data. Field names should match database column names.
                            Fields can include RawSql metadata for custom SQL expressions.
            data (QueryDict, optional): Dictionary containing parameter values for the SQL query.
                                    Keys should match parameter names in the SQL (without ':').
                                    Defaults to empty mapping.

        Returns:
            Optional[U]: The first row from the query result as an instance of the select model,
                        or None if no rows are found. The row data is validated against the
                        Pydantic model schema.

        Raises:
            ValidationError: If the returned row data doesn't match the Pydantic model schema.
            TooManyRowsError: If more than one row is returned by the query.

        Example:
            ```python
            from pydantic import BaseModel
            from commondao.annotation import RawSql
            from typing import Annotated

            class User(BaseModel):
                id: int
                name: str
                email: str
                full_name: Annotated[str, RawSql("CONCAT(first_name, ' ', last_name)")]

            # Find user by ID
            user = await db.select_one(
                "select * from users where id = :user_id",
                User,
                {"user_id": 123}
            )

            if user:
                print(f"Found user: {user.name} ({user.email})")
            else:
                print("User not found")
            ```

        Note:
            - Column selection is based on the Pydantic model fields, not the '*' in the SQL
            - Raw SQL expressions can be used through RawSql metadata on model fields
        """
        assert sql.lower().startswith('select * from')
        headless_sql = sql[13:]
        select_items: list[str] = []
        for name, info in select.model_fields.items():
            for metadata in info.metadata:
                if isinstance(metadata, RawSql):
                    select_items.append(f'({metadata.sql}) as `{name}`')
                    break
            else:  # else-for
                select_items.append(f'`{name}`')
            # end-for
        select_clause = 'select %s from ' % ', '.join(select_items)
        sql = f'{select_clause} {headless_sql}'
        rows = await self.execute_query(sql, data)
        if len(rows) > 1:
            raise TooManyResultError(f'Query returned {len(rows)} results for {select.__name__}. Use select_all() for multiple results.')
        if not rows:
            return None
        return validate_row(rows[0], select)

    async def select_one_or_fail(self, sql, select: Type[M], data: QueryDict = MappingProxyType({})) -> M:
        """
        Execute a SELECT query and return the first row as a validated Pydantic model instance.

        This method transforms a simplified SQL query (starting with 'select * from') into a proper
        SELECT statement with explicit column selection based on the provided Pydantic model fields.
        It raises a NotFoundError if no matching row is found.

        Note:
            - The method automatically adds 'LIMIT 1' to ensure only one row is returned.
            - Column selection is based on the Pydantic model fields, not the '*' in the SQL.
            - Raw SQL expressions can be used through RawSql metadata on model fields.
            - If you want to allow the query to return None if no row is found, use `select_one` instead.
        """
        assert sql.lower().startswith('select * from')
        headless_sql = sql[13:]
        select_items: list[str] = []
        for name, info in select.model_fields.items():
            for metadata in info.metadata:
                if isinstance(metadata, RawSql):
                    select_items.append(f'({metadata.sql}) as `{name}`')
                    break
            else:  # else-for
                select_items.append(f'`{name}`')
            # end-for
        select_clause = 'select %s from ' % ', '.join(select_items)
        sql = f'{select_clause} {headless_sql}'
        rows = await self.execute_query(sql, data)
        if not rows:
            raise NotFoundError(f'No {select.__name__} instance found matching the query criteria.')
        if len(rows) > 1:
            raise TooManyResultError(f'Query returned {len(rows)} results for {select.__name__}, but expected exactly 1. Use select_all() for multiple results.')
        return validate_row(rows[0], select)

    async def select_all(self, sql, select: Type[M], data: QueryDict = MappingProxyType({})) -> list[M]:
        """
        Execute a SELECT query and return all rows as validated Pydantic model instances.

        This method transforms a simplified SQL query (starting with 'select * from') into a proper
        SELECT statement with explicit column selection based on the provided Pydantic model fields.
        It supports both regular column selection and raw SQL expressions through RawSql metadata.

        Args:
            sql (str): SQL query string that must start with 'select * from'. The '*' will be
                    replaced with explicit column names based on the select model fields.
                    Example: "select * from users where age > :min_age"
            select (Type[U]): Pydantic model class that defines the expected structure of the
                            returned data. Field names should match database column names.
                            Fields can include RawSql metadata for custom SQL expressions.
            data (QueryDict, optional): Dictionary containing parameter values for the SQL query.
                                    Keys should match parameter names in the SQL (without ':').
                                    Defaults to empty mapping.

        Returns:
            list[U]: A list of rows from the query result as instances of the select model.
                    Each row data is validated against the Pydantic model schema.

        Note:
            - Column selection is based on the Pydantic model fields, not the '*' in the SQL.
            - Raw SQL expressions can be used through RawSql metadata on model fields.
        """
        assert sql.lower().startswith('select * from')
        headless_sql = sql[13:]
        select_items: list[str] = []
        for name, info in select.model_fields.items():
            for metadata in info.metadata:
                if isinstance(metadata, RawSql):
                    select_items.append(f'({metadata.sql}) as `{name}`')
                    break
            else:  # else-for
                select_items.append(f'`{name}`')
            # end-for
        select_clause = 'select %s from ' % ', '.join(select_items)
        sql = f'{select_clause} {headless_sql}'
        rows = await self.execute_query(sql, data)
        models = [validate_row(row, select) for row in rows]
        return models

    async def select_paged(
        self,
        sql: str,
        select: Type[M],
        data: QueryDict,
        *,
        size: int,
        offset: int = 0,
    ) -> Paged[M]:
        """
        Execute a paginated SELECT query and return a Paged object containing the results.

        This method transforms a SELECT query to support pagination using LIMIT and OFFSET clauses.
        It also performs a COUNT query to determine the total number of records available.

        Args:
            sql (str): The SQL query string. Must start with 'select * from' (case-insensitive).
                      The '*' will be replaced with the actual column selections based on the
                      select model fields.
            select (Type[U]): A Pydantic BaseModel class that defines the structure of the
                             returned data. The method will validate each row against this model.
            data (QueryDict): A dictionary containing parameters for the SQL query. Keys should
                             match the parameter placeholders in the SQL string (e.g., ':param').
            size (int): The maximum number of records to return per page. Must be >= 1.
                       Values less than 1 will be automatically adjusted to 1.
            offset (int, optional): The number of records to skip from the beginning of the
                            result set. Defaults to 0. Must be >= 0. Values less than 0 will be
                            automatically adjusted to 0.

        Returns:
            Paged[U]: A Paged object containing:
                - items: List of validated model instances of type U
                - offset: The offset value used for this query
                - size: The page size used for this query
                - total: The total number of records available (from COUNT query)

        Raises:
            ValidationError: If any row cannot be validated against the select model

        Example:
            ```python
            from pydantic import BaseModel

            class User(BaseModel):
                id: int
                name: str
                email: str

            # Get first 10 users
            result = await db.select_paged(
                "select * from users where active = :active order by name",
                User,
                {"active": True},
                size=10,
                offset=0
            )

            # Get next 10 users
            next_result = await db.select_paged(
                "select * from users where active = :active order by name",
                User,
                {"active": True},
                size=10,
                offset=10
            )

            print(f"Total users: {result.total}")
            print(f"Current batch: {len(result.items)} users")
            ```

        Note:
            - The method automatically handles RawSql metadata in model fields for custom SQL expressions
            - Column names are automatically quoted with backticks for MySQL compatibility
            - The original SQL's SELECT clause is replaced, so complex SELECT expressions should be
              defined using RawSql metadata in the model fields
        """
        assert sql.lower().startswith('select * from')
        headless_sql = sql[13:]
        offset = max(0, offset)
        size = max(1, size)
        select_items: list[str] = []
        for name, info in select.model_fields.items():
            for metadata in info.metadata:
                if isinstance(metadata, RawSql):
                    select_items.append(f'({metadata.sql}) as `{name}`')
                    break
            else:  # else-for
                select_items.append(f'`{name}`')
            # end-for
        select_clause = 'select %s from ' % ', '.join(select_items)
        sql = f'{select_clause} {headless_sql}'
        count_sql = f'select count(*) as total from {headless_sql}'
        count_result = await self.execute_query(count_sql, data)
        assert count_result, "count result should not be empty"
        total: int = count_result[0]['total']  # type: ignore
        limit_clause = 'limit %d' % size
        if offset:
            limit_clause += ' offset %d' % offset
        sql = f'{select_clause} {headless_sql} {limit_clause}'
        rows = await self.execute_query(sql, data)
        models = [validate_row(row, select) for row in rows]
        return Paged(models, offset, size, total)


class _ConnectionManager():
    def __init__(self, **config):
        self.config = config

    async def __aenter__(self):
        self.conn = await aiomysql.connect(**self.config)
        self.cursor = await self.conn.cursor(DictCursor)
        return Commondao(self.conn, self.cursor)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cursor.close()
        self.conn.close()


def connect(**config) -> _ConnectionManager:
    """
    Create a database connection manager using aiomysql.

    This function returns an async context manager that handles MySQL database
    connections using aiomysql. The connection manager automatically handles
    connection lifecycle (opening/closing) and provides a Commondao instance
    for database operations.

    Args:
        **config: Database connection configuration parameters passed to aiomysql.connect().
            Common parameters include:
            - host (str): Database host address
            - port (int): Database port number (default: 3306)
            - user (str): Database username
            - password (str): Database password
            - db (str): Database name
            - charset (str): Character set (default: 'utf8mb4')
            - autocommit (bool): Auto-commit mode (default: False)
            - Other aiomysql.connect() parameters are also supported

    Returns:
        _ConnectionManager: An async context manager that yields a Commondao instance
            when entered. The Commondao instance provides high-level database operations
            like save, get_by_key, insert, update, select, etc.

    Raises:
        aiomysql.Error: If there is an error connecting to the database

    Example:
        Basic usage with async context manager:

        >>> config = {
        ...     'host': 'localhost',
        ...     'port': 3306,
        ...     'user': 'myuser',
        ...     'password': 'mypassword',
        ...     'db': 'mydatabase',
        ... }
        >>> async with commondao.connect(**config) as db:
        ...     await db.save('tbl_user', {'id': 1, 'name': 'John Doe'})
        ...     user = await db.get_by_key_or_fail('tbl_user', key={'id': 1})
        ...     print(user['name'])  # Output: John Doe

    Note:
        - The connection is automatically closed when exiting the context manager
        - All database operations should be performed within the async context
        - Remember to commit transactions manually using db.commit() if autocommit=False
    """
    return _ConnectionManager(**config)
