
from ..abstract_repositories import AbstractRepository
from ...domain.model.category import Category


class CategoryRepository(AbstractRepository[str, Category]):

    def _validate(self, category: Category) -> None:
        if category.name is None:
            raise ValueError("Name attribute is mandatory")
