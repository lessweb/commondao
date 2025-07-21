import os
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict

import pytest
import pytest_asyncio

from commondao import Commondao, connect


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
        await db.insert('transaction_test', data={'name': 'Alice', 'balance': 1000.00})
        # 提交事务
        await db.commit()
        # 验证数据已提交
        result = await db.get_by_key('transaction_test', key={'name': 'Alice'})
        assert result is not None
        assert result['name'] == 'Alice'
        # 修复：处理 balance 字段的类型
        balance = result['balance']
        assert isinstance(balance, (int, float, Decimal, str))
        assert float(balance) == 1000.00

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, db_config: Dict[str, Any]) -> None:
        async with connect(**db_config) as db1:
            # 插入数据但不提交
            await db1.insert('transaction_test', data={'name': 'Bob', 'balance': 500.00})
            # 在同一连接中可以查询到未提交的数据
            result = await db1.get_by_key('transaction_test', key={'name': 'Bob'})
            assert result is not None
            assert result['name'] == 'Bob'
        # 连接关闭时，事务自动回滚
        # 创建新连接验证数据未提交
        async with connect(**db_config) as db2:
            result = await db2.get_by_key('transaction_test', key={'name': 'Bob'})
            assert result is None

    @pytest.mark.asyncio
    async def test_multiple_operations_in_transaction(self, db: Commondao) -> None:
        # 执行多个操作，统一提交
        await db.insert('transaction_test', data={'name': 'Charlie', 'balance': 1500.00})
        await db.insert('transaction_test', data={'name': 'Dave', 'balance': 2000.00})
        # 更新操作
        await db.update_by_key('transaction_test', key={'name': 'Charlie'}, data={'balance': 1600.00})
        # 提交事务
        await db.commit()
        # 验证所有操作都已提交
        charlie = await db.get_by_key('transaction_test', key={'name': 'Charlie'})
        dave = await db.get_by_key('transaction_test', key={'name': 'Dave'})
        assert charlie is not None
        assert dave is not None
        # 修复：处理 balance 字段的类型
        charlie_balance = charlie['balance']
        dave_balance = dave['balance']
        assert isinstance(charlie_balance, (int, float, Decimal, str))
        assert isinstance(dave_balance, (int, float, Decimal, str))
        assert float(charlie_balance) == 1600.00
        assert float(dave_balance) == 2000.00

    @pytest.mark.asyncio
    async def test_lastrowid_after_insert(self, db: Commondao) -> None:
        # 测试插入后获取lastrowid
        await db.insert('transaction_test', data={'name': 'Eve', 'balance': 3000.00})
        row_id = db.lastrowid()
        assert row_id > 0
        await db.commit()
        # 验证使用获取的ID可以查询到记录
        result = await db.get_by_key('transaction_test', key={'id': row_id})
        assert result is not None
        assert result['name'] == 'Eve'

    @pytest.mark.asyncio
    async def test_transaction_isolation(self, db_config: Dict[str, Any]) -> None:
        # 在第一个连接中插入数据但不提交
        async with connect(**db_config) as db1:
            await db1.insert('transaction_test', data={'name': 'Frank', 'balance': 2500.00})
            # 在第二个连接中无法看到未提交的数据
            async with connect(**db_config) as db2:
                result = await db2.get_by_key('transaction_test', key={'name': 'Frank'})
                assert result is None
            # 现在提交第一个连接中的数据
            await db1.commit()
            # 在新连接中应该能看到提交的数据
            async with connect(**db_config) as db3:
                result = await db3.get_by_key('transaction_test', key={'name': 'Frank'})
                assert result is not None
                assert result['name'] == 'Frank'
                assert isinstance(result['balance'], Decimal) and float(result['balance']) == 2500.00
