from typing import TYPE_CHECKING
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ...infrastructure.db import Base
from .wish_list_plant_table import wish_list_plant_table
from .plant_property_table import plant_property_table

if TYPE_CHECKING:
    from .user import User
    from .prop import Property
    from .list_ingredients import ListIngredients


class Ingredient(Base):
    __tablename__ = "ingredient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scientific_name: Mapped[str] = mapped_column(String(100), nullable=True)
    common_name: Mapped[str] = mapped_column(String(100), nullable=False)
    family: Mapped[str] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    country_origin: Mapped[str] = mapped_column(String(100), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    image_url: Mapped[str] = mapped_column(String, nullable=True)

    # M to N
    users: Mapped[list["User"]] = relationship(
        secondary=wish_list_plant_table, back_populates="plants"
    )
    properties: Mapped[list["Property"]] = relationship(
        secondary=plant_property_table, back_populates="plants"
    )
    # 1 to M
    list_ingredients: Mapped[list["ListIngredients"]] = relationship(
        back_populates="plant", cascade="all, delete-orphan"
    )