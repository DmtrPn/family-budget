import uuid
from . import BaseModel
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from sqlalchemy.dialects.postgresql import UUID

from app.constants import ExampleStatus

from app.infrastructure.utils.safe_enum import SafeEnumType


class ExampleModel(BaseModel):
    __tablename__ = "example"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[ExampleStatus] = mapped_column(
        SafeEnumType(ExampleStatus),
        nullable=False,
        default=ExampleStatus.active.value,
    )
