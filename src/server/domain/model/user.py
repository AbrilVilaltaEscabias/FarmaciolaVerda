from typing import TYPE_CHECKING
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ...infrastructure.db import Base
from .wish_list_recipes_table import wish_list_recipes_table
from .wish_list_plant_table import wish_list_plant_table

if TYPE_CHECKING:
    from .user_profile import UserProfile
    from .recipe import Recipe
    from .ingredient import Ingredient


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_name: Mapped[str] = mapped_column(String, nullable=False)
    alias: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String, nullable=True)
    password: Mapped[str] = mapped_column(String, nullable=False)  # guarda un hash!

    # 1 to 1
    profile: Mapped["UserProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    # M to N
    recipes: Mapped[list["Recipe"]] = relationship(
        secondary=wish_list_recipes_table, back_populates="users"
    )
    plants: Mapped[list["Ingredient"]] = relationship(
        secondary=wish_list_plant_table, back_populates="users"
    )