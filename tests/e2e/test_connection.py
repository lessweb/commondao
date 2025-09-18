import os
from typing import Annotated, Optional

import pytest
import pytest_asyncio
from pydantic import BaseModel

from commondao import connect
from commondao.annotation import TableId


class DbConfig:
    """测试数据库配置"""
    def __init__(self):
        self.host = os.environ.get('TEST_DB_HOST', 'localhost')
        self.port = int(os.environ.get('TEST_DB_PORT', '3306'))
        self.user = os.environ.get('TEST_DB_USER', 'root')
        self.password = os.environ.get('TEST_DB_PASSWORD', 'rootpassword')
        self.db = os.environ.get('TEST_DB_NAME', 'test_db')


class User(BaseModel):
    """用户模型，用于测试数据验证"""
    id: Annotated[Optional[int], TableId('test_users')] = None
    name: str
    email: str
    age: Optional[int] = None


@pytest_asyncio.fixture
async def setup_test_table():
    """创建测试表并在测试结束后删除"""
    config = DbConfig()
    db_config = {
        'host': config.host,
        'port': config.port,
        'user': config.user,
        'password': config.password,
        'db': config.db,
        'autocommit': True,
    }
    async with connect(**db_config) as db:
        # 创建测试表
        await db.execute_mutation("""
            DROP TABLE IF EXISTS test_users;
            CREATE TABLE IF NOT EXISTS test_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) NOT NULL,
                age INT
            )
        """)
        # 验证表已创建
        verify = await db.execute_query("SHOW TABLES LIKE 'test_users'")
        assert verify, "测试表未能成功创建"
        # 插入测试数据
        test_user = User(name='Test User', email='test@example.com')
        await db.insert(test_user)

    yield

    # 清理测试表
    async with connect(**db_config) as db:
        await db.execute_mutation("DROP TABLE IF EXISTS test_users")


@pytest.mark.asyncio
async def test_connection():
    """测试数据库连接是否成功"""
    config = DbConfig()
    db_config = {
        'host': config.host,
        'port': config.port,
        'user': config.user,
        'password': config.password,
        'db': config.db,
    }
    async with connect(**db_config) as db:
        result = await db.execute_query("SELECT 1 as test")
        assert result[0]['test'] == 1


@pytest.mark.asyncio
async def test_basic_operations(setup_test_table):
    """测试基本的数据库操作"""
    config = DbConfig()
    db_config = {
        'host': config.host,
        'port': config.port,
        'user': config.user,
        'password': config.password,
        'db': config.db,
        'autocommit': True,
    }
    async with connect(**db_config) as db:
        # 测试插入
        john_user = User(name='John Doe', email='john@example.com')
        await db.insert(john_user)
        # 测试查询
        user = await db.get_by_key(User, key={'name': 'John Doe'})
        assert user is not None
        assert user.name == 'John Doe'
        assert user.email == 'john@example.com'
        # 测试更新
        updated_user_data = User(id=user.id, name='Jane Doe', email=user.email)
        await db.update_by_key(updated_user_data, key={'id': user.id})
        updated_user = await db.get_by_key_or_fail(User, key={'id': user.id})
        assert updated_user.name == 'Jane Doe'
        # 测试删除
        assert user.id
        await db.delete_by_id(User, user.id)
        deleted_user = await db.get_by_id(User, user.id)
        assert deleted_user is None


@pytest.mark.asyncio
async def test_model_validation(setup_test_table):
    """测试模型验证功能"""
    config = DbConfig()
    db_config = {
        'host': config.host,
        'port': config.port,
        'user': config.user,
        'password': config.password,
        'db': config.db,
        'autocommit': True,
    }
    async with connect(**db_config) as db:
        # 使用select_one查询并验证模型
        user = await db.select_one("select * from test_users", User)
        assert user is not None
        assert isinstance(user, User)
        assert user.name == 'Test User'
        assert user.email == 'test@example.com'
        # 使用select_all查询所有数据
        users = await db.select_all("select * from test_users", User)
        assert len(users) >= 1
        assert all(isinstance(u, User) for u in users)
