"""Command-line client for the recipes backoffice.

It only talks to the server through SocketClient: no database, no models,
no business rules. Run with:  python -m src.client.app
"""
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Optional

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

from src.client.socket_client import SocketClient
from src.common.dto import IngredientDTO, RecipeDTO, RecipeSummaryDTO
from src.common.operations import Entity, Operation
from src.common.protocol import Response


# ·························································
# · STYLE AND OUTPUT HELPERS                              ·
# ·························································

def accent(text: str) -> str:
    return f"[bold medium_orchid]{text}[/bold medium_orchid]"


def highlight(text: str) -> str:
    return f"[bold dark_sea_green3]{text}[/bold dark_sea_green3]"


def show_error(console: Console, message: str) -> None:
    console.print(f"[bold red]{escape(message)}[/bold red]")


def show_success(console: Console, message: str) -> None:
    console.print(highlight(escape(message)))


def display(value: Any) -> str:
    """Printable, markup-safe version of a value ('-' when empty)."""
    return "-" if value in (None, "") else escape(str(value))


def show_title(console: Console) -> None:
    print()
    console.print("""[bold medium_orchid] \\    / _  |  _  _  ._ _   _    _|_  _  
  \\/\\/ (/_ | (_ (_) | | | (/_    |_ (_) [/bold medium_orchid][bold dark_sea_green3]
 ____  __   ____  _  _   __    ___  __  __   __     __     _  _  ____  ____  ____   __  
(  __)/ _\\ (  _ \\( \\/ ) / _\\  / __)(  )/  \\ (  )   / _\\   / )( \\(  __)(  _ \\(    \\ / _\\ 
 ) _)/    \\ )   // \\/ \\/    \\( (__  )((  O )/ (_/\\/    \\  \\ \\/ / ) _)  )   / ) D (/    \\
(__) \\_/\\_/(__\\_)\\_)(_/\\_/\\_/ \\___)(__)\\__/ \\____/\\_/\\_/   \\__/ (____)(__\\_)(____/\\_/\\_/
[/bold dark_sea_green3]""")


# ·························································
# · INPUT HELPERS                                         ·
# ·························································

@dataclass(frozen=True)
class Field:
    """Describes one value the user can type."""

    key: str
    label: str
    cast: Callable[[str], Any] = str
    optional: bool = False
    secret: bool = False


def ask(console: Console, field: Field) -> Any:
    """Ask for a value until it is valid. Optional fields may return None."""
    suffix = " (optional)" if field.optional else ""
    while True:
        raw = console.input(
            highlight(f"{field.label}{suffix}:") + " ", password=field.secret
        ).strip()
        if not raw:
            if field.optional:
                return None
            show_error(console, "This field is required.")
            continue
        try:
            return field.cast(raw)
        except ValueError:
            show_error(console, "The value is invalid.")


def ask_fields(console: Console, fields: tuple) -> dict:
    """Ask for several fields; empty optional ones are left out."""
    answers = {field.key: ask(console, field) for field in fields}
    return {key: value for key, value in answers.items() if value is not None}


def ask_id(console: Console, label: str) -> int:
    return ask(console, Field("id", label, int))


def select_option(console: Console, max_option: int, min_option: int = 0) -> int:
    while True:
        try:
            option = int(Prompt.ask(accent("Select an option")))
        except ValueError:
            show_error(console, "Error: The value is invalid")
            continue
        if min_option <= option <= max_option:
            return option
        show_error(
            console,
            f"Error: The option must be between {min_option} and {max_option}",
        )


def show_menu(console: Console, title: str, items: dict) -> int:
    table = Table(title=title)
    table.add_column(accent("Option"), justify="center", style="bold dark_sea_green3")
    table.add_column(accent("Title"), justify="left", width=75)
    for number, (name, description) in enumerate(items.items(), start=1):
        table.add_row(str(number), f"{highlight(name + ':')} {description}.")
    table.add_row("0", highlight("Exit."))
    console.print(table)
    return select_option(console, len(items))


def choose_field(console: Console, fields: tuple) -> Field:
    for number, field in enumerate(fields, start=1):
        console.print(f"{highlight(str(number) + '.')} {field.label}")
    return fields[select_option(console, len(fields), min_option=1) - 1]


# ·························································
# · SERVER CALLS                                          ·
# ·························································

