from sqlalchemy.types import TypeDecorator, String
from enum import Enum


class SafeEnumType(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, enum_cls: type[Enum], *args, **kwargs):
        self.enum_cls = enum_cls
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if isinstance(value, Enum):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        try:
            return self.enum_cls(value)
        except ValueError:
            return value
