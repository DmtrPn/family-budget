from sqlalchemy.orm import declarative_base

# Общая база для всех моделей
DeclarativeModel = declarative_base()


class BaseModel(DeclarativeModel):  # type: ignore[misc,valid-type]
    __abstract__ = True


from .example_model import ExampleModel  # noqa
