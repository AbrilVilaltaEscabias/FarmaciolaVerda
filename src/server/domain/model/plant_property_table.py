from sqlalchemy import Table, Column, ForeignKey
from ...infrastructure.db import Base

plant_property_table = Table(
    "plant_property", Base.metadata,
    Column("id_plant", ForeignKey("ingredient.id"), primary_key=True),
    Column("id_property", ForeignKey("property.id"), primary_key=True),
)