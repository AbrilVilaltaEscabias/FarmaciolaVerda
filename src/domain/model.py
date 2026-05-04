from sqlalchemy import Table, Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from .db import engine, Base

# ── TAULES N to M  ──────────────────────────────────────────────────────────

recipe_category_table = Table(
    "recipe_category", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("id_recipe", ForeignKey("recipe.id"), primary_key=True),
    Column("id_category", ForeignKey("category.id"), primary_key=True)
)

wish_list_recipes_table = Table(
    "wish_list_recipes", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("id_recipe", ForeignKey("recipe.id"), primary_key=True),
    Column("id_user", ForeignKey("user.id"), primary_key=True)
)

wish_list_plant_table = Table(
    "wish_list_plant", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("id_plant", ForeignKey("ingredient.id"), primary_key=True),
    Column("id_user", ForeignKey("user.id"), primary_key=True)
)

plant_property_table = Table(
    "plant_property", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("id_plant", ForeignKey("ingredient.id"), primary_key=True),
    Column("id_property", ForeignKey("property.id"), primary_key=True)
)

# ── CLASSES ─────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_name: Mapped[str] = mapped_column(String, nullable=False)
    alias: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=True)
    password: Mapped[str] = mapped_column(String, nullable=False)

    # 1 to 1
    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)
    # M to N
    recipes: Mapped[list["Recipe"]] = relationship(secondary=wish_list_recipes_table, back_populates="users")
    plants: Mapped[list["Ingredient"]] = relationship(secondary=wish_list_plant_table, back_populates="users")

class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bio: Mapped[str] = mapped_column(String(50), nullable=True)
    img: Mapped[str] = mapped_column(String(1000), nullable=True)
    country: Mapped[str] = mapped_column(String, nullable=True)

    # 1 to 1 — FK amb unique=True
    id_user: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False, unique=True)
    user: Mapped["User"] = relationship(back_populates="profile")


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
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)

    # M to N
    users: Mapped[list["User"]] = relationship(secondary=wish_list_recipes_table, back_populates="recipes")
    categories: Mapped[list["Category"]] = relationship(secondary=recipe_category_table, back_populates="recipes")
    # 1 to M (amb camps extra)
    list_ingredients: Mapped[list["ListIngredients"]] = relationship(back_populates="recipe")


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)

    # M to N
    recipes: Mapped[list["Recipe"]] = relationship(secondary=recipe_category_table, back_populates="categories")


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
    users: Mapped[list["User"]] = relationship(secondary=wish_list_plant_table, back_populates="plants")
    properties: Mapped[list["Property"]] = relationship(secondary=plant_property_table, back_populates="plants")
    # 1 to M
    list_ingredients: Mapped[list["ListIngredients"]] = relationship(back_populates="plant")


class ListIngredients(Base):
    __tablename__ = "list_ingredient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quantity: Mapped[str] = mapped_column(String, nullable=True)
    isoptional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # FKs
    id_recipe: Mapped[int] = mapped_column(Integer, ForeignKey("recipe.id"), nullable=False)
    id_plant: Mapped[int] = mapped_column(Integer, ForeignKey("ingredient.id"), nullable=False)

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="list_ingredients")
    plant: Mapped["Ingredient"] = relationship(back_populates="list_ingredients")


class Property(Base):
    __tablename__ = "property"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)

    # M to N
    plants: Mapped[list["Ingredient"]] = relationship(secondary=plant_property_table, back_populates="properties")