def call(
    console: Console,
    client: SocketClient,
    operation: Operation,
    entity: Entity,
    data: Optional[dict] = None,
) -> Optional[Response]:
    """Send a request. Print the server error and return None if it fails."""
    response = client.request(operation, entity, data)
    if not response.is_ok:
        show_error(console, f"Error: {response.error['message']}")
        return None
    return response


# ·························································
# · TABLES (built from DTOs received from the server)     ·
# ·························································

def detail_table(title: str, rows: list) -> Table:
    table = Table(title=escape(title), show_header=False)
    table.add_column("field", style="bold medium_orchid")
    table.add_column("value")
    for label, value in rows:
        table.add_row(label, display(value))
    return table


def recipes_table(title: str, items: list) -> Table:
    table = Table(title=escape(title))
    table.add_column(accent("ID"), justify="right")
    table.add_column(accent("Name"))
    table.add_column(accent("Duration"))
    for recipe in (RecipeSummaryDTO.from_dict(item) for item in items):
        duration = "-" if recipe.duration is None else f"{recipe.duration} min"
        table.add_row(
            highlight(str(recipe.id)),
            escape(recipe.name),
            f"[dark_sea_green3]{duration}[/dark_sea_green3]",
        )
    return table


def recipe_detail_table(item: dict) -> Table:
    recipe = RecipeDTO.from_dict(item)
    ingredients = ", ".join(
        f"{entry.ingredient.common_name} ({entry.quantity or '-'})"
        for entry in recipe.ingredients
    )
    categories = ", ".join(category.name for category in recipe.categories)
    return detail_table(
        recipe.name,
        [
            ("Name:", recipe.name),
            ("Subname:", recipe.sub_name),
            ("Duration:", recipe.duration),
            ("Description:", recipe.description),
            ("Step by step:", recipe.step_by_step),
            ("Dosage:", recipe.dosage),
            ("Categories:", categories),
            ("Ingredients:", ingredients),
            ("Created At:", recipe.created_at),
        ],
    )


def ingredients_table(title: str, items: list) -> Table:
    table = Table(title=escape(title))
    table.add_column(accent("ID"), justify="right")
    table.add_column(accent("Common Name"))
    table.add_column(accent("Scientific Name"))
    table.add_column(accent("Type"))
    table.add_column(accent("Family"))
    for plant in (IngredientDTO.from_dict(item) for item in items):
        table.add_row(
            highlight(str(plant.id)),
            escape(plant.common_name),
            f"[italic]{display(plant.scientific_name)}[/italic]",
            escape(plant.type),
            display(plant.family),
        )
    return table


def ingredient_detail_table(item: dict) -> Table:
    plant = IngredientDTO.from_dict(item)
    return detail_table(
        plant.common_name,
        [
            ("Common name:", plant.common_name),
            ("Scientific name:", plant.scientific_name),
            ("Family:", plant.family),
            ("Type:", plant.type),
            ("Description:", plant.description),
            ("Country origin:", plant.country_origin),
            ("Properties:", ", ".join(p.name for p in plant.properties)),
        ],
    )


# ·························································
# · GENERIC ACTIONS (shared by every entity)              ·
# ·························································

RECIPE_FIELDS = (
    Field("name", "Name"),
    Field("sub_name", "Subname", optional=True),
    Field("duration", "Duration (minutes)", int, optional=True),
    Field("description", "Description", optional=True),
    Field("step_by_step", "Step by step"),
    Field("dosage", "Dosage", optional=True),
)
INGREDIENT_FIELDS = (
    Field("common_name", "Common name"),
    Field("scientific_name", "Scientific name", optional=True),
    Field("family", "Family", optional=True),
    Field("type", "Type (e.g. herb, tree, shrub)"),
    Field("description", "Description", optional=True),
    Field("country_origin", "Country of origin", optional=True),
)
USER_FIELDS = (
    Field("user_name", "Username"),
    Field("alias", "Alias", optional=True),
    Field("email", "Email"),
    Field("phone", "Phone", optional=True),
    Field("password", "Password", secret=True),
)
PROFILE_FIELDS = (
    Field("bio", "Bio", optional=True),
    Field("img", "Image URL", optional=True),
    Field("country", "Country", optional=True),
)


def list_entities(console, client, entity, render, title):
    response = call(console, client, Operation.LIST, entity)
    if response is not None:
        console.print(render(title, response.data))


def show_entity(console, client, entity, render):
    entity_id = ask_id(console, f"Id of the {entity.value} to show")
    response = call(console, client, Operation.READ, entity, {"id": entity_id})
    if response is not None:
        console.print(render(response.data))


