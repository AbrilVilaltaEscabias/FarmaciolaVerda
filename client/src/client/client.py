
"""
Client de terminal de Farmaciola Verda.

Només parla amb el servidor a través del protocol de sockets
(common/protocol.py) i treballa amb diccionaris simples. Mai toca la base
de dades, els models del domini ni SQLAlchemy.
"""
import socket
import ssl
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

import base64

from rich.console import Console
from rich.markup import escape
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet

from common import protocol

ACCENT = "bold medium_orchid"
HIGHLIGHT = "bold dark_sea_green3"
ERROR = "bold red"

nom = sys.argv[1] if len(sys.argv) > 1 else "client1"

context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
try:
    context.load_cert_chain(certfile=f"certs/{nom}/{nom}.crt",
                            keyfile=f"certs/{nom}/{nom}.key")
except FileNotFoundError:
    print(f"No existeix el certificat per a {nom}")
    sys.exit(1)
context.load_verify_locations(cafile="certs/ca.crt")

# ·························································
# · CONNEXIÓ AMB EL SERVIDOR                             ·
# ·························································


class ServerError(Exception):
    """El servidor ha respost amb un ERROR."""


class ServerConnection:
    """Envia peticions al servidor i retorna les dades de la resposta."""

    def __init__(
        self,
        host: str = protocol.HOST,
        port: int = protocol.PORT,
        context: ssl.SSLContext = context,
    ) -> None:
        sock = socket.create_connection((host, port))  # socket normal, SENSE xifrar
        self._socket = context.wrap_socket(
            sock,
            server_hostname="localhost"
        )
        self._reader = self._socket.makefile("rb")

        # Rebre la clau AES xifrada del servidor
        encrypted_key = self._reader.readline()

        if not encrypted_key:
            raise ConnectionError(
                "El servidor ha rebutjat la connexió o l'ha tancat."
            )

        # Descodificar el missatge Base64
        encrypted_key = base64.b64decode(encrypted_key.strip())

        # Carregar la clau privada del client
        with open(f"certs/{nom}/{nom}.key", "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )

        # Desxifrar la clau AES
        self.session_key = private_key.decrypt(
            encrypted_key.strip(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # Crear el xifrador AES
        self.cipher = Fernet(self.session_key)

    def __enter__(self) -> "ServerConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        self._reader.close()
        self._socket.close()

    def request(self, command: str, data: dict | None = None) -> dict:
        # Construir la petició en format protocol
        request = protocol.build_request(command, data)

        # Xifrar la petició amb la clau AES de la sessió
        encrypted_request = self.cipher.encrypt(request)

        # Enviar la petició xifrada
        self._socket.sendall(encrypted_request + b"\n")

        # Rebre la resposta xifrada
        encrypted_response = self._reader.readline()

        if not encrypted_response:
            raise ConnectionError("The server closed the connection")

        # Desxifrar la resposta
        response_line = self.cipher.decrypt(encrypted_response.strip())

        # Interpretar la resposta del protocol
        response = protocol.parse_message(response_line)

        if response[protocol.FIELD_STATUS] != protocol.OK:
            error = response.get(protocol.FIELD_ERROR)
            message = response.get(protocol.FIELD_MESSAGE)
            raise ServerError(message or error)

        return response[protocol.FIELD_DATA]

    def list_items(self, resource: str, filters: dict | None = None) -> list[dict]:
        data = {protocol.FIELD_RESOURCE: resource}
        if filters:
            data[protocol.FIELD_FILTER] = filters
        return self.request(protocol.LIST, data)["items"]

    def show(self, resource: str, item_id: int) -> dict:
        return self.request(protocol.SHOW, {
            protocol.FIELD_RESOURCE: resource,
            protocol.FIELD_ID: item_id,
        })

    def create(self, resource: str, values: dict) -> dict:
        return self.request(protocol.CREATE, {
            protocol.FIELD_RESOURCE: resource,
            protocol.FIELD_VALUES: values,
        })

    def update(self, resource: str, item_id: int, values: dict) -> dict:
        return self.request(protocol.UPDATE, {
            protocol.FIELD_RESOURCE: resource,
            protocol.FIELD_ID: item_id,
            protocol.FIELD_VALUES: values,
        })

    def delete(self, resource: str, item_id: int) -> None:
        self.request(protocol.DELETE, {
            protocol.FIELD_RESOURCE: resource,
            protocol.FIELD_ID: item_id,
        })


# ·························································
# · COM ÉS CADA RECURS (formularis, taules, detall)      ·
# ·························································

@dataclass(frozen=True)
class Field:
    """Un valor que l'usuari pot escriure en crear o editar un element."""
    name: str
    label: str
    required: bool = False
    cast: type = str
    secret: bool = False


@dataclass(frozen=True)
class Resource:
    name: str                 # nom del recurs al protocol
    label: str                # nom que es mostra a l'usuari
    title_field: str          # camp que fa de títol de l'element
    form_fields: tuple = ()
    list_columns: tuple = ()  # (clau, capçalera) de la taula "show all"
    detail_rows: tuple = ()   # (clau, etiqueta) de la taula "show one"


RECIPE = Resource(
    name="recipe",
    label="recipe",
    title_field="name",
    form_fields=(
        Field("name", "Name", required=True),
        Field("sub_name", "Subname"),
        Field("duration", "Duration (minutes)", cast=int),
        Field("description", "Description"),
        Field("step_by_step", "Step by step", required=True),
        Field("dosage", "Dosage"),
    ),
    list_columns=(
        ("id", "ID"),
        ("name", "Name"),
        ("duration", "Duration (min)"),
    ),
    detail_rows=(
        ("name", "Name"),
        ("sub_name", "Subname"),
        ("duration", "Duration"),
        ("description", "Description"),
        ("step_by_step", "Step by step"),
        ("dosage", "Dosage"),
        ("created_at", "Created at"),
    ),
)

PLANT = Resource(
    name="ingredient",
    label="plant",
    title_field="common_name",
    form_fields=(
        Field("common_name", "Common name", required=True),
        Field("scientific_name", "Scientific name"),
        Field("family", "Family"),
        Field("type", "Type (e.g. herb, tree, shrub)", required=True),
        Field("description", "Description"),
        Field("country_origin", "Country of origin"),
    ),
    list_columns=(
        ("id", "ID"),
        ("common_name", "Common name"),
        ("scientific_name", "Scientific name"),
        ("type", "Type"),
        ("family", "Family"),
    ),
    detail_rows=(
        ("common_name", "Common name"),
        ("scientific_name", "Scientific name"),
        ("family", "Family"),
        ("type", "Type"),
        ("description", "Description"),
        ("country_origin", "Country of origin"),
    ),
)

USER = Resource(
    name="user",
    label="user",
    title_field="user_name",
    form_fields=(
        Field("user_name", "Username", required=True),
        Field("alias", "Alias"),
        Field("email", "Email", required=True),
        Field("phone", "Phone"),
        Field("password", "Password", required=True, secret=True),
    ),
    list_columns=(
        ("id", "ID"),
        ("user_name", "Username"),
        ("alias", "Alias"),
        ("email", "Email"),
    ),
)


# ·························································
# · FUNCIONS D'ENTRADA I SORTIDA                         ·
# ·························································

def show_title(console: Console) -> None:
    print()
    console.print("""[bold medium_orchid] \\    / _  |  _  _  ._ _   _    _|_  _
  \\/\\/ (/_ | (_ (_) | | | (/_    |_ (_) [/bold medium_orchid][bold dark_sea_green3]
 ____  __   ____  _  _   __    ___  __  __   __     __     _  _  ____  ____  ____   __
(  __)/ _\\ (  _ \\( \\/ ) / _\\  / __)(  )/  \\ (  )   / _\\   / )( \\(  __)(  _ \\(    \\ / _\\
 ) _)/    \\ )   // \\/ \\/    \\( (__  )((  O )/ (_/\\/    \\  \\ \\/ / ) _)  )   / ) D (/    \\
(__) \\_/\\_/(__\\_)\\_)(_/\\_/\\_/ \\___)(__)\\__/ \\____/\\_/\\_/   \\__/ (____)(__\\_)(____/\\_/\\_/
[/bold dark_sea_green3]""")  # noqa: E501


def format_value(value: object) -> str:
    """Text que es mostra per a un valor que ve del servidor."""
    return "-" if value is None else escape(str(value))


def select_option(console: Console, max_option: int, min_option: int = 0) -> int:
    while True:
        option = IntPrompt.ask(f"[{ACCENT}]Select an option[/]")
        if min_option <= option <= max_option:
            return option
        console.print(
            f"[{ERROR}]Error: The option must be between "
            f"{min_option} and {max_option}[/]"
        )


def ask_id(question: str) -> int:
    return IntPrompt.ask(f"[{HIGHLIGHT}]{question}[/]")


def ask_field_value(console: Console, field: Field) -> Any:
    """Demana un camp fins que el valor és vàlid. None si es deixa buit."""
    label = field.label if field.required else f"{field.label} (optional)"
    while True:
        raw = Prompt.ask(f"[{HIGHLIGHT}]{label}[/]", password=field.secret)
        if not field.secret:
            raw = raw.strip()
        if not raw:
            if not field.required:
                return None
            console.print(f"[{ERROR}]This field is required.[/]")
            continue
        try:
            return field.cast(raw)
        except ValueError:
            console.print(f"[{ERROR}]The value is invalid.[/]")


def ask_values(console: Console, fields: tuple[Field, ...]) -> dict[str, Any]:
    values = {field.name: ask_field_value(console, field) for field in fields}
    return {name: value for name, value in values.items() if value is not None}


def print_table(
    console: Console, title: str, columns: tuple, items: list[dict]
) -> None:
    table = Table(title=title, header_style=ACCENT)
    for index, (_, header) in enumerate(columns):
        table.add_column(
            header,
            justify="right" if index == 0 else "left",
            style=HIGHLIGHT if index == 0 else None,
        )
    for item in items:
        table.add_row(*(format_value(item.get(key)) for key, _ in columns))
    console.print(table)


def print_detail(console: Console, title: object, item: dict, rows: tuple) -> None:
    table = Table(title=escape(str(title)), show_header=False)
    table.add_column("field", style=ACCENT)
    table.add_column("value")
    for key, label in rows:
        table.add_row(f"{label}:", format_value(item.get(key)))
    console.print(table)


# ·························································
# · ACCIONS GENÈRIQUES (iguals per a tots els recursos)  ·
# ·························································

def show_all(
    console: Console, api: ServerConnection, resource: Resource
) -> None:
    items = api.list_items(resource.name)
    print_table(console, resource.label.capitalize() + "s",
                resource.list_columns, items)


def show_one(
    console: Console, api: ServerConnection, resource: Resource
) -> None:
    item_id = ask_id(f"Enter the id of the {resource.label} to show: ")
    item = api.show(resource.name, item_id)
    print_detail(console, item[resource.title_field], item,
                 resource.detail_rows)


def create_one(
    console: Console, api: ServerConnection, resource: Resource
) -> None:
    console.print(f"[{ACCENT}]Add a new {resource.label}[/]")
    values = ask_values(console, resource.form_fields)
    item = api.create(resource.name, values)
    console.print(
        f"[{HIGHLIGHT}]{resource.label.capitalize()} "
        f"'{escape(str(item[resource.title_field]))}' "
        f"created with id {item['id']}.[/]"
    )


def update_one(
    console: Console, api: ServerConnection, resource: Resource
) -> None:
    item_id = ask_id(f"Enter the id of the {resource.label} to update: ")
    fields = resource.form_fields

    console.print("What do you want to change? (0 to cancel)")
    for number, field in enumerate(fields, start=1):
        console.print(f"{number}. {field.label}")

    choice = select_option(console, len(fields))
    if choice == 0:
        return
    field = fields[choice - 1]
    new_value = ask_field_value(console, field)
    api.update(resource.name, item_id, {field.name: new_value})
    console.print(f"[{HIGHLIGHT}]Field '{field.name}' updated.[/]")


def delete_one(
    console: Console, api: ServerConnection, resource: Resource
) -> None:
    item_id = ask_id(f"Enter the id of the {resource.label} to delete: ")
    api.delete(resource.name, item_id)
    console.print(f"[{HIGHLIGHT}]{resource.label.capitalize()} deleted.[/]")


def filter_recipes(console: Console, api: ServerConnection) -> None:
    console.print(f"[{ACCENT}]Filter recipes[/]")
    console.print(f"[{HIGHLIGHT}]1.[/] By name")
    console.print(f"[{HIGHLIGHT}]2.[/] By category")
    choice = select_option(console, 2)
    if choice == 0:
        return

    key, question = (
        ("name", "Recipe name"),
        ("category", "Category name"),
    )[choice - 1]
    value = ask_field_value(console, Field(key, question, required=True))

    recipes = api.list_items(RECIPE.name, {key: value})
    if not recipes:
        console.print(f"[{ERROR}]No recipes found.[/]")
    for recipe in recipes:
        print_detail(console, recipe["name"], recipe, RECIPE.detail_rows)


# ·························································
# · MENÚS                                                ·
# ·························································

def show_menu(console: Console, title: str, options: dict[str, str]) -> int:
    table = Table(title=title, header_style=ACCENT)
    table.add_column("Option", justify="center", style=HIGHLIGHT)
    table.add_column("Title", justify="left", width=75)

    for number, (name, description) in enumerate(options.items(), start=1):
        table.add_row(str(number), f"[{HIGHLIGHT}]{name}:[/] {description}.")
    table.add_row("0", f"[{HIGHLIGHT}]Exit.[/]")

    console.print(table)
    return select_option(console, len(options))


def run_menu(
    console: Console,
    api: ServerConnection,
    title: str,
    entries: list[tuple[str, str, Callable[..., None]]],
) -> bool:
    """Mostra un menú i executa l'acció triada.

    entries és una llista de (nom, descripció, acció). Retorna False quan
    l'usuari tria sortir, i True en qualsevol altre cas.
    """
    options = {name: description for name, description, _ in entries}
    choice = show_menu(console, title, options)
    if choice == 0:
        return False

    action = entries[choice - 1][2]
    try:
        action(console, api)
    except ServerError as error:
        console.print(f"[{ERROR}]Error: {escape(str(error))}[/]")
    return True


def recipes_menu(console: Console, api: ServerConnection) -> None:
    run_menu(console, api, "Recipes CRUD", [
        ("Show All", "See all the medicinal recipes",
         partial(show_all, resource=RECIPE)),
        ("Show", "See a specific medicinal recipe",
         partial(show_one, resource=RECIPE)),
        ("Filter", "Search recipes by name or category", filter_recipes),
        ("Add", "Add a new recipe", partial(create_one, resource=RECIPE)),
        ("Update", "Update a recipe", partial(update_one, resource=RECIPE)),
        ("Delete", "Delete a recipe", partial(delete_one, resource=RECIPE)),
    ])


def plants_menu(console: Console, api: ServerConnection) -> None:
    run_menu(console, api, "Medicinal plants CRUD", [
        ("Show All", "See all the medicinal plants",
         partial(show_all, resource=PLANT)),
        ("Show", "See a specific medicinal plant",
         partial(show_one, resource=PLANT)),
        ("Add", "Add a new plant", partial(create_one, resource=PLANT)),
        ("Update", "Update a plant", partial(update_one, resource=PLANT)),
        ("Delete", "Delete a plant", partial(delete_one, resource=PLANT)),
    ])


def users_menu(console: Console, api: ServerConnection) -> None:
    run_menu(console, api, "Users", [
        ("Add", "Register a new user", partial(create_one, resource=USER)),
        ("Delete", "Delete a user", partial(delete_one, resource=USER)),
        ("Show All", "See all the users", partial(show_all, resource=USER)),
    ])


MAIN_MENU = [
    ("Recipes", "See all the medicinal recipes", recipes_menu),
    ("Medicinal Plants", "Discover new medicinal plants", plants_menu),
    ("Users", "Manage users", users_menu),
]


def main() -> None:
    console = Console()
    show_title(console)
    try:
        with ServerConnection() as api:
            while run_menu(console, api, "Main Menu", MAIN_MENU):
                pass
        console.print(f"[{HIGHLIGHT}]>> Exit.[/]")
    except ConnectionRefusedError:
        console.print(f"[{ERROR}]Could not connect to the server. "
                      f"Is it running?[/]")
    except OSError as error:
        console.print(f"[{ERROR}]Connection with the server lost: "
                      f"{escape(str(error))}[/]")
    except KeyboardInterrupt:
        console.print(f"\n[{HIGHLIGHT}]>> Exit.[/]")


if __name__ == "__main__":
    main()
