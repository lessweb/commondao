import os
from typing import Any, Dict

import pytest
import pytest_asyncio

from commondao import Commondao, connect


class TestQueryExecution:
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
    async def db(self, db_config: Dict[str, Any]):
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
            yield db
            # 清理测试数据
            await db.execute_mutation("DELETE FROM test_users")

    @pytest.mark.asyncio
    async def test_execute_query_with_no_params(self, db: Commondao) -> None:
        # 插入测试数据
        await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES ('Alice', 'alice@example.com', 30)"
        )
        # 执行查询
        result = await db.execute_query("SELECT * FROM test_users")
        # 验证结果
        assert len(result) == 1
        assert result[0]['name'] == 'Alice'
        assert result[0]['email'] == 'alice@example.com'
        assert result[0]['age'] == 30

    @pytest.mark.asyncio
    async def test_execute_query_with_params(self, db: Commondao) -> None:
        # 插入测试数据
        await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES ('Bob', 'bob@example.com', 25)"
        )
        await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES ('Charlie', 'charlie@example.com', 35)"
        )
        # 使用参数执行查询
        result = await db.execute_query(
            "SELECT * FROM test_users WHERE age > :min_age",
            {"min_age": 30}
        )
        # 验证结果
        assert len(result) == 1
        assert result[0]['name'] == 'Charlie'
        assert result[0]['age'] == 35

    @pytest.mark.asyncio
    async def test_execute_query_with_multiple_params(self, db: Commondao) -> None:
        # 插入测试数据
        await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES ('David', 'david@example.com', 40)"
        )
        await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES ('Eve', 'eve@example.com', 22)"
        )
        await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES ('Frank', 'frank@example.com', 35)"
        )
        # 使用多个参数执行查询
        result = await db.execute_query(
            "SELECT * FROM test_users WHERE age >= :min_age AND age <= :max_age ORDER BY name",
            {"min_age": 25, "max_age": 40}
        )
        # 验证结果
        assert len(result) == 2
        assert result[0]['name'] == 'David'
        assert result[1]['name'] == 'Frank'

    @pytest.mark.asyncio
    async def test_execute_query_empty_result(self, db: Commondao) -> None:
        # 执行查询不存在的数据
        result = await db.execute_query(
            "SELECT * FROM test_users WHERE name = :name",
            {"name": "NonExistent"}
        )
        # 验证结果为空列表
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_mutation_insert(self, db: Commondao) -> None:
        # 执行插入操作
        affected_rows = await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES (:name, :email, :age)",
            {"name": "Grace", "email": "grace@example.com", "age": 28}
        )
        # 验证受影响行数
        assert affected_rows == 1
        # 验证数据已插入
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Grace'")
        assert len(result) == 1
        assert result[0]['email'] == 'grace@example.com'

    @pytest.mark.asyncio
    async def test_execute_mutation_update(self, db: Commondao) -> None:
        # 插入测试数据
        await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES ('Helen', 'helen@example.com', 32)"
        )
        # 执行更新操作
        affected_rows = await db.execute_mutation(
            "UPDATE test_users SET age = :new_age WHERE name = :name",
            {"name": "Helen", "new_age": 33}
        )
        # 验证受影响行数
        assert affected_rows == 1
        # 验证数据已更新
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Helen'")
        assert result[0]['age'] == 33

    @pytest.mark.asyncio
    async def test_execute_mutation_delete(self, db: Commondao) -> None:
        # 插入测试数据
        await db.execute_mutation(
            "INSERT INTO test_users (name, email, age) VALUES ('Ivan', 'ivan@example.com', 45)"
        )
        # 验证数据已插入
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Ivan'")
        assert len(result) == 1
        # 执行删除操作
        affected_rows = await db.execute_mutation(
            "DELETE FROM test_users WHERE name = :name",
            {"name": "Ivan"}
        )
        # 验证受影响行数
        assert affected_rows == 1
        # 验证数据已删除
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Ivan'")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_execute_mutation_no_effect(self, db: Commondao) -> None:
        # 执行更新不存在的数据
        affected_rows = await db.execute_mutation(
            "UPDATE test_users SET age = :age WHERE name = :name",
            {"name": "NonExistent", "age": 50}
        )
        # 验证受影响行数为0
        assert affected_rows == 0
