import json
import pytest
import fakeredis
from pydantic import BaseModel


from .redis_operate import RedisOperate  # Adjust the import according to your project structure


# Define a Pydantic model for testing
class TestModel(BaseModel):
    id: str
    value: str = None


@pytest.fixture
def mock_redis():
    """Fixture to create a fake Redis instance."""
    return fakeredis.FakeStrictRedis()


@pytest.fixture
def redis_operate(mock_redis):
    """Fixture to create a RedisOperate instance with a fake Redis instance."""
    class Exc(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

    return RedisOperate(redis_db=mock_redis, exc=Exc)


def test_write_sql_data_to_redis(redis_operate):
    """Test writing SQL data to Redis using a Pydantic model."""
    table_name = "test_table"
    sql_data_list = [{"id": "1", "value": "test_value1"}, {"id": "2", "value": "test_value2"}]
    redis_operate.write_sql_data_to_redis(table_name, sql_data_list, TestModel, key="id")

    # Verify data is written correctly
    stored_data_1 = json.loads(redis_operate.redis.hget(table_name, "1"))
    stored_data_2 = json.loads(redis_operate.redis.hget(table_name, "2"))

    assert stored_data_1 == {"id": "1", "value": "test_value1"}
    assert stored_data_2 == {"id": "2", "value": "test_value2"}


def test_read_redis_data(redis_operate):
    """Test reading data from Redis."""
    redis_operate.redis.hset("test_table", "test_key", json.dumps({"id": "test_key", "value": "test_value"}))
    result = redis_operate.read_redis_data("test_table", {"test_key"})
    assert result == [{"id": "test_key", "value": "test_value"}]


def test_delete_redis_data(redis_operate):
    """Test deleting data from Redis."""
    # Pre-populate Redis with test data
    redis_operate.redis.hset("test_table", "test_key", "test_value")

    # Use the correct Pydantic model in the test
    redis_operate.delete_redis_data("test_table", [{"id": "test_key"}], TestModel, "id")

    # Assertions to verify the deletion
    assert not redis_operate.redis.hexists("test_table", "test_key"), "The key should be deleted from Redis."


def test_read_redis_return_dict(redis_operate):
    """Test reading all data from Redis and returning it as a dictionary."""
    # Pre-populate Redis with test data
    redis_operate.redis.hset("test_table_dict", "key1", json.dumps({"id": "key1", "value": "value1"}))
    redis_operate.redis.hset("test_table_dict", "key2", json.dumps({"id": "key2", "value": "value2"}))

    # Execute the function under test
    result_dict = redis_operate.read_redis_return_dict("test_table_dict")

    # Assertions to verify the data is correctly returned as a dictionary
    assert len(result_dict) == 2, "Should contain two keys"
    assert json.loads(result_dict[b"key1"]) == {"id": "key1", "value": "value1"}, "Mismatched value for key1"
    assert json.loads(result_dict[b"key2"]) == {"id": "key2", "value": "value2"}, "Mismatched value for key2"


def test_read_redis_data_without_exception(redis_operate):
    """Test reading specified data from Redis without raising an exception for missing keys."""
    # Pre-populate Redis with test data
    redis_operate.redis.hset("test_table_no_exception", "existing_key", json.dumps({"id": "existing_key", "value": "existing_value"}))

    # Attempt to read both existing and non-existing keys
    result_list = redis_operate.read_redis_data_without_exception("test_table_no_exception", {"existing_key", "non_existing_key"})

    # Assertions to verify that data for the existing key is returned and the non-existing key is silently ignored
    assert len(result_list) == 1, "Should return data for the existing key only"
    assert result_list[0] == {"id": "existing_key", "value": "existing_value"}, "Mismatched data for existing_key"
