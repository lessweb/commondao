# CommonDAO

A powerful, type-safe, and Pydantic-integrated async MySQL toolkit for Python.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![Async](https://img.shields.io/badge/Async-FF5A00?style=for-the-badge&logo=python&logoColor=white)
![Type Safe](https://img.shields.io/badge/Type_Safe-3178C6?style=for-the-badge&logoColor=white)

CommonDAO is a lightweight, type-safe async MySQL toolkit designed to simplify database operations with a clean, intuitive API. It integrates seamlessly with Pydantic for robust data validation while providing a comprehensive set of tools for common database tasks.

## ✨ Features

- **Async/Await Support**: Built on aiomysql for non-blocking database operations
- **Type Safety**: Strong typing with Python's type hints and runtime type checking
- **Pydantic Integration**: Seamless validation and transformation of database records to Pydantic models
- **SQL Injection Protection**: Parameterized queries for secure database access
- **Comprehensive CRUD Operations**: Simple methods for common database tasks
- **Raw SQL Support**: Full control when you need it with parameterized raw SQL
- **Connection Pooling**: Efficient database connection management
- **Minimal Boilerplate**: Write less code while maintaining readability and control

## 🚀 Installation

```bash
pip install commondao
```

## 🔍 Quick Start

```python
import asyncio
from commondao import connect
from commondao.annotation import TableId
from pydantic import BaseModel
from typing import Annotated

# Define your Pydantic models with TableId annotation
class User(BaseModel):
    id: Annotated[int, TableId('users')]  # First field with TableId is the primary key
    name: str
    email: str

class UserInsert(BaseModel):
    id: Annotated[Optional[int], TableId('users')] = None  # Optional for auto-increment
    name: str
    email: str

async def main():
    # Connect to database
    config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'password',
        'db': 'testdb',
        'autocommit': True,
    }

    async with connect(**config) as db:
        # Insert a new user using Pydantic model
        user = UserInsert(name='John Doe', email='john@example.com')
        await db.insert(user)

        # Query the user by key with Pydantic model validation
        result = await db.get_by_key(User, key={'email': 'john@example.com'})
        if result:
            print(f"User: {result.name} ({result.email})")  # Output => User: John Doe (john@example.com)

if __name__ == "__main__":
    asyncio.run(main())
```

## 📊 Core Operations

### Connection

```python
from commondao import connect

async with connect(
    host='localhost', 
    port=3306, 
    user='root', 
    password='password', 
    db='testdb'
) as db:
    # Your database operations here
    pass
```

### Insert Data (with Pydantic Models)

```python
from pydantic import BaseModel
from commondao.annotation import TableId
from typing import Annotated, Optional

class UserInsert(BaseModel):
    id: Annotated[Optional[int], TableId('users')] = None  # Auto-increment primary key
    name: str
    email: str

# Insert using Pydantic model (id will be auto-generated)
user = UserInsert(name='John', email='john@example.com')
await db.insert(user)
print(f"New user id: {db.lastrowid()}")  # Get the auto-generated id

# Insert with ignore option (skips duplicate key errors)
user2 = UserInsert(name='Jane', email='jane@example.com')
await db.insert(user2, ignore=True)

# Insert with custom field handling
# exclude_unset=False: includes all fields, even those not explicitly set
# exclude_none=True: excludes fields with None values
user3 = UserInsert(name='Bob', email='bob@example.com')
await db.insert(user3, exclude_unset=False, exclude_none=True)
```

### Update Data (with Pydantic Models)

```python
class UserUpdate(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None

# Update by primary key (id must be provided)
user = UserUpdate(id=1, name='John Smith', email='john.smith@example.com')
await db.update_by_id(user)

# Update by custom key (partial update - only specified fields)
user_update = UserUpdate(name='Jane Doe', email='jane.doe@example.com')
await db.update_by_key(user_update, key={'email': 'john.smith@example.com'})

# Update with field handling options
# exclude_unset=True (default): only update explicitly set fields
# exclude_none=False (default): include None values (set column to NULL)
user = UserUpdate(id=2, name='Alice', email=None)
await db.update_by_id(user, exclude_unset=True, exclude_none=False)  # Sets email to NULL

# Update excluding None values
user = UserUpdate(id=3, name='Bob', email=None)
await db.update_by_id(user, exclude_unset=True, exclude_none=True)  # Won't update email column
```

### Delete Data

```python
# Delete by primary key
await db.delete_by_id(User, 1)

# Delete by custom key
await db.delete_by_key(User, key={'email': 'john@example.com'})
```

### Query Data

```python
# Get a single row by primary key
user = await db.get_by_id(User, 1)

# Get a row by primary key or raise NotFoundError if not found
user = await db.get_by_id_or_fail(User, 1)

# Get by custom key
user = await db.get_by_key(User, key={'email': 'john@example.com'})

# Get by key or raise NotFoundError if not found
user = await db.get_by_key_or_fail(User, key={'email': 'john@example.com'})

# Use with Pydantic models
from pydantic import BaseModel
from commondao.annotation import RawSql
from typing import Annotated

class UserModel(BaseModel):
    id: int
    name: str
    email: str
    full_name: Annotated[str, RawSql("CONCAT(first_name, ' ', last_name)")]

# Query with model validation
user = await db.select_one(
    "from users where id = :id",
    UserModel,
    {"id": 1}
)

# Query multiple rows
users = await db.select_all(
    "from users where status = :status",
    UserModel,
    {"status": "active"}
)

# Paginated queries
from commondao import Paged

result: Paged[UserModel] = await db.select_paged(
    "from users where status = :status",
    UserModel,
    {"status": "active"},
    size=10,
    offset=0
)

print(f"Total users: {result.total}")
print(f"Current page: {len(result.items)} users")
```

### Raw SQL Execution

CommonDAO supports parameterized SQL queries using named parameters with the `:parameter_name` format for secure and readable queries.

#### execute_query - For SELECT operations

```python
# Simple query without parameters
rows = await db.execute_query("SELECT * FROM users")

# Query with single parameter
user_rows = await db.execute_query(
    "SELECT * FROM users WHERE id = :user_id",
    {"user_id": 123}
)

# Query with multiple parameters
filtered_rows = await db.execute_query(
    "SELECT * FROM users WHERE name = :name AND age > :min_age",
    {"name": "John", "min_age": 18}
)

# Query with IN clause (using list parameter)
users_in_group = await db.execute_query(
    "SELECT * FROM users WHERE id IN :user_ids",
    {"user_ids": [1, 2, 3, 4]}
)

# Complex query with date filtering
recent_users = await db.execute_query(
    "SELECT * FROM users WHERE created_at > :date AND status = :status",
    {"date": "2023-01-01", "status": "active"}
)
```

#### execute_mutation - For INSERT, UPDATE, DELETE operations

```python
# INSERT statement
affected = await db.execute_mutation(
    "INSERT INTO users (name, email, age) VALUES (:name, :email, :age)",
    {"name": "John", "email": "john@example.com", "age": 25}
)
print(f"Inserted {affected} rows")

# UPDATE statement
affected = await db.execute_mutation(
    "UPDATE users SET email = :new_email WHERE id = :user_id",
    {"new_email": "newemail@example.com", "user_id": 123}
)
print(f"Updated {affected} rows")

# DELETE statement
affected = await db.execute_mutation(
    "DELETE FROM users WHERE age < :min_age",
    {"min_age": 18}
)
print(f"Deleted {affected} rows")

# Multiple parameter UPDATE
affected = await db.execute_mutation(
    "UPDATE users SET name = :name, age = :age WHERE id = :id",
    {"name": "Jane", "age": 30, "id": 456}
)

# Bulk operations with loop
user_list = [
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"},
]

for user_data in user_list:
    affected = await db.execute_mutation(
        "INSERT INTO users (name, email) VALUES (:name, :email)",
        user_data
    )
```

#### Parameter Format Rules

- **Named Parameters**: Use `:parameter_name` format in SQL
- **Dictionary Keys**: Match parameter names without the colon prefix
- **Supported Types**: str, int, float, bytes, datetime, date, time, timedelta, Decimal
- **Lists/Tuples**: Supported for IN clauses in queries
- **None Values**: Properly handled as SQL NULL

```python
# Example with various data types
from datetime import datetime, date
from decimal import Decimal

result = await db.execute_query(
    """
    SELECT * FROM orders
    WHERE customer_id = :customer_id
    AND total >= :min_total
    AND created_date = :order_date
    AND status IN :valid_statuses
    """,
    {
        "customer_id": 123,
        "min_total": Decimal("99.99"),
        "order_date": date(2023, 12, 25),
        "valid_statuses": ["pending", "confirmed", "shipped"]
    }
)
```

### Transactions

```python
from commondao.annotation import TableId
from typing import Annotated, Optional

class OrderInsert(BaseModel):
    id: Annotated[Optional[int], TableId('orders')] = None
    customer_id: int
    total: float

class OrderItemInsert(BaseModel):
    id: Annotated[Optional[int], TableId('order_items')] = None
    order_id: int
    product_id: int

async with connect(host='localhost', user='root', db='testdb') as db:
    # Start transaction (autocommit=False by default)
    order = OrderInsert(customer_id=1, total=99.99)
    await db.insert(order)
    order_id = db.lastrowid()  # Get the auto-generated order id

    item = OrderItemInsert(order_id=order_id, product_id=42)
    await db.insert(item)

    # Commit the transaction
    await db.commit()
```

## 🔐 Type Safety

CommonDAO provides robust type checking to help prevent errors:

```python
from commondao import is_row_dict, is_query_dict
from typing import Dict, Any
from datetime import datetime

# Valid row dict (for updates/inserts)
valid_data: Dict[str, Any] = {
    "id": 1,
    "name": "John",
    "created_at": datetime.now(),
}

# Check type safety
assert is_row_dict(valid_data)  # Type check passes

# Valid query dict (can contain lists/tuples for IN clauses)
valid_query: Dict[str, Any] = {
    "id": 1,
    "status": "active",
    "tags": ["admin", "user"],  # Lists are valid for query dicts
    "codes": (200, 201)  # Tuples are also valid
}

assert is_query_dict(valid_query)  # Type check passes

# Invalid row dict (contains a list)
invalid_data: Dict[str, Any] = {
    "id": 1,
    "tags": ["admin", "user"]  # Lists are not valid row values
}

assert not is_row_dict(invalid_data)  # Type check fails
```

## 📖 API Documentation

For complete API documentation, please see the docstrings in the code or visit our documentation website.

## 🧪 Testing

CommonDAO comes with comprehensive tests to ensure reliability:

```bash
# Install test dependencies
pip install -e ".[test]"

# Run tests
pytest tests
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the Apache License 2.0.

# CommonDAO API Reference

This document provides comprehensive API reference for CommonDAO, a powerful async MySQL toolkit with Pydantic integration.

## Table of Contents

- [Connection Management](#connection-management)
- [Core CRUD Operations](#core-crud-operations)
- [Query Methods](#query-methods)
- [Raw SQL Execution](#raw-sql-execution)
- [Transaction Management](#transaction-management)
- [Type Safety Utilities](#type-safety-utilities)
- [Annotations](#annotations)
- [Error Classes](#error-classes)
- [Data Types](#data-types)

## Connection Management

### `connect(**config) -> AsyncContextManager[Commondao]`

Creates an async database connection context manager.

**Parameters:**
- `host` (str): Database host
- `port` (int): Database port (default: 3306)
- `user` (str): Database username
- `password` (str): Database password
- `db` (str): Database name
- `autocommit` (bool): Enable autocommit mode (default: True)
- Additional aiomysql connection parameters

**Returns:** AsyncContextManager yielding a Commondao instance

**Example:**
```python
async with connect(host='localhost', user='root', password='pwd', db='testdb') as db:
    # Database operations here
    pass
```

---

## Core CRUD Operations

### `insert(entity: BaseModel, *, ignore: bool = False, exclude_unset: bool = True, exclude_none: bool = False) -> int`

Insert a Pydantic model instance into the database.

**Parameters:**
- `entity` (BaseModel): Pydantic model instance to insert
- `ignore` (bool): Use INSERT IGNORE to skip duplicate key errors
- `exclude_unset` (bool): If True (default), excludes fields not explicitly set. Allows database defaults for unset fields
- `exclude_none` (bool): If False (default), includes None values. If True, excludes None values from INSERT

**Returns:** int - Number of affected rows (1 on success, 0 if ignored)

**Example:**
```python
user = UserInsert(name='John', email='john@example.com')
affected_rows = await db.insert(user)
```

### `update_by_id(entity: BaseModel, *, exclude_unset: bool = True, exclude_none: bool = False) -> int`

Update a record by its primary key using a Pydantic model.

**Parameters:**
- `entity` (BaseModel): Pydantic model with primary key value set
- `exclude_unset` (bool): If True (default), only updates explicitly set fields. Enables partial updates
- `exclude_none` (bool): If False (default), includes None values (sets to NULL). If True, excludes None values

**Returns:** int - Number of affected rows

**Raises:**
- `EmptyPrimaryKeyError`: If primary key is None or empty

**Example:**
```python
user = UserUpdate(id=1, name='John Updated', email='john.new@example.com')
affected_rows = await db.update_by_id(user)
```

### `update_by_key(entity: BaseModel, *, key: QueryDict, exclude_unset: bool = True, exclude_none: bool = False) -> int`

Update records matching the specified key conditions.

**Parameters:**
- `entity` (BaseModel): Pydantic model with update values
- `key` (QueryDict): Dictionary of key-value pairs for WHERE conditions
- `exclude_unset` (bool): If True (default), only updates explicitly set fields. Enables partial updates
- `exclude_none` (bool): If False (default), includes None values (sets to NULL). If True, excludes None values

**Returns:** int - Number of affected rows

**Example:**
```python
user_update = UserUpdate(name='Jane', email='jane@example.com')
affected_rows = await db.update_by_key(user_update, key={'id': 1})
```

### `delete_by_id(entity_class: Type[BaseModel], entity_id: Union[int, str]) -> int`

Delete a record by its primary key value.

**Parameters:**
- `entity_class` (Type[BaseModel]): Pydantic model class
- `entity_id` (Union[int, str]): The primary key value

**Returns:** int - Number of affected rows

**Raises:**
- `AssertionError`: If entity_id is None

**Example:**
```python
affected_rows = await db.delete_by_id(User, 1)
```
### `delete_by_key(entity_class: Type[BaseModel], *, key: QueryDict) -> int`

Delete records matching the specified key conditions.

**Parameters:**
- `entity_class` (Type[BaseModel]): Pydantic model class
- `key` (QueryDict): Dictionary of key-value pairs for WHERE conditions

**Returns:** int - Number of affected rows

**Example:**
```python
affected_rows = await db.delete_by_key(User, key={'id': 1})
```

---

## Query Methods

### `get_by_id(entity_class: Type[M], entity_id: Union[int, str]) -> Optional[M]`

Get a single record by its primary key value.

**Parameters:**
- `entity_class` (Type[M]): Pydantic model class
- `entity_id` (Union[int, str]): The primary key value

**Returns:** Optional[M] - Model instance or None if not found

**Raises:**
- `AssertionError`: If entity_id is None

**Example:**
```python
user = await db.get_by_id(User, 1)
if user:
    print(f"Found user: {user.name}")
```

### `get_by_id_or_fail(entity_class: Type[M], entity_id: Union[int, str]) -> M`

Get a single record by its primary key value or raise an error if not found.

**Parameters:**
- `entity_class` (Type[M]): Pydantic model class
- `entity_id` (Union[int, str]): The primary key value

**Returns:** M - Model instance

**Raises:**
- `NotFoundError`: If no record matches the primary key
- `AssertionError`: If entity_id is None

**Example:**
```python
try:
    user = await db.get_by_id_or_fail(User, 1)
    print(f"User: {user.name}")
except NotFoundError:
    print("User not found")
```

### `get_by_key(entity_class: Type[M], *, key: QueryDict) -> Optional[M]`

Get a single record matching the specified key conditions.

**Parameters:**
- `entity_class` (Type[M]): Pydantic model class
- `key` (QueryDict): Dictionary of key-value pairs for WHERE conditions

**Returns:** Optional[M] - Model instance or None if not found

**Example:**
```python
user = await db.get_by_key(User, key={'email': 'john@example.com'})
```

### `get_by_key_or_fail(entity_class: Type[M], *, key: QueryDict) -> M`

Get a single record matching the key conditions or raise an error if not found.

**Parameters:**
- `entity_class` (Type[M]): Pydantic model class
- `key` (QueryDict): Dictionary of key-value pairs for WHERE conditions

**Returns:** M - Model instance

**Raises:**
- `NotFoundError`: If no record matches the conditions

**Example:**
```python
user = await db.get_by_key_or_fail(User, key={'email': 'john@example.com'})
```

### `select_one(headless_sql: str, select: Type[M], data: QueryDict = {}) -> Optional[M]`

Execute a SELECT query and return the first row as a validated model instance.

**Parameters:**
- `headless_sql` (str): SQL query starting with 'from' (without SELECT clause). Examples: `"from users where age > :min_age"`, `"from \`users\`"`, `"from (subquery) as t"`
- `select` (Type[M]): Pydantic model class for result validation
- `data` (QueryDict): Parameters for the query

**Returns:** Optional[M] - Model instance or None if no results

**Example:**
```python
user = await db.select_one(
    "from users where age > :min_age",
    User,
    {"min_age": 18}
)
```

### `select_one_or_fail(headless_sql: str, select: Type[M], data: QueryDict = {}) -> M`

Execute a SELECT query and return the first row or raise an error if not found.

**Parameters:**
- `headless_sql` (str): SQL query starting with 'from' (without SELECT clause). Examples: `"from users where email = :email"`, `"from \`users\`"`, `"from (subquery) as t"`
- `select` (Type[M]): Pydantic model class for result validation
- `data` (QueryDict): Parameters for the query

**Returns:** M - Model instance

**Raises:**
- `NotFoundError`: If no results found

**Example:**
```python
user = await db.select_one_or_fail(
    "from users where email = :email",
    User,
    {"email": "john@example.com"}
)
```

### `select_all(headless_sql: str, select: Type[M], data: QueryDict = {}) -> list[M]`

Execute a SELECT query and return all matching rows as validated model instances.

**Parameters:**
- `headless_sql` (str): SQL query starting with 'from' (without SELECT clause). Examples: `"from users where status = :status"`, `"from \`users\`"`, `"from (subquery) as t"`
- `select` (Type[M]): Pydantic model class for result validation
- `data` (QueryDict): Parameters for the query

**Returns:** list[M] - List of model instances

**Example:**
```python
active_users = await db.select_all(
    "from users where status = :status",
    User,
    {"status": "active"}
)
```

### `select_paged(headless_sql: str, select: Type[M], data: QueryDict = {}, *, size: int, offset: int = 0) -> Paged[M]`

Execute a paginated SELECT query with total count.

**Parameters:**
- `headless_sql` (str): SQL query starting with 'from' (without SELECT clause). Examples: `"from users where status = :status"`, `"from \`users\`"`, `"from (subquery) as t"`
- `select` (Type[M]): Pydantic model class for result validation
- `data` (QueryDict): Parameters for the query
- `size` (int): Number of items per page
- `offset` (int): Number of items to skip

**Returns:** Paged[M] - Paginated result with items and total count

**Example:**
```python
result = await db.select_paged(
    "from users where status = :status",
    User,
    {"status": "active"},
    size=10,
    offset=20
)
print(f"Total: {result.total}, Page items: {len(result.items)}")
```

---

## Raw SQL Execution

### `execute_query(sql: str, data: Mapping[str, Any] = {}) -> list`

Execute a parameterized SQL query and return all results.

**Parameters:**
- `sql` (str): SQL query with named parameter placeholders (:param_name)
- `data` (Mapping[str, Any]): Dictionary mapping parameter names to values

**Returns:** list - List of result rows (dictionaries)

**Supported Parameter Types:**
- str, int, float, bytes, datetime, date, time, timedelta, Decimal
- Lists/tuples (for IN clauses)
- None (converted to SQL NULL)

**Examples:**
```python
# Simple query
rows = await db.execute_query("SELECT * FROM users")

# Parameterized query
rows = await db.execute_query(
    "SELECT * FROM users WHERE age > :min_age AND status = :status",
    {"min_age": 18, "status": "active"}
)

# IN clause with list
rows = await db.execute_query(
    "SELECT * FROM users WHERE id IN :user_ids",
    {"user_ids": [1, 2, 3, 4]}
)
```

### `execute_mutation(sql: str, data: Mapping[str, Any] = {}) -> int`

Execute a parameterized SQL mutation (INSERT, UPDATE, DELETE) and return affected row count.

**Parameters:**
- `sql` (str): SQL mutation statement with named parameter placeholders (:param_name)
- `data` (Mapping[str, Any]): Dictionary mapping parameter names to values

**Returns:** int - Number of affected rows

**Examples:**
```python
# INSERT
affected = await db.execute_mutation(
    "INSERT INTO users (name, email, age) VALUES (:name, :email, :age)",
    {"name": "John", "email": "john@example.com", "age": 25}
)

# UPDATE
affected = await db.execute_mutation(
    "UPDATE users SET email = :email WHERE id = :id",
    {"email": "newemail@example.com", "id": 123}
)

# DELETE
affected = await db.execute_mutation(
    "DELETE FROM users WHERE age < :min_age",
    {"min_age": 18}
)
```

---

## Transaction Management

### `commit() -> None`

Commit the current transaction.

**Example:**
```python
async with connect(host='localhost', autocommit=False) as db:
    await db.insert(user)
    await db.commit()  # Explicitly commit
```

### `rollback() -> None`

Rollback the current transaction.

**Example:**
```python
try:
    await db.insert(user)
    await db.insert(order)
    await db.commit()
except Exception:
    await db.rollback()
```

### `lastrowid() -> int`

Get the auto-generated ID of the last inserted row.

**Returns:** int - The last inserted row ID

**Example:**
```python
await db.insert(user)
user_id = db.lastrowid()
print(f"New user ID: {user_id}")
```

---

## Type Safety Utilities

### `is_row_dict(data: Mapping) -> TypeGuard[RowDict]`

Check if a mapping is valid for database row operations (INSERT/UPDATE).

**Parameters:**
- `data` (Mapping): The mapping to check

**Returns:** bool - True if valid for row operations

**Valid Types:** str, int, float, bytes, datetime, date, time, timedelta, Decimal, None

**Example:**
```python
from commondao import is_row_dict

data = {"id": 1, "name": "John", "age": 25}
assert is_row_dict(data)
# Now TypeScript knows data is a valid RowDict
```

### `is_query_dict(data: Mapping) -> TypeGuard[QueryDict]`

Check if a mapping is valid for query operations (WHERE clauses).

**Parameters:**
- `data` (Mapping): The mapping to check

**Returns:** bool - True if valid for query operations

**Valid Types:** All RowDict types plus lists and tuples (for IN clauses)

**Example:**
```python
from commondao import is_query_dict

query_data = {"id": 1, "status": "active", "tags": ["admin", "user"]}
assert is_query_dict(query_data)
# Now TypeScript knows query_data is a valid QueryDict
```

---

## Annotations

### `TableId(table_name: str)`

Annotation to mark a field as the primary key and specify the table name.

**Parameters:**
- `table_name` (str): Name of the database table

**Usage:**
```python
from commondao.annotation import TableId
from typing import Annotated, Optional
from pydantic import BaseModel

class User(BaseModel):
    id: Annotated[Optional[int], TableId('users')] = None
    name: str
    email: str
```

### `RawSql(expression: str)`

Annotation to include raw SQL expressions in SELECT queries.

**Parameters:**
- `expression` (str): SQL expression to include

**Usage:**
```python
from commondao.annotation import RawSql
from typing import Annotated

class UserWithFullName(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: Annotated[str, RawSql("CONCAT(first_name, ' ', last_name)")]
```

---

## Error Classes

### `NotFoundError(ValueError)`

Raised when a record is not found in operations that expect a result.

**Example:**
```python
try:
    user = await db.get_by_id_or_fail(User, 999)
except NotFoundError as e:
    print(f"User not found: {e}")
```

### `EmptyPrimaryKeyError(ValueError)`

Raised when attempting operations with empty or None primary key values.

**Example:**
```python
try:
    user = UserUpdate(id=None, name="John")
    await db.update_by_id(user)
except EmptyPrimaryKeyError as e:
    print(f"Primary key error: {e}")
```

### `NotTableError(ValueError)`

Raised when a Pydantic model doesn't have proper table annotation.

### `MissingParamError(ValueError)`

Raised when required parameters are missing from SQL queries.

### `TooManyResultError(ValueError)`

Raised when operations expecting single results return multiple rows.

---

## Data Types

### `RowDict`

Type alias for mappings valid in database row operations.

```python
RowDict = Mapping[str, Union[str, int, float, bytes, datetime, date, time, timedelta, Decimal, None]]
```

### `QueryDict`

Type alias for mappings valid in query operations (extends RowDict with list/tuple support).

```python
QueryDict = Mapping[str, Union[RowValueType, list, tuple]]
```

### `Paged[T]`

Generic container for paginated query results.

**Attributes:**
- `items` (list[T]): List of result items
- `total` (int): Total count of all matching records

**Example:**
```python
result: Paged[User] = await db.select_paged(
    "select * from users",
    User,
    size=10
)
print(f"Page has {len(result.items)} items out of {result.total} total")
```

---

## Type Safety with TypeGuard

CommonDAO provides TypeGuard functions `is_row_dict()` and `is_query_dict()` for runtime type checking. **Important**: These functions should only be used with `assert` statements for proper type narrowing.

### Correct Usage Pattern

```python
from commondao import is_row_dict, is_query_dict

# ✅ Correct: Use with assert
def process_database_row(data: dict):
    assert is_row_dict(data)
    # Type checker now knows data is RowDict
    # Safe to use for database operations
    user = UserInsert(**data)
    await db.insert(user)

def process_query_parameters(params: dict):
    assert is_query_dict(params)
    # Type checker now knows params is QueryDict
    # Safe to use in queries
    result = await db.execute_query(
        "SELECT * FROM users WHERE status = :status",
        params
    )

# ✅ Correct: In test validation
async def test_query_result():
    rows = await db.execute_query("SELECT * FROM users")
    assert len(rows) > 0
    row = rows[0]
    assert is_row_dict(row)  # Validates row format
    # Now safely access row data
    user_id = row['id']
```

### What NOT to do

```python
# ❌ Wrong: Don't use in if statements
if is_row_dict(data):
    # Type narrowing won't work properly
    pass

# ❌ Wrong: Don't use in boolean expressions
valid = is_row_dict(data) and data['id'] > 0

# ❌ Wrong: Don't use with or/and logic
assert is_row_dict(data) or True  # Defeats the purpose
```

### Why Use Assert

TypeGuard functions with `assert` provide both runtime validation and compile-time type narrowing:

```python
def example_function(unknown_data: dict):
    # Before assert: unknown_data is just dict
    assert is_row_dict(unknown_data)
    # After assert: type checker knows unknown_data is RowDict

    # This will have proper type hints and validation
    await db.execute_mutation(
        "INSERT INTO users (name, email) VALUES (:name, :email)",
        unknown_data  # Type checker knows this is safe
    )
```

## Best Practices

### Entity Class Naming Conventions

When designing Pydantic models for database operations, follow these naming conventions to improve code clarity and maintainability:

- **Naming Convention**: Name entity classes used for `dao.insert()` with an `Insert` suffix; name entity classes used for `dao.update()` with an `Update` suffix; keep query entity class names unchanged.

- **Field Optionality Rules**:
  - For query entity classes: If a field's DDL is `NOT NULL`, the field should not be optional
  - For insert entity classes: If a field's DDL is `nullable` or has a default value, the field can be optional
  - For update entity classes: All fields should be optional

- **Field Inclusion**:
  - Insert entity classes should only include fields that may need to be inserted
  - Update entity classes should only include fields that may need to be modified

- **TableId Annotation**: Entity classes used for insert/update operations must always include the `TableId` annotation, even if the primary key field is optional
