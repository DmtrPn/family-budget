import pytest
import uuid
from app.infrastructure.example_storage import ExampleStorage
from app.constants import ExampleStatus
from app.domain.example_dto import ExampleCreateParams


@pytest.fixture(scope="function")
def storage(storage_factory):
    return storage_factory(ExampleStorage)


async def test_add_example(storage: ExampleStorage):
    config = ExampleCreateParams(id=uuid.uuid4(), status=ExampleStatus.active)
    await storage.add(config)

    result = await storage.get(config.id)
    assert result is not None
    assert result.id == config.id
    assert result.status == config.status