def add_entity(console, client, entity, fields):
    console.print(accent(f"Add a new {entity.value}"))
    data = ask_fields(console, fields)
    response = call(console, client, Operation.CREATE, entity, data)
    if response is not None:
        show_success(
            console,
            f"{entity.value.capitalize()} created with id {response.data['id']}.",
        )


def update_entity(console, client, entity, fields, nested_key=None):
    """Change one field. `nested_key` is used for sub-objects (profile)."""
    entity_id = ask_id(console, f"Id of the {entity.value} to update")
    field = choose_field(console, fields)
    value = ask(console, Field(field.key, f"New value for {field.label}", field.cast))
    changes = {nested_key: {field.key: value}} if nested_key else {field.key: value}
    response = call(
        console, client, Operation.UPDATE, entity, {"id": entity_id, **changes}
    )
    if response is not None:
        show_success(console, f"{entity.value.capitalize()} updated.")


def delete_entity(console, client, entity):
    entity_id = ask_id(console, f"Id of the {entity.value} to delete")
    response = call(console, client, Operation.DELETE, entity, {"id": entity_id})
    if response is not None:
        show_success(console, f"{entity.value.capitalize()} deleted.")


# ·························································
# · RECIPES                                               ·
# ·························································

def filter_recipes(console, client):
    option = show_menu(
        console,
        "Filter recipes",
        {"By name": "Search by recipe name", "By category": "Search by category"},
    )
    if option == 0:
        return
    filter_key = ("name", "category")[option - 1]
    value = ask(console, Field(filter_key, f"Recipe {filter_key}"))
    response = call(console, client, Operation.LIST, Entity.RECIPE, {filter_key: value})
    if response is None:
        return
    if not response.data:
        show_error(console, "No recipes found.")
    for recipe in response.data:
        console.print(recipe_detail_table(recipe))


def add_recipe_ingredient(console, client):
    data = {
        "recipe_id": ask_id(console, "Recipe id"),
        "ingredient_id": ask(console, Field("ingredient_id", "Ingredient id", int)),
        "quantity": ask(console, Field("quantity", "Quantity (e.g. 5 g)")),
    }
    response = call(console, client, Operation.CREATE, Entity.RECIPE_INGREDIENT, data)
    if response is not None:
        show_success(console, "Ingredient added to the recipe.")


# ·························································
# · WISH LISTS (recipes and plants share the same flow)   ·
# ·························································

@dataclass(frozen=True)
class WishList:
    entity: Entity
    item_key: str
    item_name: str
    render: Callable[[str, list], Table]


RECIPE_WISH_LIST = WishList(
    Entity.WISH_LIST_RECIPE, "recipe_id", "recipe", recipes_table
)
INGREDIENT_WISH_LIST = WishList(
    Entity.WISH_LIST_INGREDIENT, "ingredient_id", "plant", ingredients_table
)


def show_wish_list(console, client, wish_list):
    user_id = ask(console, Field("user_id", "Your user id", int))
    response = call(
        console, client, Operation.LIST, wish_list.entity, {"user_id": user_id}
    )
    if response is not None:
        title = f"Wish list of {wish_list.item_name}s (user {user_id})"
        console.print(wish_list.render(title, response.data))


def change_wish_list(console, client, wish_list, operation, verb):
    data = {
        "user_id": ask(console, Field("user_id", "Your user id", int)),
        wish_list.item_key: ask(
            console, Field(wish_list.item_key, f"Id of the {wish_list.item_name}", int)
        ),
    }
    response = call(console, client, operation, wish_list.entity, data)
    if response is not None:
        show_success(console, f"{wish_list.item_name.capitalize()} {verb}.")


# ·························································
# · USERS                                                 ·
# ·························································

def register_user(console, client):
    console.print(accent("Register a new User"))
    data = ask_fields(console, USER_FIELDS)
    console.print("\n" + accent("Profile (optional, press Enter to skip)"))
    profile = ask_fields(console, PROFILE_FIELDS)
    if profile:
        data["profile"] = profile
    response = call(console, client, Operation.CREATE, Entity.USER, data)
    if response is not None:
        show_success(console, f"User created with id {response.data['id']}.")


# ·························································
# · MENUS                                                 ·
# ·························································

@dataclass(frozen=True)
class Submenu:
    title: str
    items: dict
    handlers: dict  # option number -> function(console, client)


