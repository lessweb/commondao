import os
from typing import Annotated, Any, AsyncGenerator, Dict

import pytest
import pytest_asyncio
from pydantic import BaseModel

from commondao import Commondao, NotFoundError, connect
from commondao.annotation import TableId


class ErrorHandlingRecord(BaseModel):
    id: Annotated[int | None, TableId('test_error_handling')] = None
    name: str
    email: str | None = None


class TestErrorHandling:
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
                CREATE TABLE IF NOT EXISTS test_error_handling (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE
                )
            ''')
            await db.execute_mutation("DELETE FROM test_error_handling")
            yield db
            await db.execute_mutation("DELETE FROM test_error_handling")

    @pytest.mark.asyncio
    async def test_get_by_key_or_fail_not_found(self, db: Commondao) -> None:
        with pytest.raises(NotFoundError):
            await db.get_by_key_or_fail(ErrorHandlingRecord, key={'id': 999})

    @pytest.mark.asyncio
    async def test_select_one_or_fail_not_found(self, db: Commondao) -> None:
        from pydantic import BaseModel

        class TestRecord(BaseModel):
            id: int
            name: str
            email: str

        with pytest.raises(NotFoundError):
            await db.select_one_or_fail(
                'select * from test_error_handling where id = :id',
                TestRecord,
                {'id': 999}
            )

    @pytest.mark.asyncio
    async def test_get_by_key_returns_none(self, db: Commondao) -> None:
        result = await db.get_by_key(ErrorHandlingRecord, key={'id': 999})
        assert result is None

    @pytest.mark.asyncio
    async def test_select_one_returns_none(self, db: Commondao) -> None:

        class TestRecord(BaseModel):
            id: int
            name: str
            email: str

        result = await db.select_one(
            'select * from test_error_handling where id = :id',
            TestRecord,
            {'id': 999}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_duplicate_key_error(self, db: Commondao) -> None:
        # 先插入一条记录
        record1 = ErrorHandlingRecord(name='Test User', email='test@example.com')
        await db.insert(record1)

        # 尝试插入相同的email (这应该是唯一的)
        record2 = ErrorHandlingRecord(name='Another User', email='test@example.com')
        affected_rows = await db.insert(record2, ignore=True)

        # 使用ignore=True应该不会抛出异常，但也不会插入记录
        assert affected_rows == 0

        # 验证实际上只有一条记录
        result = await db.execute_query("SELECT COUNT(*) as count FROM test_error_handling")
        assert result[0]['count'] == 1
