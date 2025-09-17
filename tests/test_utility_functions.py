import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from commondao.annotation import RawSql
from commondao.commondao import (
    RegexCollect,
    and_,
    is_list_type,
    is_query_dict,
    is_row_dict,
    join,
    script,
    where,
)


class TestUtilityFunctions(unittest.TestCase):
    def test_is_row_dict_valid_values(self) -> None:
        valid_data: Dict[str, Any] = {
            "str_val": "test",
            "int_val": 123,
            "float_val": 123.45,
            "decimal_val": Decimal("123.45"),
            "bytes_val": b"test",
            "datetime_val": datetime.now(),
            "date_val": date.today(),
            "time_val": datetime.now().time(),
            "timedelta_val": timedelta(days=1),
            "null_val": None
        }
        self.assertTrue(is_row_dict(valid_data))

    def test_is_row_dict_invalid_values(self) -> None:
        invalid_data_list: Dict[str, Any] = {"key": ["value1", "value2"]}
        invalid_data_dict: Dict[str, Any] = {"key": {"nested": "value"}}
        invalid_data_tuple: Dict[str, Any] = {"key": (1, 2, 3)}
        invalid_data_set: Dict[str, Any] = {"key": {1, 2, 3}}
        invalid_data_bool: Dict[str, Any] = {"key": True}
        self.assertFalse(is_row_dict(invalid_data_list))
        self.assertFalse(is_row_dict(invalid_data_dict))
        self.assertFalse(is_row_dict(invalid_data_tuple))
        self.assertFalse(is_row_dict(invalid_data_set))
        self.assertTrue(is_row_dict(invalid_data_bool))

    def test_is_row_dict_empty_dict(self) -> None:
        empty_dict: Dict[str, Any] = {}
        self.assertTrue(is_row_dict(empty_dict))

    def test_is_query_dict_valid_values(self) -> None:
        valid_data: Dict[str, Any] = {
            "str_val": "test",
            "int_val": 123,
            "float_val": 123.45,
            "decimal_val": Decimal("123.45"),
            "bytes_val": b"test",
            "datetime_val": datetime.now(),
            "date_val": date.today(),
            "time_val": datetime.now().time(),
            "timedelta_val": timedelta(days=1),
            "list_val": [1, 2, 3],
            "tuple_val": (1, 2, 3),
            "null_val": None
        }
        self.assertTrue(is_query_dict(valid_data))

    def test_is_query_dict_invalid_values(self) -> None:
        invalid_data_dict: Dict[str, Any] = {"key": {"nested": "value"}}
        invalid_data_set: Dict[str, Any] = {"key": {1, 2, 3}}
        invalid_data_bool: Dict[str, Any] = {"key": True}
        self.assertFalse(is_query_dict(invalid_data_dict))
        self.assertFalse(is_query_dict(invalid_data_set))
        self.assertTrue(is_query_dict(invalid_data_bool))

    def test_is_query_dict_empty_dict(self) -> None:
        empty_dict: Dict[str, Any] = {}
        self.assertTrue(is_query_dict(empty_dict))

    def test_is_list_type(self) -> None:
        from typing import List as TypingList
        self.assertTrue(is_list_type(list))
        self.assertTrue(is_list_type(List[int]))
        self.assertTrue(is_list_type(TypingList[str]))
        self.assertFalse(is_list_type(tuple))
        self.assertFalse(is_list_type(dict))
        self.assertFalse(is_list_type(set))
        self.assertFalse(is_list_type(int))
        self.assertFalse(is_list_type(str))

    def test_script_function(self) -> None:
        result = script("select", "*", "from", "users", "where", "id = 1")
        self.assertEqual(result, "select * from users where id = 1")
        result_with_none = script("select", "*", "from", "users", None, "where", "id = 1")
        self.assertEqual(result_with_none, "select * from users  where id = 1")
        result_empty = script()
        self.assertEqual(result_empty, "")

    def test_join_function(self) -> None:
        result = join("id", "name", "email")
        self.assertEqual(result, "id,name,email")
        result_with_none = join("id", None, "name", "email")
        self.assertEqual(result_with_none, "id,name,email")
        result_empty = join()
        self.assertEqual(result_empty, "")

    def test_and_function(self) -> None:
        result = and_("id = 1", "name = 'test'")
        self.assertEqual(result, "(id = 1 and name = 'test')")
        result_with_none = and_(None, "id = 1", None, "name = 'test'")
        self.assertEqual(result_with_none, "(id = 1 and name = 'test')")
        result_empty = and_()
        self.assertEqual(result_empty, "")

    def test_where_function(self) -> None:
        result = where("id = 1", "name = 'test'")
        self.assertEqual(result, "where (id = 1 and name = 'test') ")
        result_with_none = where(None, "id = 1", None, "name = 'test'")
        self.assertEqual(result_with_none, "where (id = 1 and name = 'test') ")
        result_empty = where()
        self.assertEqual(result_empty, "")

    def test_raw_sql(self) -> None:
        raw_sql = RawSql("COUNT(*)")
        self.assertEqual(raw_sql.sql, "COUNT(*)")
        raw_sql = RawSql("CONCAT(first_name, ' ', last_name)")
        self.assertEqual(raw_sql.sql, "CONCAT(first_name, ' ', last_name)")

    def test_regex_collect(self) -> None:
        # 测试基本参数替换
        rc = RegexCollect()
        sql = "SELECT * FROM users WHERE id = :id AND name = :name"
        params = {"id": 1, "name": "John"}
        pg_sql, pg_params = rc.build(sql, params)
        self.assertEqual(pg_sql, "SELECT * FROM users WHERE id = %s AND name = %s")
        self.assertEqual(pg_params, (1, "John"))
        # 测试带点的参数名
        rc = RegexCollect()
        sql = "SELECT * FROM users WHERE user.id = :user.id"
        params = {"user.id": 1}
        pg_sql, pg_params = rc.build(sql, params)
        self.assertEqual(pg_sql, "SELECT * FROM users WHERE user.id = %s")
        self.assertEqual(pg_params, (1,))
        # 测试没有参数的情况
        rc = RegexCollect()
        sql = "SELECT * FROM users"
        params = {}
        pg_sql, pg_params = rc.build(sql, params)
        self.assertEqual(pg_sql, "SELECT * FROM users")
        self.assertEqual(pg_params, ())
        # 测试参数在词中间的情况（不应被替换）
        rc = RegexCollect()
        sql = "SELECT * FROM users WHERE name=\n:name AND email LIKE 'a:id@example.com'"
        params = {"id": 1, "name": "John"}
        pg_sql, pg_params = rc.build(sql, params)
        self.assertEqual(pg_sql, "SELECT * FROM users WHERE name=\n%s AND email LIKE 'a:id@example.com'")
        self.assertEqual(pg_params, ('John',))


if __name__ == "__main__":
    unittest.main()
