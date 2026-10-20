"""
Mapping IMPERATIU de SQLAlchemy: aquí (i només aquí) es diu com les classes
del domini es guarden en taules. El domini no importa res d'aquest fitxer;
és aquest fitxer qui importa el domini.

Cal cridar `start_mappers()` una vegada, a l'arrencada del servidor.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Table,
)
from sqlalchemy.orm import registry, relationship

from server.domain import (
    Category, Ingredient, ListIngredients, Property, Recipe, User, UserProfile,
)

mapper_registry = registry()
metadata = mapper_registry.metadata      # el fan servir create_all i alembic

# ---------- Taules ----------

user_table = Table(
    "user", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_name", String, nullable=False),
    Column("alias", String, nullable=True),
    Column("email", String, nullable=False),
    Column("phone", String, nullable=True),
    Column("password", String, nullable=False),
)

user_profile_table = Table(
    "user_profile", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bio", String(50), nullable=True),
    Column("img", String(1000), nullable=True),
    Column("country", String, nullable=True),
    Column("id_user", Integer, ForeignKey("user.id"), nullable=False, unique=True),
)

recipe_table = Table(
    "recipe", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("duration", Integer, nullable=True),
    Column("step_by_step", String(10000), nullable=False),
    Column("sub_name", String(100), nullable=True),
    Column("note", String(10000), nullable=True),
    Column("dosage", String(100), nullable=True),
    Column("description", String(1000), nullable=True),
    Column("created_at", DateTime, nullable=True),
)

category_table = Table(
    "category", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("description", String, nullable=True),
)

ingredient_table = Table(
    "ingredient", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scientific_name", String(100), nullable=True),
    Column("common_name", String(100), nullable=False),
    Column("family", String(100), nullable=True),
    Column("description", String(1000), nullable=True),
    Column("country_origin", String(100), nullable=True),
    Column("type", String(50), nullable=False),
    Column("image_url", String, nullable=True),
)

property_table = Table(
    "property", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("description", String, nullable=True),
)

list_ingredient_table = Table(
    "list_ingredient", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("quantity", String, nullable=True),
    Column("isoptional", Boolean, nullable=False, default=False),
    Column("is_checked", Boolean, nullable=False, default=False),
    Column("id_recipe", Integer, ForeignKey("recipe.id"), nullable=False),
    Column("id_plant", Integer, ForeignKey("ingredient.id"), nullable=False),
)

# ---------- Taules d'associació (M a N) ----------

recipe_category_table = Table(
    "recipe_category", metadata,
    Column("id_recipe", ForeignKey("recipe.id"), primary_key=True),
    Column("id_category", ForeignKey("category.id"), primary_key=True),
)

wish_list_recipes_table = Table(
    "wish_list_recipes", metadata,
    Column("id_recipe", ForeignKey("recipe.id"), primary_key=True),
    Column("id_user", ForeignKey("user.id"), primary_key=True),
)

wish_list_plant_table = Table(
    "wish_list_plant", metadata,
    Column("id_plant", ForeignKey("ingredient.id"), primary_key=True),
    Column("id_user", ForeignKey("user.id"), primary_key=True),
)

plant_property_table = Table(
    "plant_property", metadata,
    Column("id_plant", ForeignKey("ingredient.id"), primary_key=True),
    Column("id_property", ForeignKey("property.id"), primary_key=True),
)


# ---------- Mapping classe <-> taula ----------

def start_mappers():
    if mapper_registry.mappers:          # ja s'ha cridat: no tornar-ho a fer
        return

    map_ = mapper_registry.map_imperatively

    map_(User, user_table, properties={
        "profile": relationship(UserProfile, back_populates="user", uselist=False),
        "recipes": relationship(Recipe, secondary=wish_list_recipes_table, back_populates="users"),
        "plants": relationship(Ingredient, secondary=wish_list_plant_table, back_populates="users"),
    })

    map_(UserProfile, user_profile_table, properties={
        "user": relationship(User, back_populates="profile"),
    })

    map_(Recipe, recipe_table, properties={
        "users": relationship(User, secondary=wish_list_recipes_table, back_populates="recipes"),
        "categories": relationship(Category, secondary=recipe_category_table, back_populates="recipes"),
        "list_ingredients": relationship(ListIngredients, back_populates="recipe"),
    })

    map_(Category, category_table, properties={
        "recipes": relationship(Recipe, secondary=recipe_category_table, back_populates="categories"),
    })

    map_(Ingredient, ingredient_table, properties={
        "users": relationship(User, secondary=wish_list_plant_table, back_populates="plants"),
        "properties": relationship(Property, secondary=plant_property_table, back_populates="plants"),
        "list_ingredients": relationship(ListIngredients, back_populates="plant"),
    })

    map_(Property, property_table, properties={
        "plants": relationship(Ingredient, secondary=plant_property_table, back_populates="properties"),
    })

    map_(ListIngredients, list_ingredient_table, properties={
        "recipe": relationship(Recipe, back_populates="list_ingredients"),
        "plant": relationship(Ingredient, back_populates="list_ingredients"),
    })
