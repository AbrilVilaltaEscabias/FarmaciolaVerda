
"""
És el traductor entre el món dels sockets i el del domini. Rep un missatge ja llegit, identifica quina comanda és, valida els paràmetres, crea un UoW i crida el servei corresponent. Converteix el resultat (o l’error del domini) en una resposta segons el protocol, serialitzant les dades a JSON si cal.
"""

import json
 
from common import protocol
from server.db import Session
from server.domain.exceptions import AlreadyExists, NotFound
from server.service_layer import services, unit_of_work
 
 
def _new_uow():
    # Un UoW nou per cada petició: les sessions no es comparteixen entre fils.
   return unit_of_work.SqlAlchemyUnitOfWork()

# --- HANDLERS -----------------------------------------------------------------
""" Tots segueixen la mateixa idea: reben data (un diccionari), crida un servei
i retornen una resposta en bytes. """

def handle_list(data):
    items = services.list_resources(
        _new_uow(),
        data[protocol.FIELD_RESOURCE], # El tipus d'objecte (recipe, ingredient...)
        data.get(protocol.FIELD_FILTER), # (Opcional)
        data.get(protocol.FIELD_PAGE),  # (Opcional) 
        data.get(protocol.FIELD_PAGE_SIZE, 10)  # (Opcional)
    )
    return protocol.build_ok({"items": items}) # Retorna la llista d'items
 
 
def handle_show(data):
    item = services.show_resource(
        _new_uow(), 
        data[protocol.FIELD_RESOURCE], 
        data[protocol.FIELD_ID]
    )
    return protocol.build_ok(item) # Retorna l'item

def handle_create(data):
    item = services.create_resource(
        _new_uow(), 
        data[protocol.FIELD_RESOURCE], 
        data[protocol.FIELD_VALUES] # objecte json amb les dades
    )
    return protocol.build_ok(item) # Retorna l'item creat
 
 
def handle_update(data):
    item = services.update_resource(
        _new_uow(),
        data[protocol.FIELD_RESOURCE],
        data[protocol.FIELD_ID],
        data[protocol.FIELD_VALUES],
    )
    return protocol.build_ok(item)  # Retorna l'item actualitzat
 
 
def handle_delete(data):
    services.delete_resource(
        _new_uow(), data[protocol.FIELD_RESOURCE], data[protocol.FIELD_ID]
    )
    return protocol.build_ok()
 
 
# ---------- Taula: comanda -> handler ----------
 
COMMANDS = {
    protocol.LIST: handle_list,
    protocol.SHOW: handle_show,
    protocol.CREATE: handle_create,
    protocol.UPDATE: handle_update,
    protocol.DELETE: handle_delete,
}
 
 
# ---------- Punt d'entrada (el crida server.py) ----------
 
def handle(line):
    
    # 1. Interpretar el missatge
    try:
        request = protocol.parse_message(line)
        command = request[protocol.FIELD_COMMAND]
        if not isinstance(command, str):
            raise TypeError("command ha de ser un text")
        data = request.get(protocol.FIELD_DATA) or {}
        if not isinstance(data, dict):
            raise TypeError("data ha de ser un objecte")
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, AttributeError):
        return protocol.build_error(protocol.INVALID_DATA, "Missatge mal format")

    # 2. Buscar el handler de la comanda
    func = COMMANDS.get(command)
    if func is None:
        return protocol.build_error(protocol.UNKNOWN_COMMAND, f"Comanda desconeguda: {command}")
 
    # 3. Executar-lo i convertir errors en respostes del protocol
    try:
        return func(data)
    except KeyError as e:
        return protocol.build_error(protocol.INVALID_DATA, f"Falta el camp {e}")
    except ValueError as e:
        return protocol.build_error(protocol.INVALID_DATA, str(e))
    except AlreadyExists as e:
        return protocol.build_error(protocol.ALREADY_EXISTS, str(e))
    except NotFound as e:
        return protocol.build_error(protocol.NOT_FOUND, str(e))
    except Exception as e:
        print(f"[!] Error inesperat a {command}: {e!r}")
        return protocol.build_error(protocol.SERVER_ERROR, "Error intern del servidor")
 