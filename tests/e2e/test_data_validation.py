import json
import os
from typing import Annotated, Any, AsyncGenerator, Dict, List, Optional

import pytest
import pytest_asyncio
from pydantic import BaseModel

from commondao import Commondao, connect, is_row_dict
from commondao.annotation import RawSql
from commondao.commondao import validate_row


class User(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    age: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class UserWithRawSql(BaseModel):
    id: int
    name: str
    upper_name: Annotated[str, RawSql("UPPER(name)")]
    age: Optional[int] = None
    is_adult: Annotated[bool, RawSql("age >= 18")]


class TestDataValidation:
    @pytest_asyncio.fixture
    async def db_config(self) -> Dict[str, Any]:
        return {
            'host': os.environ.get('TEST_DB_HOST', 'localhost'),
            'port': int(os.environ.get('TEST_DB_PORT', '3306')),
            'user': os.environ.get('TEST_DB_USER', 'root'),
            'password': os.environ.get('TEST_DB_PASSWORD', 'rootpassword'),
            'db': os.environ.get('TEST_DB_NAME', 'test_db'),
            'autocommit': True
        }

    @pytest_asyncio.fixture
    async def db(self, db_config: Dict[str, Any]) -> AsyncGenerator[Commondao, None]:
        async with connect(**db_config) as db:
            await db.execute_mutation('''
                CREATE TABLE IF NOT EXISTS test_users_validation (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    age INT,
                    metadata JSON,
                    tags JSON
                )
            ''')
            await db.execute_mutation("DELETE FROM test_users_validation")
            yield db
            await db.execute_mutation("DELETE FROM test_users_validation")

    @pytest.mark.asyncio
    async def test_validate_row_basic(self, db: Commondao) -> None:
        row_dict = {
            'id': 1,
            'name': 'John Doe',
            'email': 'john@example.com',
            'age': 30,
            'metadata': None,
            'tags': None
        }
        assert is_row_dict(row_dict)
        user = validate_row(row_dict, User)
        assert isinstance(user, User)
        assert user.id == 1
        assert user.name == 'John Doe'
        assert user.email == 'john@example.com'
        assert user.age == 30
        assert user.metadata is None
        assert user.tags is None

    @pytest.mark.asyncio
    async def test_validate_row_with_json(self, db: Commondao) -> None:
        metadata_json = json.dumps({"role": "admin", "active": True})
        tags_json = json.dumps(["python", "mysql", "testing"])
        row_dict = {
            'id': 1,
            'name': 'John Doe',
            'email': 'john@example.com',
            'age': 30,
            'metadata': metadata_json,
            'tags': tags_json
        }
        assert is_row_dict(row_dict)
        user = validate_row(row_dict, User)
        assert isinstance(user, User)
        assert user.metadata == {"role": "admin", "active": True}
        assert user.tags == ["python", "mysql", "testing"]

    @pytest.mark.asyncio
    async def test_select_one_validation(self, db: Commondao) -> None:
        await db.execute_mutation(
            "INSERT INTO test_users_validation (name, email, age, metadata, tags) VALUES "
            "('Alice', 'alice@example.com', 25, '{\"role\":\"user\"}', '[\"python\",\"mysql\"]')"
        )
        user = await db.select_one("SELECT * FROM test_users_validation WHERE name = :name", User, {"name": "Alice"})
        assert user is not None
        assert isinstance(user, User)
        assert user.name == "Alice"
        assert user.email == "alice@example.com"
        assert user.age == 25
        assert user.metadata == {"role": "user"}
        assert user.tags == ["python", "mysql"]

    @pytest.mark.asyncio
    async def test_select_all_validation(self, db: Commondao) -> None:
        await db.execute_mutation(
            "INSERT INTO test_users_validation (name, email, age) VALUES "
            "('Bob', 'bob@example.com', 30), "
            "('Charlie', 'charlie@example.com', 35)"
        )
        users = await db.select_all("SELECT * FROM test_users_validation WHERE age > :min_age", User, {"min_age": 25})
        assert len(users) == 2
        assert all(isinstance(user, User) for user in users)
        assert {user.name for user in users} == {"Bob", "Charlie"}

    @pytest.mark.asyncio
    async def test_select_paged_validation(self, db: Commondao) -> None:
        # Insert 5 users
        for i in range(5):
            await db.execute_mutation(
                "INSERT INTO test_users_validation (name, email, age) VALUES "
                f"('User{i}', 'user{i}@example.com', {20 + i})"
            )
        # Get first 2 users
        paged_result = await db.select_paged(
            "SELECT * FROM test_users_validation ORDER BY id",
            User, {}, size=2, offset=0
        )
        assert paged_result.total == 5
        assert paged_result.size == 2
        assert paged_result.offset == 0
        assert len(paged_result.items) == 2
        assert all(isinstance(user, User) for user in paged_result.items)
        assert paged_result.items[0].name == "User0"
        assert paged_result.items[1].name == "User1"
        # Get next 2 users
        paged_result = await db.select_paged(
            "SELECT * FROM test_users_validation ORDER BY id",
            User, {}, size=2, offset=2
        )
        assert len(paged_result.items) == 2
        assert paged_result.items[0].name == "User2"
        assert paged_result.items[1].name == "User3"

    @pytest.mark.asyncio
    async def test_raw_sql_model_fields(self, db: Commondao) -> None:
        await db.execute_mutation(
            "INSERT INTO test_users_validation (name, age) VALUES "
            "('David', 17), "
            "('Eve', 21)"
        )
        users = await db.select_all("SELECT * FROM test_users_validation", UserWithRawSql, {})
        assert len(users) == 2
        david = next(user for user in users if user.name == "David")
        eve = next(user for user in users if user.name == "Eve")
        assert david.upper_name == "DAVID"
        assert eve.upper_name == "EVE"
        assert david.is_adult is False
        assert eve.is_adult is True

    @pytest.mark.asyncio
    async def test_select_one_or_fail(self, db: Commondao) -> None:
        await db.execute_mutation(
            "INSERT INTO test_users_validation (name, email, age) VALUES "
            "('Frank', 'frank@example.com', 40)"
        )
        user = await db.select_one_or_fail(
            "SELECT * FROM test_users_validation WHERE name = :name",
            User, {"name": "Frank"}
        )
        assert isinstance(user, User)
        assert user.name == "Frank"
        assert user.age == 40
        with pytest.raises(Exception):
            await db.select_one_or_fail(
                "SELECT * FROM test_users_validation WHERE name = :name",
                User,
                {"name": "NonExistent"}
            )
