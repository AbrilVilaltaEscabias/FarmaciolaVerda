from sqlalchemy import Table, Column, ForeignKey
from ...infrastructure.db import Base

wish_list_plant_table = Table(
    "wish_list_plant", Base.metadata,
    Column("id_plant", ForeignKey("ingredient.id"), primary_key=True),
    Column("id_user", ForeignKey("users.id"), primary_key=True),
)