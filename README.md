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
from pydantic import BaseModel

# Define your Pydantic model
class User(BaseModel):
    id: int
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
        # Insert a new user
        await db.insert('users', data={'name': 'John Doe', 'email': 'john@example.com'})
        # Query the user with Pydantic model validation
        user = await db.select_one(
            "select * from users where email = :email",
            User,
            {"email": "john@example.com"}
        )
        print(f"User: {user.name} ({user.email})")  # Output => User: John Doe (john@example.com)

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

### Insert Data

```python
# Simple insert
await db.insert('users', data={'name': 'John', 'email': 'john@example.com'})

# Insert with ignore option (skips duplicate key errors)
await db.insert('users', data={'name': 'Jane', 'email': 'jane@example.com'}, ignore=True)
```

### Update Data

```python
# Update where id = 1
await db.update_by_key(
    'users', 
    key={'id': 1}, 
    data={'name': 'John Smith', 'email': 'john.smith@example.com'}
)

# Only non-None values will be updated
await db.update_by_key(
    'users',
    key={'id': 1},
    data={'name': 'Jane Doe', 'email': None}  # email won't be updated
)
```

### Delete Data

```python
# Delete where id = 1
await db.delete_by_key('users', key={'id': 1})
```

### Query Data

```python
# Get a single row
user = await db.get_by_key('users', key={'id': 1})

# Get a row or raise NotFoundError if not found
user = await db.get_by_key_or_fail('users', key={'id': 1})

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
async with connect(host='localhost', user='root', db='testdb') as db:
    # Start transaction (autocommit=False by default)
    await db.insert('orders', data={'customer_id': 1, 'total': 99.99})
    await db.insert('order_items', data={'order_id': db.lastrowid(), 'product_id': 42})
    # Commit the transaction
    await db.commit()
```

## 🔐 Type Safety

CommonDAO provides robust type checking to help prevent errors:

```python
from commondao import is_row_dict, is_query_dict
from typing import Dict, Any

# Valid row dict (for updates/inserts)
valid_data: Dict[str, Any] = {
    "id": 1,
    "name": "John",
    "created_at": datetime.now(),
}

# Check type safety
assert is_row_dict(valid_data)  # Type check passes
await db.update_by_key('users', key={'id': 1}, data=valid_data)  # Type check passes

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
