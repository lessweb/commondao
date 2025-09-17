import os
from decimal import Decimal
from typing import Annotated, Any, AsyncGenerator, Dict

import pytest
import pytest_asyncio
from pydantic import BaseModel

from commondao import Commondao, connect
from commondao.annotation import TableId


class TransactionTest(BaseModel):
    id: Annotated[int | None, TableId('transaction_test')] = None
    name: str
    balance: Decimal


class TestTransactions:
    @pytest_asyncio.fixture
    async def db_config(self) -> Dict[str, Any]:
        return {
            'host': os.environ.get('TEST_DB_HOST', 'localhost'),
            'port': int(os.environ.get('TEST_DB_PORT', '3306')),
            'user': os.environ.get('TEST_DB_USER', 'root'),
            'password': os.environ.get('TEST_DB_PASSWORD', 'rootpassword'),
            'db': os.environ.get('TEST_DB_NAME', 'test_db'),
            'autocommit': False
        }

    @pytest_asyncio.fixture
    async def db(self, db_config: Dict[str, Any]) -> AsyncGenerator[Commondao, None]:
        async with connect(**db_config) as db:
            # 创建测试表
            await db.execute_mutation('''
                CREATE TABLE IF NOT EXISTS transaction_test (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    balance DECIMAL(10, 2) NOT NULL
                )
            ''')
            await db.commit()
            # 清空测试数据
            await db.execute_mutation("DELETE FROM transaction_test")
            await db.commit()
            yield db
            # 清理测试数据
            await db.execute_mutation("DELETE FROM transaction_test")
            await db.commit()

    @pytest.mark.asyncio
    async def test_commit_transaction(self, db: Commondao) -> None:
        # 插入测试数据
        entity = TransactionTest(name='Alice', balance=Decimal('1000.00'))
        await db.insert(entity)
        # 提交事务
        await db.commit()
        # 验证数据已提交
        result = await db.get_by_key(TransactionTest, key={'name': 'Alice'})
        assert result is not None
        assert result.name == 'Alice'
        assert result.balance == Decimal('1000.00')

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, db_config: Dict[str, Any]) -> None:
        async with connect(**db_config) as db1:
            # 插入数据但不提交
            entity = TransactionTest(name='Bob', balance=Decimal('500.00'))
            await db1.insert(entity)
            # 在同一连接中可以查询到未提交的数据
            result = await db1.get_by_key(TransactionTest, key={'name': 'Bob'})
            assert result is not None
            assert result.name == 'Bob'
        # 连接关闭时，事务自动回滚
        # 创建新连接验证数据未提交
        async with connect(**db_config) as db2:
            result = await db2.get_by_key(TransactionTest, key={'name': 'Bob'})
            assert result is None

    @pytest.mark.asyncio
    async def test_multiple_operations_in_transaction(self, db: Commondao) -> None:
        # 执行多个操作，统一提交
        charlie = TransactionTest(name='Charlie', balance=Decimal('1500.00'))
        dave = TransactionTest(name='Dave', balance=Decimal('2000.00'))
        await db.insert(charlie)
        await db.insert(dave)
        # 更新操作
        updated_charlie = TransactionTest(name='Charlie', balance=Decimal('1600.00'))
        await db.update_by_key(updated_charlie, key={'name': 'Charlie'})
        # 提交事务
        await db.commit()
        # 验证所有操作都已提交
        charlie_result = await db.get_by_key(TransactionTest, key={'name': 'Charlie'})
        dave_result = await db.get_by_key(TransactionTest, key={'name': 'Dave'})
        assert charlie_result is not None
        assert dave_result is not None
        assert charlie_result.balance == Decimal('1600.00')
        assert dave_result.balance == Decimal('2000.00')

    @pytest.mark.asyncio
    async def test_lastrowid_after_insert(self, db: Commondao) -> None:
        # 测试插入后获取lastrowid
        eve = TransactionTest(name='Eve', balance=Decimal('3000.00'))
        await db.insert(eve)
        row_id = db.lastrowid()
        assert row_id > 0
        await db.commit()
        # 验证使用获取的ID可以查询到记录
        result = await db.get_by_key(TransactionTest, key={'id': row_id})
        assert result is not None
        assert result.name == 'Eve'

    @pytest.mark.asyncio
    async def test_transaction_isolation(self, db_config: Dict[str, Any]) -> None:
        # 在第一个连接中插入数据但不提交
        async with connect(**db_config) as db1:
            frank = TransactionTest(name='Frank', balance=Decimal('2500.00'))
            await db1.insert(frank)
            # 在第二个连接中无法看到未提交的数据
            async with connect(**db_config) as db2:
                result = await db2.get_by_key(TransactionTest, key={'name': 'Frank'})
                assert result is None
            # 现在提交第一个连接中的数据
            await db1.commit()
            # 在新连接中应该能看到提交的数据
            async with connect(**db_config) as db3:
                result = await db3.get_by_key(TransactionTest, key={'name': 'Frank'})
                assert result is not None
                assert result.name == 'Frank'
                assert result.balance == Decimal('2500.00')