MAIN_MENU = {
    "Recipes": "See all the medicinal recipes",
    "Medicinal Plants": "Discover new medicinal plants",
    "Recipes wish list": "See all the recipes on your wish list",
    "Plants wish list": "See all the plants on your wish list",
    "Users": "Manage users and profiles",
}

SUBMENUS = {
    1: Submenu(
        "Recipes CRUD",
        {
            "Show All": "See all the medicinal recipes",
            "Show": "See a specific medicinal recipe",
            "Filter": "Search recipes by name or category",
            "Add": "Add a new recipe",
            "Update": "Update a recipe",
            "Add ingredient": "Add or update an ingredient of the recipe",
            "Delete": "Delete a recipe",
        },
        {
            1: partial(list_entities, entity=Entity.RECIPE,
                       render=recipes_table, title="Recipes"),
            2: partial(show_entity, entity=Entity.RECIPE,
                       render=recipe_detail_table),
            3: filter_recipes,
            4: partial(add_entity, entity=Entity.RECIPE, fields=RECIPE_FIELDS),
            5: partial(update_entity, entity=Entity.RECIPE, fields=RECIPE_FIELDS),
            6: add_recipe_ingredient,
            7: partial(delete_entity, entity=Entity.RECIPE),
        },
    ),
    2: Submenu(
        "Medicinal plants CRUD",
        {
            "Show All": "See all the medicinal plants",
            "Show": "See a specific medicinal plant",
            "Add": "Add a new plant",
            "Update": "Update a plant",
            "Delete": "Delete a plant",
        },
        {
            1: partial(list_entities, entity=Entity.INGREDIENT,
                       render=ingredients_table, title="Medicinal Plants"),
            2: partial(show_entity, entity=Entity.INGREDIENT,
                       render=ingredient_detail_table),
            3: partial(add_entity, entity=Entity.INGREDIENT,
                       fields=INGREDIENT_FIELDS),
            4: partial(update_entity, entity=Entity.INGREDIENT,
                       fields=INGREDIENT_FIELDS),
            5: partial(delete_entity, entity=Entity.INGREDIENT),
        },
    ),
    3: Submenu(
        "Recipes wish list",
        {
            "Show": "See all the recipes in the wish list",
            "Add": "Add a recipe",
            "Remove": "Remove a recipe",
        },
        {
            1: partial(show_wish_list, wish_list=RECIPE_WISH_LIST),
            2: partial(change_wish_list, wish_list=RECIPE_WISH_LIST,
                       operation=Operation.CREATE, verb="added to the wish list"),
            3: partial(change_wish_list, wish_list=RECIPE_WISH_LIST,
                       operation=Operation.DELETE, verb="removed from the wish list"),
        },
    ),
    4: Submenu(
        "Plants wish list",
        {
            "Show": "See all the plants in the wish list",
            "Add": "Add a plant",
            "Remove": "Remove a plant",
        },
        {
            1: partial(show_wish_list, wish_list=INGREDIENT_WISH_LIST),
            2: partial(change_wish_list, wish_list=INGREDIENT_WISH_LIST,
                       operation=Operation.CREATE, verb="added to the wish list"),
            3: partial(change_wish_list, wish_list=INGREDIENT_WISH_LIST,
                       operation=Operation.DELETE, verb="removed from the wish list"),
        },
    ),
    5: Submenu(
        "Users",
        {
            "Add": "Register a new user",
            "Delete": "Delete a user",
            "Edit profile": "Edit bio, image or country of a user",
        },
        {
            1: register_user,
            2: partial(delete_entity, entity=Entity.USER),
            3: partial(update_entity, entity=Entity.USER,
                       fields=PROFILE_FIELDS, nested_key="profile"),
        },
    ),
}


def run_main_menu(console: Console, client: SocketClient) -> None:
    while True:
        option = show_menu(console, "Main Menu", MAIN_MENU)
        if option == 0:
            show_success(console, ">> Exit.")
            return
        submenu = SUBMENUS[option]
        handler = submenu.handlers.get(show_menu(console, submenu.title, submenu.items))
        if handler is not None:
            handler(console, client)


def main() -> None:
    console = Console()
    show_title(console)
    try:
        with SocketClient() as client:
            run_main_menu(console, client)
    except ConnectionRefusedError:
        show_error(console, "Cannot connect to the server. Is it running?")
    except ConnectionError as exc:
        show_error(console, f"Connection lost: {exc}")


if __name__ == "__main__":
    main()