import os
from typing import Any, Dict, Optional

import pytest
import pytest_asyncio
from pydantic import BaseModel

from commondao import Commondao, connect


class User(BaseModel):
    id: Optional[int] = None
    name: str
    email: str
    age: int


class TestCRUDOperations:
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
            await db.execute_mutation('''
                CREATE TABLE IF NOT EXISTS test_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    age INT
                )
            ''')
            await db.execute_mutation("DELETE FROM test_users")
            yield db
            await db.execute_mutation("DELETE FROM test_users")

    @pytest.mark.asyncio
    async def test_insert(self, db: Commondao) -> None:
        # 测试基本插入
        affected_rows = await db.insert(
            'test_users',
            data={'name': 'Alice', 'email': 'alice@example.com', 'age': 30}
        )
        assert affected_rows == 1
        # 验证数据已插入
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Alice'")
        assert len(result) == 1
        assert result[0]['email'] == 'alice@example.com'
        assert result[0]['age'] == 30

    @pytest.mark.asyncio
    async def test_insert_ignore(self, db: Commondao) -> None:
        # 首先插入一条记录
        await db.insert(
            'test_users',
            data={'name': 'Bob', 'email': 'bob@example.com', 'age': 25}
        )
        # 尝试使用相同的email插入，应该被忽略
        affected_rows = await db.insert(
            'test_users',
            data={'name': 'Bob2', 'email': 'bob@example.com', 'age': 26},
            ignore=True
        )
        assert affected_rows == 0
        # 验证原始数据未被修改
        result = await db.execute_query("SELECT * FROM test_users WHERE email = 'bob@example.com'")
        assert len(result) == 1
        assert result[0]['name'] == 'Bob'
        assert result[0]['age'] == 25

    @pytest.mark.asyncio
    async def test_insert_with_none_values(self, db: Commondao) -> None:
        # 测试包含None值的插入
        affected_rows = await db.insert(
            'test_users',
            data={'name': 'Charlie', 'email': 'charlie@example.com', 'age': None}
        )
        assert affected_rows == 1
        # 验证数据已插入，且None值正确处理
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Charlie'")
        assert len(result) == 1
        assert result[0]['email'] == 'charlie@example.com'
        assert result[0]['age'] is None

    @pytest.mark.asyncio
    async def test_update_by_key(self, db: Commondao) -> None:
        # 插入测试数据
        await db.insert(
            'test_users',
            data={'name': 'David', 'email': 'david@example.com', 'age': 40}
        )
        # 通过key更新数据
        affected_rows = await db.update_by_key(
            'test_users',
            key={'name': 'David'},
            data={'email': 'david.updated@example.com', 'age': 41}
        )
        assert affected_rows == 1
        # 验证数据已更新
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'David'")
        assert len(result) == 1
        assert result[0]['email'] == 'david.updated@example.com'
        assert result[0]['age'] == 41

    @pytest.mark.asyncio
    async def test_update_by_key_with_none_values(self, db: Commondao) -> None:
        # 插入测试数据
        await db.insert(
            'test_users',
            data={'name': 'Eve', 'email': 'eve@example.com', 'age': 22}
        )
        # 使用包含None值的数据更新
        affected_rows = await db.update_by_key(
            'test_users',
            key={'name': 'Eve'},
            data={'email': 'eve.updated@example.com', 'age': None}
        )
        assert affected_rows == 1
        # 验证数据已更新，但age保持原值未变
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Eve'")
        assert len(result) == 1
        assert result[0]['email'] == 'eve.updated@example.com'
        assert result[0]['age'] == 22  # 预期age保持原值，因为update_by_key跳过None值

    @pytest.mark.asyncio
    async def test_update_by_key_no_change(self, db: Commondao) -> None:
        # 插入测试数据
        await db.insert(
            'test_users',
            data={'name': 'Frank', 'email': 'frank@example.com', 'age': 35}
        )
        # 使用全部为None的数据更新（不应有变化）
        affected_rows = await db.update_by_key(
            'test_users',
            key={'name': 'Frank'},
            data={'email': None, 'age': None}
        )
        assert affected_rows == 0
        # 验证数据未变
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Frank'")
        assert len(result) == 1
        assert result[0]['email'] == 'frank@example.com'
        assert result[0]['age'] == 35

    @pytest.mark.asyncio
    async def test_update_by_key_nonexistent(self, db: Commondao) -> None:
        # 尝试更新不存在的记录
        affected_rows = await db.update_by_key(
            'test_users',
            key={'name': 'NonExistent'},
            data={'email': 'new@example.com', 'age': 50}
        )
        assert affected_rows == 0

    @pytest.mark.asyncio
    async def test_delete_by_key(self, db: Commondao) -> None:
        # 插入测试数据
        await db.insert(
            'test_users',
            data={'name': 'Grace', 'email': 'grace@example.com', 'age': 28}
        )
        # 通过key删除数据
        affected_rows = await db.delete_by_key(
            'test_users',
            key={'name': 'Grace'}
        )
        assert affected_rows == 1
        # 验证数据已删除
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Grace'")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_delete_by_key_composite_key(self, db: Commondao) -> None:
        # 插入两条测试数据
        await db.insert(
            'test_users',
            data={'name': 'Helen', 'email': 'helen@example.com', 'age': 32}
        )
        await db.insert(
            'test_users',
            data={'name': 'Helen', 'email': 'helen2@example.com', 'age': 33}
        )
        # 使用组合键删除其中一条
        affected_rows = await db.delete_by_key(
            'test_users',
            key={'name': 'Helen', 'age': 32}
        )
        assert affected_rows == 1
        # 验证正确的数据被删除
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Helen'")
        assert len(result) == 1
        assert result[0]['email'] == 'helen2@example.com'
        assert result[0]['age'] == 33

    @pytest.mark.asyncio
    async def test_delete_by_key_nonexistent(self, db: Commondao) -> None:
        # 尝试删除不存在的记录
        affected_rows = await db.delete_by_key(
            'test_users',
            key={'name': 'NonExistent'}
        )
        assert affected_rows == 0

    @pytest.mark.asyncio
    async def test_get_by_key(self, db: Commondao) -> None:
        # 插入测试数据
        await db.insert(
            'test_users',
            data={'name': 'Ivan', 'email': 'ivan@example.com', 'age': 45}
        )
        # 通过key获取数据
        result = await db.get_by_key('test_users', key={'name': 'Ivan'})
        # 验证结果
        assert result is not None
        assert result['email'] == 'ivan@example.com'
        assert result['age'] == 45

    @pytest.mark.asyncio
    async def test_get_by_key_nonexistent(self, db: Commondao) -> None:
        # 尝试获取不存在的记录
        result = await db.get_by_key('test_users', key={'name': 'NonExistent'})
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_key_or_fail(self, db: Commondao) -> None:
        # 插入测试数据
        await db.insert(
            'test_users',
            data={'name': 'Jack', 'email': 'jack@example.com', 'age': 50}
        )
        # 通过key获取数据
        result = await db.get_by_key_or_fail('test_users', key={'name': 'Jack'})
        # 验证结果
        assert result is not None
        assert result['email'] == 'jack@example.com'
        assert result['age'] == 50

    @pytest.mark.asyncio
    async def test_get_by_key_or_fail_nonexistent(self, db: Commondao) -> None:
        from commondao import NotFoundError

        # 尝试获取不存在的记录，应抛出NotFoundError
        with pytest.raises(NotFoundError):
            await db.get_by_key_or_fail('test_users', key={'name': 'NonExistent'})

    @pytest.mark.asyncio
    async def test_multiple_keys(self, db: Commondao) -> None:
        # 插入几条测试数据
        await db.insert('test_users', data={'name': 'Kate', 'email': 'kate@example.com', 'age': 28})
        await db.insert('test_users', data={'name': 'Kate', 'email': 'kate2@example.com', 'age': 29})
        # 使用组合键获取特定记录
        result = await db.get_by_key('test_users', key={'name': 'Kate', 'age': 29})
        assert result is not None
        assert result['email'] == 'kate2@example.com'
