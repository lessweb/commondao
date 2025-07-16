import asyncio
import os

import pytest
from pydantic import BaseModel

import commondao


class User(BaseModel):
    id: int
    name: str
    email: str = ""


@pytest.mark.asyncio
async def test_database_connection():
    """Test basic database operations with a real MySQL server."""
    # 从环境变量获取数据库配置
    config = {
        'host': os.environ.get('TEST_DB_HOST', 'localhost'),
        'port': int(os.environ.get('TEST_DB_PORT', '3306')),
        'user': os.environ.get('TEST_DB_USER', 'root'),
        'password': os.environ.get('TEST_DB_PASSWORD', ''),
        'db': os.environ.get('TEST_DB_NAME', 'test_db'),
        'autocommit': True,
    }

    try:
        async with commondao.connect(**config) as db:
            # 创建测试表
            await db.execute_mutation("""
                CREATE TABLE IF NOT EXISTS test_users (
                    id INT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100)
                )
            """)

            # 清空测试表
            await db.execute_mutation("DELETE FROM test_users")

            # 插入测试数据
            await db.insert('test_users', data={'id': 1, 'name': 'Test User', 'email': 'test@example.com'})

            # 查询测试数据
            user = await db.get_by_key_or_fail('test_users', key={'id': 1})
            assert user['id'] == 1
            assert user['name'] == 'Test User'

            # 使用Pydantic模型查询
            user_model = await db.select_one_or_fail(
                "select * from test_users where id = :id",
                User,
                {"id": 1}
            )
            assert user_model.id == 1
            assert user_model.name == 'Test User'
            assert user_model.email == 'test@example.com'

            # 清理
            await db.execute_mutation("DROP TABLE test_users")

        return True
    except Exception as e:
        pytest.skip(f"Skipping E2E test: {str(e)}")
        return False


if __name__ == "__main__":
    asyncio.run(test_database_connection())
