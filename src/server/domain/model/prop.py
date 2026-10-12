from typing import TYPE_CHECKING
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ...infrastructure.db import Base
from .plant_property_table import plant_property_table

if TYPE_CHECKING:
    from .ingredient import Ingredient


class Property(Base):
    __tablename__ = "property"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)

    # M to N
    plants: Mapped[list["Ingredient"]] = relationship(
        secondary=plant_property_table, back_populates="properties"
    )