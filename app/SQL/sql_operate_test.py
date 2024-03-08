import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from .sql_operate import SQLOperate
from pydantic import BaseModel

Base = declarative_base()


class ExampleModel(Base):
    __tablename__ = "example"
    id = Column(Integer, primary_key=True, index=True)
    value = Column(String)


# Define a Pydantic model for testing
class TestModel(BaseModel):
    id: int
    value: str = None


def custom_exception(status_code: int, detail: str):
    return HTTPException(status_code=status_code, detail=detail)


# Setup an in-memory SQLite database for testing
@pytest.fixture(scope="module")
def engine():
    return create_engine("sqlite:///:memory:", echo=True)


@pytest.fixture(scope="module")
def tables(engine):
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine, tables):
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    SQLOperate.exc = custom_exception(status_code=484, detail="test")  # Setting the custom exception handler
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# Now, write tests for each method in SQLOperate
def test_create_multiple_sql_data(db_session):
    sqloperate = SQLOperate(custom_exception(status_code=484, detail="test"))
    test_data = [TestModel(id="1", value='Test1').dict(), TestModel(id="2", value='Test2').dict()]
    created = sqloperate.create_multiple_sql_data(db_session, test_data, ExampleModel)
    assert len(created) == 2
    assert db_session.query(ExampleModel).count() == 2


def test_get_sql_data(db_session):
    sqloperate = SQLOperate(custom_exception)
    # Assuming ExampleModel entries are already created in the database
    test_entries = [ExampleModel(id=1, value="Test1"), ExampleModel(id=2, value="Test2")]
    db_session.add_all(test_entries)
    db_session.commit()

    field_value_set = {1, 2}
    fetched_data = sqloperate.get_sql_data(db_session, ExampleModel, field_value_set, "id")
    assert len(fetched_data) == 2


def test_get_all_sql_data(db_session):
    sqloperate = SQLOperate(custom_exception)
    # Populate the database
    test_entries = [ExampleModel(id=3, value="Test3"), ExampleModel(id=4, value="Test4")]
    db_session.add_all(test_entries)
    db_session.commit()

    all_data = sqloperate.get_all_sql_data(db_session, ExampleModel)
    assert len(all_data) >= 2  # Use >= because other tests may also add data


def test_update_multiple_sql_data(db_session):
    sqloperate = SQLOperate(custom_exception)
    # Create initial entries
    test_entries = [ExampleModel(id=5, value="OldValue1"), ExampleModel(id=6, value="OldValue2")]
    db_session.add_all(test_entries)
    db_session.commit()

    # Pydantic models for update
    update_list = [TestModel(id=5, value="NewValue1"), TestModel(id=6, value="NewValue2")]
    updated_entries = sqloperate.update_multiple_sql_data(db_session, update_list, ExampleModel)
    assert all(entry.value.startswith("NewValue") for entry in updated_entries)


def test_delete_multiple_sql_data(db_session):
    sqloperate = SQLOperate(custom_exception)
    # Add entries to be deleted
    test_entries = [ExampleModel(id=7, value="ToDelete1"), ExampleModel(id=8, value="ToDelete2")]
    db_session.add_all(test_entries)
    db_session.commit()

    id_set = {7, 8}
    sqloperate.delete_multiple_sql_data(db_session, id_set, ExampleModel)
    remaining_entries = db_session.query(ExampleModel).filter(ExampleModel.id.in_(id_set)).all()
    assert len(remaining_entries) == 0
