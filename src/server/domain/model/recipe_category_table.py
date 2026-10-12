from sqlalchemy import Table, Column, ForeignKey
from ...infrastructure.db import Base

recipe_category_table = Table(
    "recipe_category", Base.metadata,
    Column("id_recipe", ForeignKey("recipe.id"), primary_key=True),
    Column("id_category", ForeignKey("category.id"), primary_key=True),
)