"""Business logic for ingredients (medicinal plants)."""
from src.server.domain.model import Ingredient
from src.server.services.crud_service import CrudService
from src.server.services.mappers import to_ingredient


class IngredientService(CrudService):
    _label = "Ingredient"
    _repository = "ingredients"
    _model = Ingredient
    _to_dto = staticmethod(to_ingredient)
    _to_list_dto = staticmethod(to_ingredient)
