import os
from typing import Annotated, Any, AsyncGenerator, Dict, Optional

import pytest
import pytest_asyncio
from pydantic import BaseModel

from commondao import Commondao, NotFoundError, connect
from commondao.annotation import RawSql


class User(BaseModel):
    id: int
    name: str
    email: str
    age: int


class UserWithFullName(BaseModel):
    id: int
    name: str
    email: str
    age: int
    full_name: Annotated[str, RawSql("CONCAT(name, ' (', age, ')')")]


class TestSelectMethods:
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
            # 创建测试表
            await db.execute_mutation('''
                CREATE TABLE IF NOT EXISTS test_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    age INT
                )
            ''')
            # 清空测试数据
            await db.execute_mutation("DELETE FROM test_users")
            # 插入测试数据
            await db.execute_mutation(
                "INSERT INTO test_users (name, email, age) VALUES ('Alice', 'alice@example.com', 30)"
            )
            await db.execute_mutation(
                "INSERT INTO test_users (name, email, age) VALUES ('Bob', 'bob@example.com', 25)"
            )
            await db.execute_mutation(
                "INSERT INTO test_users (name, email, age) VALUES ('Charlie', 'charlie@example.com', 35)"
            )
            await db.execute_mutation(
                "INSERT INTO test_users (name, email, age) VALUES ('David', 'david@example.com', 40)"
            )
            await db.execute_mutation(
                "INSERT INTO test_users (name, email, age) VALUES ('Eve', 'eve@example.com', 22)"
            )
            yield db
            # 清理测试数据
            await db.execute_mutation("DELETE FROM test_users")

    @pytest.mark.asyncio
    async def test_select_one(self, db: Commondao) -> None:
        # 测试正常情况
        user: Optional[User] = await db.select_one(
            "select * from test_users where name = :name",
            User,
            {"name": "Alice"}
        )
        assert user is not None
        assert user.id is not None
        assert user.name == "Alice"
        assert user.email == "alice@example.com"
        assert user.age == 30
        # 测试返回空的情况
        non_user: Optional[User] = await db.select_one(
            "select * from test_users where name = :name",
            User,
            {"name": "NonExistent"}
        )
        assert non_user is None
        # 测试带有RawSql的情况
        user_with_full_name: Optional[UserWithFullName] = await db.select_one(
            "select * from test_users where name = :name",
            UserWithFullName,
            {"name": "Bob"}
        )
        assert user_with_full_name is not None
        assert user_with_full_name.full_name == "Bob (25)"

    @pytest.mark.asyncio
    async def test_select_one_or_fail(self, db: Commondao) -> None:
        # 测试正常情况
        user: User = await db.select_one_or_fail(
            "select * from test_users where name = :name",
            User,
            {"name": "Charlie"}
        )
        assert user.id is not None
        assert user.name == "Charlie"
        assert user.email == "charlie@example.com"
        assert user.age == 35
        # 测试抛出异常的情况
        with pytest.raises(NotFoundError):
            await db.select_one_or_fail(
                "select * from test_users where name = :name",
                User,
                {"name": "NonExistent"}
            )
        # 测试带有RawSql的情况
        user_with_full_name: UserWithFullName = await db.select_one_or_fail(
            "select * from test_users where name = :name",
            UserWithFullName,
            {"name": "David"}
        )
        assert user_with_full_name.full_name == "David (40)"

    @pytest.mark.asyncio
    async def test_select_all(self, db: Commondao) -> None:
        # 测试获取所有记录
        users: list[User] = await db.select_all(
            "select * from test_users order by age",
            User
        )
        assert len(users) == 5
        assert users[0].name == "Eve"
        assert users[1].name == "Bob"
        assert users[2].name == "Alice"
        assert users[3].name == "Charlie"
        assert users[4].name == "David"
        # 测试使用条件过滤
        filtered_users: list[User] = await db.select_all(
            "select * from test_users where age > :min_age order by name",
            User,
            {"min_age": 30}
        )
        assert len(filtered_users) == 2
        assert filtered_users[0].name == "Charlie"
        assert filtered_users[1].name == "David"
        # 测试空结果
        empty_users: list[User] = await db.select_all(
            "select * from test_users where name = :name",
            User,
            {"name": "NonExistent"}
        )
        assert len(empty_users) == 0
        # 测试带有RawSql的情况
        users_with_full_name: list[UserWithFullName] = await db.select_all(
            "select * from test_users order by age desc limit 2",
            UserWithFullName
        )
        assert len(users_with_full_name) == 2
        assert users_with_full_name[0].full_name == "David (40)"
        assert users_with_full_name[1].full_name == "Charlie (35)"

    @pytest.mark.asyncio
    async def test_select_paged(self, db: Commondao) -> None:
        # 测试基本分页功能
        result = await db.select_paged(
            "select * from test_users order by age",
            User,
            {},
            size=2,
            offset=0
        )
        assert result.total == 5
        assert result.size == 2
        assert result.offset == 0
        assert len(result.items) == 2
        assert result.items[0].name == "Eve"
        assert result.items[1].name == "Bob"
        # 测试下一页
        next_page = await db.select_paged(
            "select * from test_users order by age",
            User,
            {},
            size=2,
            offset=2
        )
        assert next_page.total == 5
        assert next_page.size == 2
        assert next_page.offset == 2
        assert len(next_page.items) == 2
        assert next_page.items[0].name == "Alice"
        assert next_page.items[1].name == "Charlie"
        # 测试最后一页（不满size的情况）
        last_page = await db.select_paged(
            "select * from test_users order by age",
            User,
            {},
            size=2,
            offset=4
        )
        assert last_page.total == 5
        assert last_page.size == 2
        assert last_page.offset == 4
        assert len(last_page.items) == 1
        assert last_page.items[0].name == "David"
        # 测试带条件的分页
        filtered_page = await db.select_paged(
            "select * from test_users where age > :min_age order by name",
            User,
            {"min_age": 25},
            size=2,
            offset=0
        )
        assert filtered_page.total == 3
        assert len(filtered_page.items) == 2
        assert filtered_page.items[0].name == "Alice"
        assert filtered_page.items[1].name == "Charlie"
        # 测试带有RawSql的情况
        custom_page = await db.select_paged(
            "select * from test_users order by age desc",
            UserWithFullName,
            {},
            size=3,
            offset=1
        )
        assert custom_page.total == 5
        assert len(custom_page.items) == 3
        assert custom_page.items[0].full_name == "Charlie (35)"
        assert custom_page.items[1].full_name == "Alice (30)"
        assert custom_page.items[2].full_name == "Bob (25)"
