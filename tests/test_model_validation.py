import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel

from commondao import is_row_dict
from commondao.annotation import TableId
from commondao.commondao import dump_entity_to_row, get_table_meta, validate_row


class UserKV(BaseModel):
    """Test nested model for complex field validation."""
    key: str
    value: int


class Gender(Enum):
    """Test enum for enum field validation."""
    MALE = 'M'
    FEMALE = 'F'


class UserModel(BaseModel):
    """Test model representing a user with various field types."""
    id: Annotated[int | None, TableId('tbl_user')] = None
    name: str
    age: int | None = None
    birthday: date
    is_admin: bool = False
    kv_list: list[int]
    kv_map: dict[str, int] | None = None
    kv_obj: UserKV | None = None
    created_at: datetime | None = None
    dec_val: Decimal
    buf: bytes
    time_diff: timedelta
    gender: Gender | None = None


class TestModelValidation(unittest.TestCase):
    """Test cases for model validation and serialization functionality."""

    def test_get_table_meta(self) -> None:
        """Test getting table metadata from a model."""
        pk_field, table_meta = get_table_meta(UserModel)
        self.assertEqual(pk_field, 'id')
        self.assertEqual(table_meta.tablename, 'tbl_user')

    def test_validate_row_full_data(self) -> None:
        """Test validating a complete row with all fields."""
        row = {
            'id': 1,
            'name': 'John Doe',
            'age': 25,
            'birthday': '1990-01-01',
            'is_admin': 1,  # MySQL returns 1/0 for boolean
            'created_at': datetime.now().isoformat(),
            'kv_list': '[1,2,3]',  # JSON string as returned by MySQL
            'kv_map': '{"a":1,"b":2}',  # JSON string as returned by MySQL
            'kv_obj': '{"key":"test_key","value":42}',  # JSON string as returned by MySQL
            'dec_val': Decimal('19.99'),
            'buf': b'hello world',
            'time_diff': timedelta(hours=2, minutes=30),
            'gender': 'M',
            'extra_field': 'ignored',  # Should be ignored
        }

        assert is_row_dict(row)
        user = validate_row(row, UserModel)

        self.assertEqual(user.id, 1)
        self.assertEqual(user.name, 'John Doe')
        self.assertEqual(user.age, 25)
        self.assertEqual(user.birthday, date(1990, 1, 1))
        self.assertTrue(user.is_admin)
        self.assertEqual(user.kv_list, [1, 2, 3])
        self.assertEqual(user.kv_map, {'a': 1, 'b': 2})
        self.assertIsInstance(user.kv_obj, UserKV)
        assert user.kv_obj is not None
        self.assertEqual(user.kv_obj.key, 'test_key')
        self.assertEqual(user.kv_obj.value, 42)
        self.assertEqual(user.dec_val, Decimal('19.99'))
        self.assertEqual(user.buf, b'hello world')
        self.assertEqual(user.time_diff, timedelta(hours=2, minutes=30))
        self.assertEqual(user.gender, Gender.MALE)

    def test_validate_row_minimal_data(self) -> None:
        """Test validating a row with only required fields."""
        row = {
            'name': 'Jane Smith',
            'birthday': '1995-05-15',
            'kv_list': '[4, 5, 6]',
            'dec_val': Decimal('29.99'),
            'buf': b'test data',
            'time_diff': timedelta(minutes=45),
        }

        assert is_row_dict(row)
        user = validate_row(row, UserModel)

        self.assertIsNone(user.id)
        self.assertEqual(user.name, 'Jane Smith')
        self.assertIsNone(user.age)
        self.assertEqual(user.birthday, date(1995, 5, 15))
        self.assertFalse(user.is_admin)  # Default value
        self.assertEqual(user.kv_list, [4, 5, 6])
        self.assertIsNone(user.kv_map)
        self.assertIsNone(user.kv_obj)
        self.assertIsNone(user.created_at)
        self.assertEqual(user.dec_val, Decimal('29.99'))
        self.assertEqual(user.buf, b'test data')
        self.assertEqual(user.time_diff, timedelta(minutes=45))
        self.assertIsNone(user.gender)

    def test_dump_entity_to_row_full_data(self) -> None:
        """Test converting a model instance to row dict with all fields."""
        user = UserModel(
            id=1,
            name='Test User',
            age=30,
            birthday=date(1993, 8, 20),
            is_admin=True,
            kv_list=[1, 2, 3],
            kv_map={'x': 10, 'y': 20},
            kv_obj=UserKV(key='sample', value=100),
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            dec_val=Decimal('99.99'),
            buf=b'binary data',
            time_diff=timedelta(days=1),
            gender=Gender.FEMALE,
        )

        row = dump_entity_to_row(user, exclude_unset=True, exclude_none=True)

        self.assertTrue(is_row_dict(row))
        self.assertEqual(row['id'], 1)
        self.assertEqual(row['name'], 'Test User')
        self.assertEqual(row['age'], 30)
        self.assertEqual(row['birthday'], date(1993, 8, 20))
        self.assertEqual(row['is_admin'], True)
        # Complex types should be JSON encoded
        self.assertEqual(row['kv_list'], '[1,2,3]')
        self.assertEqual(row['kv_map'], '{"x":10,"y":20}')
        self.assertEqual(row['kv_obj'], '{"key":"sample","value":100}')
        self.assertEqual(row['created_at'], datetime(2023, 1, 1, 12, 0, 0))
        self.assertEqual(row['dec_val'], Decimal('99.99'))
        self.assertEqual(row['buf'], b'binary data')
        self.assertEqual(row['time_diff'], timedelta(days=1))
        # Enum should be converted to value
        self.assertEqual(row['gender'], 'F')

    def test_dump_entity_to_row_exclude_none(self) -> None:
        """Test converting a model instance to row dict excluding None values."""
        user = UserModel(
            name='Minimal User',
            birthday=date(2000, 1, 1),
            kv_list=[],
            dec_val=Decimal('0.00'),
            buf=b'',
            time_diff=timedelta(0),
        )

        row = dump_entity_to_row(user, exclude_unset=True, exclude_none=True)

        self.assertTrue(is_row_dict(row))
        # None values should be excluded
        self.assertNotIn('id', row)
        self.assertNotIn('age', row)
        self.assertNotIn('kv_map', row)
        self.assertNotIn('kv_obj', row)
        self.assertNotIn('created_at', row)
        self.assertNotIn('gender', row)

        # Non-None values should be included
        self.assertEqual(row['name'], 'Minimal User')
        self.assertEqual(row['birthday'], date(2000, 1, 1))
        self.assertNotIn('is_admin', row)
        self.assertEqual(row['kv_list'], '[]')
        self.assertEqual(row['dec_val'], Decimal('0.00'))
        self.assertEqual(row['buf'], b'')
        self.assertEqual(row['time_diff'], timedelta(0))

    def test_dump_entity_to_row_include_none(self) -> None:
        """Test converting a model instance to row dict including None values."""
        user = UserModel(
            name='User With None',
            birthday=date(2000, 1, 1),
            kv_list=[7, 8, 9],
            dec_val=Decimal('15.50'),
            buf=b'some data',
            time_diff=timedelta(hours=3),
        )

        row = dump_entity_to_row(user, exclude_unset=False, exclude_none=False)

        self.assertTrue(is_row_dict(row))
        # None values should be included
        self.assertIn('id', row)
        self.assertIn('age', row)
        self.assertIn('kv_map', row)
        self.assertIn('kv_obj', row)
        self.assertIn('created_at', row)
        self.assertIn('gender', row)

        # Check None values
        self.assertIsNone(row['id'])
        self.assertIsNone(row['age'])
        self.assertIsNone(row['kv_map'])
        self.assertIsNone(row['kv_obj'])
        self.assertIsNone(row['created_at'])
        self.assertIsNone(row['gender'])

    def test_json_field_handling(self) -> None:
        """Test handling of JSON fields in string format (as returned by MySQL)."""
        # Simulate data returned from MySQL where JSON fields are strings
        row = {
            'name': 'JSON Test User',
            'birthday': '1988-12-12',
            'kv_list': '[10, 20, 30]',  # JSON string
            'kv_map': '{"key1": 100, "key2": 200}',  # JSON string
            'kv_obj': '{"key": "json_test", "value": 999}',  # JSON string
            'dec_val': Decimal('123.45'),
            'buf': b'json test',
            'time_diff': timedelta(hours=6),
        }

        assert is_row_dict(row)
        user = validate_row(row, UserModel)

        self.assertEqual(user.name, 'JSON Test User')
        self.assertEqual(user.kv_list, [10, 20, 30])
        self.assertEqual(user.kv_map, {'key1': 100, 'key2': 200})
        self.assertIsInstance(user.kv_obj, UserKV)
        assert user.kv_obj is not None
        self.assertEqual(user.kv_obj.key, 'json_test')
        self.assertEqual(user.kv_obj.value, 999)

    def test_roundtrip_conversion(self) -> None:
        """Test converting model to row and back to model."""
        original_user = UserModel(
            id=42,
            name='Roundtrip User',
            age=35,
            birthday=date(1988, 4, 15),
            is_admin=True,
            kv_list=[100, 200, 300],
            kv_map={'test': 500},
            kv_obj=UserKV(key='roundtrip', value=777),
            created_at=datetime(2023, 6, 15, 14, 30, 0),
            dec_val=Decimal('456.78'),
            buf=b'roundtrip test',
            time_diff=timedelta(days=2, hours=4),
            gender=Gender.MALE,
        )

        # Convert to row
        row = dump_entity_to_row(original_user, exclude_unset=True, exclude_none=True)
        self.assertTrue(is_row_dict(row))

        # Convert back to model
        restored_user = validate_row(row, UserModel)

        # Compare all fields
        self.assertEqual(restored_user.id, original_user.id)
        self.assertEqual(restored_user.name, original_user.name)
        self.assertEqual(restored_user.age, original_user.age)
        self.assertEqual(restored_user.birthday, original_user.birthday)
        self.assertEqual(restored_user.is_admin, original_user.is_admin)
        self.assertEqual(restored_user.kv_list, original_user.kv_list)
        self.assertEqual(restored_user.kv_map, original_user.kv_map)
        assert restored_user.kv_obj is not None
        assert original_user.kv_obj is not None
        self.assertEqual(restored_user.kv_obj.key, original_user.kv_obj.key)
        self.assertEqual(restored_user.kv_obj.value, original_user.kv_obj.value)
        self.assertEqual(restored_user.created_at, original_user.created_at)
        self.assertEqual(restored_user.dec_val, original_user.dec_val)
        self.assertEqual(restored_user.buf, original_user.buf)
        self.assertEqual(restored_user.time_diff, original_user.time_diff)
        self.assertEqual(restored_user.gender, original_user.gender)


if __name__ == "__main__":
    unittest.main()
