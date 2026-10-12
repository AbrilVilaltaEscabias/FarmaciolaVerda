"""Model -> DTO conversion.

This is the only place where persistence objects are turned into the plain
DTOs sent to the client. Always call these inside the unit of work, while
the session is still open (relationships are loaded lazily).
"""
from src.common.dto import (
    CategoryDTO,
    IngredientDTO,
    IngredientSummaryDTO,
    ListIngredientDTO,
    PropertyDTO,
    RecipeDTO,
    RecipeSummaryDTO,
    UserDTO,
    UserProfileDTO,
)


def to_category(category) -> CategoryDTO:
    return CategoryDTO(
        id=category.id, name=category.name, description=category.description
    )


def to_property(prop) -> PropertyDTO:
    return PropertyDTO(
        id=prop.id, name=prop.name, description=prop.description
    )


def to_ingredient_summary(ingredient) -> IngredientSummaryDTO:
    return IngredientSummaryDTO(
        id=ingredient.id,
        common_name=ingredient.common_name,
        type=ingredient.type,
    )


def to_ingredient(ingredient) -> IngredientDTO:
    return IngredientDTO(
        id=ingredient.id,
        common_name=ingredient.common_name,
        type=ingredient.type,
        scientific_name=ingredient.scientific_name,
        family=ingredient.family,
        description=ingredient.description,
        country_origin=ingredient.country_origin,
        image_url=ingredient.image_url,
        properties=[to_property(p) for p in ingredient.properties],
    )


def to_list_ingredient(list_ingredient) -> ListIngredientDTO:
    return ListIngredientDTO(
        id=list_ingredient.id,
        ingredient=to_ingredient_summary(list_ingredient.plant),
        quantity=list_ingredient.quantity,
        is_optional=bool(list_ingredient.isoptional),
        is_checked=bool(list_ingredient.is_checked),
    )


def to_recipe_summary(recipe) -> RecipeSummaryDTO:
    return RecipeSummaryDTO(
        id=recipe.id, name=recipe.name, duration=recipe.duration
    )


def to_recipe(recipe) -> RecipeDTO:
    created_at = recipe.created_at.isoformat() if recipe.created_at else None
    return RecipeDTO(
        id=recipe.id,
        name=recipe.name,
        step_by_step=recipe.step_by_step,
        duration=recipe.duration,
        sub_name=recipe.sub_name,
        note=recipe.note,
        dosage=recipe.dosage,
        description=recipe.description,
        created_at=created_at,
        categories=[to_category(c) for c in recipe.categories],
        ingredients=[to_list_ingredient(i) for i in recipe.list_ingredients],
    )


def to_user(user) -> UserDTO:
    """The password is deliberately never copied."""
    profile = None
    if user.profile is not None:
        profile = UserProfileDTO(
            bio=user.profile.bio,
            img=user.profile.img,
            country=user.profile.country,
        )
    return UserDTO(
        id=user.id,
        user_name=user.user_name,
        email=user.email,
        alias=user.alias,
        phone=user.phone,
        profile=profile,
        wish_list_recipes=[to_recipe_summary(r) for r in user.recipes],
        wish_list_ingredients=[to_ingredient_summary(i) for i in user.plants],
    )
