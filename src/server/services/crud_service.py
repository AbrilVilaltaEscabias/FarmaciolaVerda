"""Generic CRUD behaviour shared by every main-entity service."""
from typing import Any, Callable

from src.server.domain.exceptions import NotFoundError

UnitOfWorkFactory = Callable[[], Any]


def get_or_raise(repository: Any, entity_id: int, label: str) -> Any:
    entity = repository.get(entity_id)
    if entity is None:
        raise NotFoundError(f"{label} {entity_id} not found")
    return entity


class CrudService:
    """Create / read / update / delete / list for one entity.

    Subclasses only declare what is specific to them: the model, the name
    of its repository in the unit of work and the model -> DTO converters.
    Every method opens its own unit of work, so one call is one transaction.
    """

    _label: str
    _repository: str  # attribute of the unit of work
    _model: type
    _to_dto: Callable[[Any], Any]
    _to_list_dto: Callable[[Any], Any]

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def create(self, **fields: Any) -> Any:
        with self._uow_factory() as uow:
            entity = self._model(**fields)
            self._repo(uow).add(entity)
            uow.flush()
            return self._to_dto(entity)

    def get(self, entity_id: int) -> Any:
        with self._uow_factory() as uow:
            return self._to_dto(self._find(uow, entity_id))

    def update(self, entity_id: int, **changes: Any) -> Any:
        with self._uow_factory() as uow:
            entity = self._find(uow, entity_id)
            self._apply_changes(uow, entity, changes)
            self._repo(uow).update(entity)
            uow.flush()
            return self._to_dto(entity)

    def delete(self, entity_id: int) -> None:
        with self._uow_factory() as uow:
            self._find(uow, entity_id)
            self._repo(uow).delete(entity_id)

    def list_all(self) -> list:
        with self._uow_factory() as uow:
            return [self._to_list_dto(e) for e in self._repo(uow).get_all()]

    # ------------------------------------------------------------ helpers
    def _repo(self, uow: Any) -> Any:
        return getattr(uow, self._repository)

    def _find(self, uow: Any, entity_id: int) -> Any:
        return get_or_raise(self._repo(uow), entity_id, self._label)

    def _apply_changes(self, uow: Any, entity: Any, changes: dict) -> None:
        for name, value in changes.items():
            setattr(entity, name, value)
