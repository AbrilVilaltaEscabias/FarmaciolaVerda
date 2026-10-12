from sqlalchemy import Table, Column, ForeignKey
from ...infrastructure.db import Base

wish_list_recipes_table = Table(
    "wish_list_recipes", Base.metadata,
    Column("id_recipe", ForeignKey("recipe.id"), primary_key=True),
    Column("id_user", ForeignKey("users.id"), primary_key=True),
)