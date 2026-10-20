
"""
Els casos d’ús de l’aplicació (registrar un usuari, fer una comanda...). Cada funció rep un UoW i dades simples, fa la feina dins un with uow: i retorna el resultat. Aquí viu la lògica que orquestra el domini.
"""

import hashlib
import os
from datetime import datetime
 
from server.domain import Category, Ingredient, Recipe, User
from server.domain.exceptions import AlreadyExists, NotFound

 
#   repo     -> nom de l'atribut del repositori dins l'UoW
#   model    -> classe del model
#   fields   -> camps que s'envien al client (mai la password!)
#   required -> camps obligatoris en crear
#   editable -> camps que es poden modificar

RESOURCES = {
    "recipe": {
        "repo": "recipes",
        "model": Recipe,
        "fields": ["id", "name", "duration", "step_by_step", "sub_name",
                   "note", "dosage", "description", "created_at"],
        "required": ["name", "step_by_step"],
        "editable": ["name", "duration", "step_by_step", "sub_name",
                     "note", "dosage", "description"],
    },
    "ingredient": {
        "repo": "ingredients",
        "model": Ingredient,
        "fields": ["id", "scientific_name", "common_name", "family",
                   "description", "country_origin", "type", "image_url"],
        "required": ["common_name", "type"],
        "editable": ["scientific_name", "common_name", "family", "description",
                     "country_origin", "type", "image_url"],
    },
    "category": {
        "repo": "categories",
        "model": Category,
        "fields": ["id", "name", "description"],
        "required": ["name"],
        "editable": ["name", "description"],
    },
    "user": {
        "repo": "users",
        "model": User,
        "fields": ["id", "user_name", "alias", "email", "phone"],
        "required": ["user_name", "email", "password"],
        "editable": ["user_name", "alias", "email", "phone"],
    },
}
 
 
# ---------- Auxiliars ----------
 
def _config(resource):
    if resource not in RESOURCES:
        raise ValueError(f"Recurs desconegut: {resource}")
    return RESOURCES[resource]
 
 
def _to_dict(obj, fields):
    result = {}
    for field in fields:
        value = getattr(obj, field)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[field] = value
    return result
 
 
def _get_or_fail(repo, resource, id):
    obj = repo.get(id)
    if obj is None:
        raise NotFound(f"{resource} amb id {id} no existeix")
    return obj
 
 
def _hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + "$" + digest.hex()
 
 
# ---------- Casos d'ús ----------
 
def list_resources(uow, resource, filters=None, page=None, page_size=10):
    cfg = _config(resource)
    filters = filters or {}
    with uow:
        repo = getattr(uow, cfg["repo"])
        if resource == "recipe" and "category" in filters:
            objs = repo.get_by_category(filters["category"])
        elif resource == "recipe" and "name" in filters:
            objs = repo.get_by_name(filters["name"])
        elif resource == "recipe" and page:
            objs = repo.get_paginated(page, page_size)
        else:
            objs = repo.get_all()
        return [_to_dict(o, cfg["fields"]) for o in objs]
 
 
def show_resource(uow, resource, id):
    cfg = _config(resource)
    with uow:
        obj = _get_or_fail(getattr(uow, cfg["repo"]), resource, id)
        return _to_dict(obj, cfg["fields"])
 
def create_resource(uow, resource, values):
    cfg = _config(resource)
    if not isinstance(values, dict):
        raise ValueError("values ha de ser un objecte")
    missing = [f for f in cfg["required"] if values.get(f) in (None, "")]
    if missing:
        raise ValueError(f"Falten camps obligatoris: {', '.join(missing)}")

    allowed = set(cfg["editable"]) | set(cfg["required"])
    fields = {k: v for k, v in values.items() if k in allowed}
 
    with uow:
        repo = getattr(uow, cfg["repo"])
        if resource == "user":
            if any(u.email == fields["email"] for u in repo.get_all()):
                raise AlreadyExists("Aquest email ja existeix")
            fields["password"] = _hash_password(fields["password"])
        if "created_at" in cfg["fields"]:
            fields["created_at"] = datetime.now()
 
        obj = cfg["model"](**fields)
        repo.add(obj)
        uow.session.flush()                 # perquè obj.id ja tingui valor
        return _to_dict(obj, cfg["fields"])
 
 
def update_resource(uow, resource, id, values):
    cfg = _config(resource)
    if not isinstance(values, dict):
        raise ValueError("values ha de ser un objecte")
    with uow:
        obj = _get_or_fail(getattr(uow, cfg["repo"]), resource, id)
        for field, value in values.items():
            if field in cfg["editable"]:
                setattr(obj, field, value)  # el commit del UoW guarda els canvis
        return _to_dict(obj, cfg["fields"])
 
 
def delete_resource(uow, resource, id):
    cfg = _config(resource)
    with uow:
        repo = getattr(uow, cfg["repo"])
        _get_or_fail(repo, resource, id)
        repo.delete(id)