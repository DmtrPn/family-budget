import uuid
from sqlalchemy import select

from app.application.abastract.i_example_storage import IExampleStorage
from app.infrastructure.abstract.base_storage import BaseStorage
from app.infrastructure.models.example_model import ExampleModel
from app.domain.example_dto import ExampleCreateParams


class ExampleStorage(BaseStorage, IExampleStorage):
    async def add(self, config: ExampleCreateParams):
        async with self.session_scope() as session:
            owner = ExampleModel(id=config.id, status=config.status)
            session.add(owner)

    async def get(self, id: uuid.UUID) -> ExampleModel | None:
        async with self.session_scope(read_only=True) as session:
            result = await session.execute(select(ExampleModel).filter_by(id=id))
            return result.scalars().first()
