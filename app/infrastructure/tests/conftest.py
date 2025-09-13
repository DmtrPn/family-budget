# import pytest
# from uuid import UUID
# from typing import Optional
# from app.db.owner_storage import OwnerStorage
#
#
# @pytest.fixture(scope="function")
# def owner_storage(storage_factory):
#     return storage_factory(OwnerStorage)
#
#
# @pytest.fixture(scope="function")
# def create_owner(owner_storage, owner_id):
#     """
#     Фикстура для создания владельца с заданным ID.
#     """
#     from app.db.owner_storage import OwnerConfig
#
#     def _create(force_id: Optional[UUID] = None):
#         """
#         Вспомогательная функция.
#         :param owner_id: UUID владельца.
#         :return: созданный объект владельца.
#         """
#         # Попробовать получить владельца
#         id = force_id or owner_id
#         owner = owner_storage.get(id)
#         if owner is None:
#             # Если нет, создать конфигурацию владельца
#             config = OwnerConfig(id=id, tg_id=112, name="Default Owner")
#             owner_storage.add(config)
#             # Заново получить из хранилища
#             owner = owner_storage.get(id)
#         return owner
#
#     return _create
