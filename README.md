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

# Define your Pydantic model with TableId annotation
class User(BaseModel):
    id: Annotated[int, TableId('users')]  # First field with TableId is the primary key
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
        user = User(id=1, name='John Doe', email='john@example.com')
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

class User(BaseModel):
    id: Annotated[Optional[int], TableId('users')] = None  # Auto-increment primary key
    name: str
    email: str

# Insert using Pydantic model (id will be auto-generated)
user = User(name='John', email='john@example.com')
await db.insert(user)
print(f"New user id: {db.lastrowid()}")  # Get the auto-generated id

# Insert with ignore option (skips duplicate key errors)
user2 = User(name='Jane', email='jane@example.com')
await db.insert(user2, ignore=True)
```

### Update Data (with Pydantic Models)

```python
# Update by primary key (id must be provided)
user = User(id=1, name='John Smith', email='john.smith@example.com')
await db.update_by_id(user)

# Update by custom key (partial update - only non-None fields)
user_update = User(name='Jane Doe', email='jane.doe@example.com')  # id can be None
await db.update_by_key(user_update, key={'email': 'john.smith@example.com'})
```

### Delete Data

```python
# Delete by key using entity class
await db.delete_by_key(User, key={'id': 1})
```

### Query Data

```python
# Get a single row by id
user = await db.get_by_id(User, key={'id': 1})

# Get a row by id or raise NotFoundError if not found
user = await db.get_by_id_or_fail(User, key={'id': 1})

# Get by custom key
user = await db.get_by_key(User, key={'email': 'john@example.com'})

# Get by key or raise NotFoundError if not found
user = await db.get_by_key_or_fail(User, key={'email': 'john@example.com'})

# Use with Pydantic models
from pydantic import BaseModel
from commondao import RawSql
from typing import Annotated

class UserModel(BaseModel):
    id: int
    name: str
    email: str
    full_name: Annotated[str, RawSql("CONCAT(first_name, ' ', last_name)")]

# Query with model validation
user = await db.select_one(
    "select * from users where id = :id",
    UserModel,
    {"id": 1}
)

# Query multiple rows
users = await db.select_all(
    "select * from users where status = :status",
    UserModel,
    {"status": "active"}
)

# Paginated queries
from commondao import Paged

result: Paged[UserModel] = await db.select_paged(
    "select * from users where status = :status",
    UserModel,
    {"status": "active"},
    size=10,
    offset=0
)

print(f"Total users: {result.total}")
print(f"Current page: {len(result.items)} users")
```

### Raw SQL Execution

```python
# Execute a query and return results
rows = await db.execute_query(
    "SELECT * FROM users WHERE created_at > :date",
    {"date": "2023-01-01"}
)

# Execute a mutation and return affected row count
affected = await db.execute_mutation(
    "UPDATE users SET status = :status WHERE last_login < :cutoff",
    {"status": "inactive", "cutoff": "2023-01-01"}
)
```

### Transactions

```python
from commondao.annotation import TableId
from typing import Annotated, Optional

class Order(BaseModel):
    id: Annotated[Optional[int], TableId('orders')] = None
    customer_id: int
    total: float

class OrderItem(BaseModel):
    id: Annotated[Optional[int], TableId('order_items')] = None
    order_id: int
    product_id: int

async with connect(host='localhost', user='root', db='testdb') as db:
    # Start transaction (autocommit=False by default)
    order = Order(customer_id=1, total=99.99)
    await db.insert(order)
    order_id = db.lastrowid()  # Get the auto-generated order id

    item = OrderItem(order_id=order_id, product_id=42)
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
