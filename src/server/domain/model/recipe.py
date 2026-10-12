from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ...infrastructure.db import Base
from .wish_list_recipes_table import wish_list_recipes_table
from .recipe_category_table import recipe_category_table

if TYPE_CHECKING:
    from .user import User
    from .category import Category
    from .list_ingredients import ListIngredients


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=True)
    step_by_step: Mapped[str] = mapped_column(String(10000), nullable=False)
    sub_name: Mapped[str] = mapped_column(String(100), nullable=True)
    note: Mapped[str] = mapped_column(String(10000), nullable=True)
    dosage: Mapped[str] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    # M to N
    users: Mapped[list["User"]] = relationship(
        secondary=wish_list_recipes_table, back_populates="recipes"
    )
    categories: Mapped[list["Category"]] = relationship(
        secondary=recipe_category_table, back_populates="recipes"
    )
    # 1 to M (amb camps extra)
    list_ingredients: Mapped[list["ListIngredients"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )