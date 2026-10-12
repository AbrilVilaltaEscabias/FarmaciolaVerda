from typing import TYPE_CHECKING
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ...infrastructure.db import Base
from .recipe_category_table import recipe_category_table

if TYPE_CHECKING:
    from .recipe import Recipe


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)

    # M to N
    recipes: Mapped[list["Recipe"]] = relationship(
        secondary=recipe_category_table, back_populates="categories"
    )