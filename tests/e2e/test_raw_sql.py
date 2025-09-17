import os
from enum import Enum
from typing import Annotated, Any, AsyncGenerator, Dict, Optional

import pytest
import pytest_asyncio
from pydantic import BaseModel

from commondao import Commondao, connect
from commondao.annotation import RawSql


class RegistrationStatus(Enum):
    NOT_REGISTERED = "Not registered"
    REGISTERED = "Registered"


class UserWithCalculatedFields(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    age: Optional[int] = None
    full_name: Annotated[str, RawSql("CONCAT(name, ' (', COALESCE(email, 'N/A'), ')')")]
    is_adult: Annotated[Optional[bool], RawSql("age >= 18")] = None
    registration_info: Annotated[RegistrationStatus, RawSql("CASE WHEN email IS NULL THEN 'Not registered' ELSE 'Registered' END")]


class TestRawSql:
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
                CREATE TABLE IF NOT EXISTS test_raw_sql_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    age INT
                )
            ''')
            # 清空测试数据
            await db.execute_mutation("DELETE FROM test_raw_sql_users")
            # 插入测试数据
            await db.execute_mutation('''
                INSERT INTO test_raw_sql_users (name, email, age) VALUES
                ('Alice', 'alice@example.com', 30),
                ('Bob', 'bob@example.com', 17),
                ('Charlie', NULL, 25),
                ('David', 'david@example.com', NULL)
            ''')
            yield db
            # 清理测试数据
            await db.execute_mutation("DROP TABLE IF EXISTS test_raw_sql_users")

    @pytest.mark.asyncio
    async def test_select_one_with_raw_sql(self, db: Commondao) -> None:
        # 测试使用 RawSql 获取单个记录
        user = await db.select_one(
            "select * from test_raw_sql_users where id = :id",
            UserWithCalculatedFields,
            {"id": 1}
        )
        assert user is not None
        assert user.name == "Alice"
        assert user.full_name == "Alice (alice@example.com)"
        assert user.is_adult is True
        assert user.registration_info == RegistrationStatus.REGISTERED

    @pytest.mark.asyncio
    async def test_select_one_with_null_values(self, db: Commondao) -> None:
        # 测试带有空值的记录
        user = await db.select_one(
            "select * from test_raw_sql_users where id = :id",
            UserWithCalculatedFields,
            {"id": 3}
        )
        assert user is not None
        assert user.name == "Charlie"
        assert user.email is None
        assert user.full_name == "Charlie (N/A)"
        assert user.is_adult is True
        assert user.registration_info == RegistrationStatus.NOT_REGISTERED

    @pytest.mark.asyncio
    async def test_select_all_with_raw_sql(self, db: Commondao) -> None:
        # 测试使用 RawSql 获取多个记录
        users = await db.select_all(
            "select * from test_raw_sql_users order by id",
            UserWithCalculatedFields,
            {}
        )
        assert len(users) == 4
        # 检查第一个用户
        assert users[0].id == 1
        assert users[0].name == "Alice"
        assert users[0].is_adult is True
        # 检查第二个用户
        assert users[1].id == 2
        assert users[1].name == "Bob"
        assert users[1].is_adult is False

    @pytest.mark.asyncio
    async def test_select_paged_with_raw_sql(self, db: Commondao) -> None:
        # 测试使用 RawSql 进行分页查询
        paged_result = await db.select_paged(
            "select * from test_raw_sql_users order by id",
            UserWithCalculatedFields,
            {},
            size=2,
            offset=0
        )
        assert paged_result.total == 4
        assert paged_result.size == 2
        assert paged_result.offset == 0
        assert len(paged_result.items) == 2
        # 检查返回的项目
        assert paged_result.items[0].id == 1
        assert paged_result.items[1].id == 2

    @pytest.mark.asyncio
    async def test_complex_raw_sql_expressions(self, db: Commondao) -> None:
        # 创建一个带有更复杂表达式的模型
        class UserWithComplexExpressions(BaseModel):
            id: int
            name: str
            age_category: Annotated[str, RawSql("""
                CASE
                    WHEN age IS NULL THEN 'Unknown'
                    WHEN age < 18 THEN 'Minor'
                    WHEN age BETWEEN 18 AND 65 THEN 'Adult'
                    ELSE 'Senior'
                END
            """)]
            name_length: Annotated[int, RawSql("LENGTH(name)")]
            has_email: Annotated[bool, RawSql("email IS NOT NULL")]
        # 测试复杂的 RawSql 表达式
        users = await db.select_all(
            "select * from test_raw_sql_users order by id",
            UserWithComplexExpressions,
            {}
        )
        assert len(users) == 4
        # 验证计算字段
        assert users[0].age_category == "Adult"
        assert users[0].name_length == 5  # Alice
        assert users[0].has_email is True
        assert users[1].age_category == "Minor"
        assert users[1].name_length == 3  # Bob
        assert users[1].has_email is True
        assert users[2].age_category == "Adult"
        assert users[2].name_length == 7  # Charlie
        assert users[2].has_email is False
        assert users[3].age_category == "Unknown"
        assert users[3].name_length == 5  # David
        assert users[3].has_email is True
