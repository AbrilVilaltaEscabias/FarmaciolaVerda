"""Operations and entities supported by the protocol.

Every request is "do <Operation> on <Entity>". Relations (many-to-many,
recipe ingredients...) are modelled as entities of their own, so the five
CRUD operations are enough for the whole application.
"""
from enum import Enum


class Operation(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"


class Entity(str, Enum):
    # Main entities
    USER = "user"
    RECIPE = "recipe"
    INGREDIENT = "ingredient"
    CATEGORY = "category"
    PROPERTY = "property"
    # Relations
    WISH_LIST_RECIPE = "wish_list_recipe"          # user <-> recipe
    WISH_LIST_INGREDIENT = "wish_list_ingredient"  # user <-> ingredient
    RECIPE_CATEGORY = "recipe_category"            # recipe <-> category
    RECIPE_INGREDIENT = "recipe_ingredient"        # recipe <-> ingredient
    INGREDIENT_PROPERTY = "ingredient_property"    # ingredient <-> property