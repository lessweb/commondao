import os
from typing import Annotated, Any, AsyncGenerator, Dict, Optional

import pytest
import pytest_asyncio
from pydantic import BaseModel

from commondao import (
    Commondao,
    EmptyPrimaryKeyError,
    NotFoundError,
    connect,
    is_row_dict,
)
from commondao.annotation import TableId


class User(BaseModel):
    id: Annotated[Optional[int], TableId('test_users')] = None
    name: str
    email: str
    age: Optional[int] = None


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
    async def db(self, db_config: Dict[str, Any]) -> AsyncGenerator[Commondao, None]:
        async with connect(**db_config) as db:
            await db.execute_mutation('''
                DROP TABLE IF EXISTS test_users;
                CREATE TABLE test_users (
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
        user = User(name='Alice', email='alice@example.com', age=30)
        affected_rows = await db.insert(user)
        assert affected_rows == 1
        # 验证数据已插入
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Alice'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['email'] == 'alice@example.com'
        assert result[0]['age'] == 30

    @pytest.mark.asyncio
    async def test_insert_ignore(self, db: Commondao) -> None:
        # 首先插入一条记录
        user1 = User(name='Bob', email='bob@example.com', age=25)
        await db.insert(user1)
        # 尝试使用相同的email插入，应该被忽略
        user2 = User(name='Bob2', email='bob@example.com', age=26)
        affected_rows = await db.insert(user2, ignore=True)
        assert affected_rows == 0
        # 验证原始数据未被修改
        result = await db.execute_query("SELECT * FROM test_users WHERE email = 'bob@example.com'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['name'] == 'Bob'
        assert result[0]['age'] == 25

    @pytest.mark.asyncio
    async def test_insert_with_none_values(self, db: Commondao) -> None:
        # 测试包含None值的插入
        user = User(name='Charlie', email='charlie@example.com', age=None)
        affected_rows = await db.insert(user)
        assert affected_rows == 1
        # 验证数据已插入，且None值正确处理
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Charlie'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['email'] == 'charlie@example.com'
        assert result[0]['age'] is None

    @pytest.mark.asyncio
    async def test_update_by_key(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='David', email='david@example.com', age=40)
        await db.insert(user)
        # 通过key更新数据
        updated_user = User(name='David', email='david.updated@example.com', age=41)
        affected_rows = await db.update_by_key(updated_user, key={'name': 'David'})
        assert affected_rows == 1
        # 验证数据已更新
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'David'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['email'] == 'david.updated@example.com'
        assert result[0]['age'] == 41

    @pytest.mark.asyncio
    async def test_update_by_key_with_none_values(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Eve', email='eve@example.com', age=22)
        await db.insert(user)
        # 使用包含None值的数据更新
        updated_user = User(name='Eve', email='eve.updated@example.com', age=None)
        affected_rows = await db.update_by_key(updated_user, key={'name': 'Eve'}, exclude_none=True)
        assert affected_rows == 1
        # 验证数据已更新，但age保持原值未变
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Eve'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['email'] == 'eve.updated@example.com'
        assert result[0]['age'] == 22  # 预期age保持原值，因为update_by_key跳过None值

    @pytest.mark.asyncio
    async def test_update_by_key_no_change(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Frank', email='frank@example.com', age=35)
        await db.insert(user)
        # Test updating with only None age field (exclude_none=True means only age is excluded)
        # Since email has the same value, MySQL returns 0 when no actual change occurs
        updated_user = User(name='Frank', email='frank@example.com', age=None)
        affected_rows = await db.update_by_key(updated_user, key={'name': 'Frank'}, exclude_none=True)
        # MySQL returns 0 when updating with same values (no actual change)
        assert affected_rows == 0
        # 验证数据保持相同值
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Frank'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['email'] == 'frank@example.com'
        assert result[0]['age'] == 35

    @pytest.mark.asyncio
    async def test_update_by_key_nonexistent(self, db: Commondao) -> None:
        # 尝试更新不存在的记录
        updated_user = User(name='NonExistent', email='new@example.com', age=50)
        affected_rows = await db.update_by_key(updated_user, key={'name': 'NonExistent'})
        assert affected_rows == 0

    @pytest.mark.asyncio
    async def test_delete_by_key(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Grace', email='grace@example.com', age=28)
        await db.insert(user)
        # 通过key删除数据
        affected_rows = await db.delete_by_key(User, key={'name': 'Grace'})
        assert affected_rows == 1
        # 验证数据已删除
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Grace'")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_delete_by_key_composite_key(self, db: Commondao) -> None:
        # 插入两条测试数据
        user1 = User(name='Helen', email='helen@example.com', age=32)
        user2 = User(name='Helen', email='helen2@example.com', age=33)
        await db.insert(user1)
        await db.insert(user2)
        # 使用组合键删除其中一条
        affected_rows = await db.delete_by_key(User, key={'name': 'Helen', 'age': 32})
        assert affected_rows == 1
        # 验证正确的数据被删除
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Helen'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['email'] == 'helen2@example.com'
        assert result[0]['age'] == 33

    @pytest.mark.asyncio
    async def test_delete_by_key_nonexistent(self, db: Commondao) -> None:
        # 尝试删除不存在的记录
        affected_rows = await db.delete_by_key(User, key={'name': 'NonExistent'})
        assert affected_rows == 0

    @pytest.mark.asyncio
    async def test_get_by_key(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Ivan', email='ivan@example.com', age=45)
        await db.insert(user)
        # 通过key获取数据
        result = await db.get_by_key(User, key={'name': 'Ivan'})
        # 验证结果
        assert result is not None
        assert result.email == 'ivan@example.com'
        assert result.age == 45

    @pytest.mark.asyncio
    async def test_get_by_key_nonexistent(self, db: Commondao) -> None:
        # 尝试获取不存在的记录
        result = await db.get_by_key(User, key={'name': 'NonExistent'})
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_key_or_fail(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Jack', email='jack@example.com', age=50)
        await db.insert(user)
        # 通过key获取数据
        result = await db.get_by_key_or_fail(User, key={'name': 'Jack'})
        # 验证结果
        assert result is not None
        assert result.email == 'jack@example.com'
        assert result.age == 50

    @pytest.mark.asyncio
    async def test_get_by_key_or_fail_nonexistent(self, db: Commondao) -> None:
        # 尝试获取不存在的记录，应抛出NotFoundError
        with pytest.raises(NotFoundError):
            await db.get_by_key_or_fail(User, key={'name': 'NonExistent'})

    @pytest.mark.asyncio
    async def test_multiple_keys(self, db: Commondao) -> None:
        # 插入几条测试数据
        user1 = User(name='Kate', email='kate@example.com', age=28)
        user2 = User(name='Kate', email='kate2@example.com', age=29)
        await db.insert(user1)
        await db.insert(user2)
        # 使用组合键获取特定记录
        result = await db.get_by_key(User, key={'name': 'Kate', 'age': 29})
        assert result is not None
        assert result.email == 'kate2@example.com'

    @pytest.mark.asyncio
    async def test_update_by_id(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Luke', email='luke@example.com', age=35)
        await db.insert(user)
        # 获取插入后的ID
        user_id = db.lastrowid()
        # 通过ID更新数据
        updated_user = User(id=user_id, name='Luke Updated', email='luke.updated@example.com', age=36)
        affected_rows = await db.update_by_id(updated_user)
        assert affected_rows == 1
        # 验证数据已更新
        result = await db.execute_query("SELECT * FROM test_users WHERE id = :id", {'id': user_id})
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['name'] == 'Luke Updated'
        assert result[0]['email'] == 'luke.updated@example.com'
        assert result[0]['age'] == 36

    @pytest.mark.asyncio
    async def test_update_by_id_with_none_values(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Maria', email='maria@example.com', age=25)
        await db.insert(user)
        user_id = db.lastrowid()
        # 使用包含None值的数据更新（exclude_none=True，所以None值会被跳过）
        updated_user = User(id=user_id, name='Maria Updated', email='maria.updated@example.com', age=None)
        affected_rows = await db.update_by_id(updated_user, exclude_none=True)
        assert affected_rows == 1
        # 验证数据已更新，但age保持原值未变
        result = await db.execute_query("SELECT * FROM test_users WHERE id = :id", {'id': user_id})
        assert len(result) == 1
        assert is_row_dict(result[0])
        assert result[0]['name'] == 'Maria Updated'
        assert result[0]['email'] == 'maria.updated@example.com'
        assert result[0]['age'] == 25  # age保持原值，因为update_by_id跳过None值

    @pytest.mark.asyncio
    async def test_update_by_id_nonexistent(self, db: Commondao) -> None:
        # 尝试更新不存在的记录
        updated_user = User(id=99999, name='NonExistent', email='new@example.com', age=50)
        affected_rows = await db.update_by_id(updated_user)
        assert affected_rows == 0

    @pytest.mark.asyncio
    async def test_update_by_id_empty_primary_key(self, db: Commondao) -> None:
        # 测试空的主键应该抛出异常
        updated_user = User(id=None, name='EmptyPK', email='empty@example.com', age=30)
        with pytest.raises(EmptyPrimaryKeyError):
            await db.update_by_id(updated_user)

    @pytest.mark.asyncio
    async def test_get_by_id(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Nina', email='nina@example.com', age=30)
        await db.insert(user)
        # 获取插入后的ID
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Nina'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        user_id = result[0]['id']
        assert isinstance(user_id, int)
        # 通过ID获取数据
        retrieved_user = await db.get_by_id(User, user_id)
        # 验证结果
        assert retrieved_user is not None
        assert retrieved_user.name == 'Nina'
        assert retrieved_user.email == 'nina@example.com'
        assert retrieved_user.age == 30

    @pytest.mark.asyncio
    async def test_get_by_id_nonexistent(self, db: Commondao) -> None:
        # 尝试获取不存在的记录
        result = await db.get_by_id(User, 99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_none_primary_key(self, db: Commondao) -> None:
        # 测试None主键应该抛出断言异常
        with pytest.raises(AssertionError):
            await db.get_by_id(User, None)  # type: ignore

    @pytest.mark.asyncio
    async def test_get_by_id_or_fail(self, db: Commondao) -> None:
        # 插入测试数据
        user = User(name='Oscar', email='oscar@example.com', age=40)
        await db.insert(user)
        # 获取插入后的ID
        result = await db.execute_query("SELECT * FROM test_users WHERE name = 'Oscar'")
        assert len(result) == 1
        assert is_row_dict(result[0])
        user_id = result[0]['id']
        assert isinstance(user_id, int)
        # 通过ID获取数据
        retrieved_user = await db.get_by_id_or_fail(User, user_id)
        # 验证结果
        assert retrieved_user is not None
        assert retrieved_user.name == 'Oscar'
        assert retrieved_user.email == 'oscar@example.com'
        assert retrieved_user.age == 40

    @pytest.mark.asyncio
    async def test_get_by_id_or_fail_nonexistent(self, db: Commondao) -> None:
        # 尝试获取不存在的记录，应抛出NotFoundError
        with pytest.raises(NotFoundError):
            await db.get_by_id_or_fail(User, 99999)

    @pytest.mark.asyncio
    async def test_get_by_id_or_fail_none_primary_key(self, db: Commondao) -> None:
        # 测试None主键应该抛出断言异常
        with pytest.raises(AssertionError):
            await db.get_by_id_or_fail(User, None)  # type: ignore
