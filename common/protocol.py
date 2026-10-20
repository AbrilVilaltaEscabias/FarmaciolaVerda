
"""
Defineix el “contracte” entre client i servidor: host i port, la llista de comandes (LOGIN, MSG, QUIT...), el separador de missatges (per exemple \n) i els codis de resposta (OK, ERROR...). També pot tenir dues funcions petites per construir i interpretar missatges. No coneix ni la BD ni els models.
"""

import json

# --- CONNEXIÓ --------------------------------------------------------------

HOST = "127.0.0.1"
PORT = 5000
SEPARATOR = "\n" # Cada missatge acaba amb /n (ENTER)

# --- COMANDES (client -> servidor) -----------------------------------------

CREATE_USER = "CREATE_USER"
LIST = "LIST"
SHOW = "SHOW"
CREATE = "CREATE"
DELETE = "DELETE"
UPDATE = "UPDATE"

# --- CAMPS DE "data" (dins de la petició) ----------------------------------

FIELD_RESOURCE = "resource"
FIELD_ID = "id"
FIELD_VALUES = "values"
FIELD_FILTER = "filter"
FIELD_PAGE = "page"
FIELD_PAGE_SIZE = "page_size"

# --- ESTAT DE RESPOSTA (servidor -> client) --------------------------------

OK = "OK"
ERROR = "ERROR"

# --- TIPUS D'ERROR ---------------------------------------------------------

ALREADY_EXISTS = "ALREADY_EXISTS"
INVALID_DATA = "INVALID_DATA"
UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
NOT_FOUND = "NOT_FOUND"
SERVER_ERROR = "SERVER_ERROR"

# --- FUNCIONS --------------------------------------------------------------

SEPARATOR = "\n"
FIELD_COMMAND = "command"
FIELD_DATA = "data"
FIELD_STATUS = "status"
FIELD_ERROR = "error"
FIELD_MESSAGE = "message"

def build_request(command, data=None):
    """Client: construeix la petició a enviar."""
    message = {FIELD_COMMAND: command, FIELD_DATA: data or {}}
    return (json.dumps(message) + SEPARATOR).encode()

def build_ok(data=None):
    """Servidor: resposta d'èxit."""
    message = {FIELD_STATUS: OK, FIELD_DATA: data or {}}
    return (json.dumps(message) + SEPARATOR).encode()


def build_error(error, message=""):
    """Servidor: resposta d'error."""
    msg = {FIELD_STATUS: ERROR, FIELD_ERROR: error, FIELD_MESSAGE: message}
    return (json.dumps(msg) + SEPARATOR).encode()


def parse_message(line):
    """Tots dos: converteix una línia rebuda en diccionari."""
    return json.loads(line.decode().strip())