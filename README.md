# Farmaciola Verda

Aplicació client-servidor amb sockets TCP. El **servidor** és l'únic que parla amb la base de dades (SQLAlchemy); el **client** és un programa de terminal que només envia peticions i mostra les respostes.

Aquest document descriu el **protocol de comunicació** entre els dos.

## Índex

1. [Visió general](#1-visió-general)
2. [Format de la petició](#2-format-de-la-petició)
3. [Format de la resposta](#3-format-de-la-resposta)
4. [Operacions suportades](#4-operacions-suportades)
5. [Recursos](#5-recursos)
6. [Gestió d'errors](#6-gestió-derrors)
7. [On és implementat](#7-on-és-implementat)
8. [Com executar-ho](#8-com-executar-ho)

---

## 1. Visió general

| Aspecte | Valor |
|---|---|
| Transport | TCP |
| Adreça per defecte | `127.0.0.1:5000` (definida a `common/protocol.py`) |
| Format dels missatges | JSON, codificat en UTF-8 |
| Delimitador | Cada missatge és **una sola línia** acabada en `\n` |
| Patró | Petició → resposta. Cada petició rep **exactament una** resposta |
| Clients | El servidor atén **un client a la vegada** |

Com que TCP és un flux de bytes i no de missatges, el `\n` final és el que indica on acaba cada missatge. Per això un missatge **no pot contenir salts de línia reals** (dins del JSON, un salt de línia dins d'un text s'escriu com `\n` escapat, i `json.dumps` ja ho fa sol).

> Als exemples d'aquest document els JSON es mostren en diverses línies per facilitar-ne la lectura, però pel socket sempre viatgen en una sola línia.

Les peticions són **genèriques**: hi ha cinc comandes (`LIST`, `SHOW`, `CREATE`, `UPDATE`, `DELETE`) i l'entitat sobre la qual s'apliquen s'indica dins de les dades amb el camp `resource`.

---

## 2. Format de la petició

El client envia un objecte JSON amb dos camps:

```json
{
  "command": "SHOW",
  "data": { "resource": "recipe", "id": 3 }
}
```

| Camp | Tipus | Obligatori | Descripció |
|---|---|---|---|
| `command` | text | Sí | Nom de l'operació: `LIST`, `SHOW`, `CREATE`, `UPDATE` o `DELETE` |
| `data` | objecte | No | Paràmetres de la comanda. Si no hi és, es considera `{}`. Si hi és, ha de ser un objecte |

Camps possibles dins de `data` (cada comanda utilitza els que li calen, vegeu l'apartat 4):

| Camp | Tipus | Descripció |
|---|---|---|
| `resource` | text | Tipus d'element: `recipe`, `ingredient`, `category` o `user` |
| `id` | enter | Identificador de l'element |
| `values` | objecte | Dades de l'element (en crear o modificar) |
| `filter` | objecte | Filtre per llistar |
| `page` | enter | Número de pàgina (comença a 1) |
| `page_size` | enter | Elements per pàgina (per defecte, 10) |

---

## 3. Format de la resposta

El servidor sempre respon amb un objecte JSON que té un camp `status`.

### Resposta d'èxit

```json
{
  "status": "OK",
  "data": { "id": 7, "name": "Camamilla" }
}
```

| Camp | Descripció |
|---|---|
| `status` | `"OK"` |
| `data` | Objecte amb el resultat. Pot ser `{}` si l'operació no retorna res |

### Resposta d'error

```json
{
  "status": "ERROR",
  "error": "NOT_FOUND",
  "message": "recipe amb id 99 no existeix"
}
```

| Camp | Descripció |
|---|---|
| `status` | `"ERROR"` |
| `error` | **Codi d'error** (vegeu l'apartat 6). És el que han de consultar els programes |
| `message` | Text per a persones. És orientatiu i pot canviar; no s'ha de fer servir per prendre decisions |

---

## 4. Operacions suportades

| Operació | Comanda | Què fa |
|---|---|---|
| Llistar | `LIST` | Retorna tots els elements d'un recurs (opcionalment filtrats o paginats) |
| Llegir | `SHOW` | Retorna un element pel seu `id` |
| Crear | `CREATE` | Crea un element nou i el retorna amb el seu `id` |
| Modificar | `UPDATE` | Canvia camps d'un element i el retorna actualitzat |
| Esborrar | `DELETE` | Esborra un element |

### 4.1 `LIST`: llistar elements

**Dades**

| Camp | Obligatori | Descripció |
|---|---|---|
| `resource` | Sí | Recurs a llistar |
| `filter` | No | Només per a `recipe`: `{"category": "..."}` o `{"name": "..."}` |
| `page` | No | Només per a `recipe` i sense filtre: activa la paginació |
| `page_size` | No | Mida de la pàgina (per defecte, 10) |

Si hi ha `filter`, el de `category` té prioritat sobre el de `name`, i amb qualsevol filtre no s'aplica la paginació. Per a la resta de recursos, `filter` i `page` s'ignoren.

**Resposta:** `data.items` és una llista d'elements (buida si no n'hi ha cap).

**Exemple**

```json
{"command": "LIST", "data": {"resource": "recipe", "filter": {"category": "Tisanes"}}}
```
```json
{
  "status": "OK",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "Camamilla",
        "duration": 10,
        "step_by_step": "Bullir aigua i infusionar",
        "sub_name": null,
        "note": null,
        "dosage": null,
        "description": "Relaxant",
        "created_at": "2026-10-20T09:31:10.557495"
      }
    ]
  }
}
```

### 4.2 `SHOW`: llegir un element

**Dades**

| Camp | Obligatori | Descripció |
|---|---|---|
| `resource` | Sí | Tipus d'element |
| `id` | Sí | Identificador |

**Resposta:** `data` és l'element.

**Exemple**

```json
{"command": "SHOW", "data": {"resource": "ingredient", "id": 1}}
```
```json
{
  "status": "OK",
  "data": {
    "id": 1,
    "scientific_name": null,
    "common_name": "Camamilla",
    "family": null,
    "description": null,
    "country_origin": null,
    "type": "flower",
    "image_url": null
  }
}
```

### 4.3 `CREATE`: crear un element

**Dades**

| Camp | Obligatori | Descripció |
|---|---|---|
| `resource` | Sí | Tipus d'element |
| `values` | Sí | Camps del nou element. Els obligatoris depenen del recurs (apartat 5) |

Les claus de `values` que no són camps del recurs s'ignoren. No s'envia mai l'`id`: el genera la base de dades.

**Resposta:** `data` és l'element creat, ja amb el seu `id`.

**Exemple**

```json
{
  "command": "CREATE",
  "data": {
    "resource": "user",
    "values": { "user_name": "anna", "email": "anna@mail.com", "password": "1234" }
  }
}
```
```json
{
  "status": "OK",
  "data": { "id": 1, "user_name": "anna", "alias": "anna", "email": "anna@mail.com", "phone": null }
}
```

Notes:
- La contrasenya es guarda amb *hash* i **mai** es retorna al client.
- Si no s'indica `alias`, el servidor hi posa el valor de `user_name`.
- A les receptes, `created_at` l'assigna el servidor.

### 4.4 `UPDATE`: modificar un element

**Dades**

| Camp | Obligatori | Descripció |
|---|---|---|
| `resource` | Sí | Tipus d'element |
| `id` | Sí | Element a modificar |
| `values` | Sí | **Només els camps que es volen canviar** |

Només es poden modificar els camps *editables* del recurs (apartat 5). Els altres s'ignoren sense error. Els camps que no s'envien no es toquen.

**Resposta:** `data` és l'element ja actualitzat.

**Exemple**

```json
{"command": "UPDATE", "data": {"resource": "recipe", "id": 1, "values": {"duration": 15}}}
```

### 4.5 `DELETE`: esborrar un element

**Dades**

| Camp | Obligatori | Descripció |
|---|---|---|
| `resource` | Sí | Tipus d'element |
| `id` | Sí | Element a esborrar |

**Resposta:** `data` és `{}`.

**Exemple**

```json
{"command": "DELETE", "data": {"resource": "recipe", "id": 1}}
```
```json
{"status": "OK", "data": {}}
```

---

## 5. Recursos

| `resource` | Entitat |
|---|---|
| `recipe` | Receptes |
| `ingredient` | Plantes medicinals |
| `category` | Categories de receptes |
| `user` | Usuaris |

Per a cada recurs: camps que retorna el servidor, camps **obligatoris** en crear i camps **editables** amb `UPDATE`.

| Recurs | Camps retornats | Obligatoris | Editables |
|---|---|---|---|
| `recipe` | `id`, `name`, `duration`, `step_by_step`, `sub_name`, `note`, `dosage`, `description`, `created_at` | `name`, `step_by_step` | tots menys `id` i `created_at` |
| `ingredient` | `id`, `scientific_name`, `common_name`, `family`, `description`, `country_origin`, `type`, `image_url` | `common_name`, `type` | tots menys `id` |
| `category` | `id`, `name`, `description` | `name` | `name`, `description` |
| `user` | `id`, `user_name`, `alias`, `email`, `phone` | `user_name`, `email`, `password` | `user_name`, `alias`, `email`, `phone` |

Les dates (`created_at`) viatgen en format ISO 8601 (`2026-10-20T09:31:10.557495`). Els camps opcionals sense valor es retornen com a `null`.

---

## 6. Gestió d'errors

### Estratègia

- **Tota petició rep una resposta**, mai silenci: `OK` o `ERROR`.
- **Un error no tanca la connexió.** Després d'una resposta d'error, el client pot continuar enviant peticions pel mateix socket.
- **El servidor no cau** per una petició incorrecta. Tots els errors, previstos o no, es converteixen en una resposta `ERROR`.
- **Cada error té un codi estable** (`error`) i un text legible (`message`). Els programes han de mirar el codi.
- **Els errors interns no es detallen al client.** Només es retorna `SERVER_ERROR`; el detall queda al terminal del servidor.
- **Atomicitat.** Cada petició s'executa dins d'una transacció: si hi ha un error, es desfan tots els canvis d'aquella petició (*rollback*).
- **Errors de connexió** (servidor aturat, connexió tancada): els gestiona el client, no formen part del protocol. El client els mostra i acaba.

### Codis d'error

| Codi | Quan es produeix |
|---|---|
| `INVALID_DATA` | La línia no és JSON vàlid; el missatge no és un objecte amb el camp `command`; `data` no és un objecte; falta un camp obligatori de `data` (`resource`, `id`, `values`); `resource` desconegut; falten camps obligatoris a `values`; les dades no passen la validació |
| `UNKNOWN_COMMAND` | `command` no és cap de les comandes del protocol |
| `NOT_FOUND` | L'`id` indicat no existeix (`SHOW`, `UPDATE`, `DELETE`) |
| `ALREADY_EXISTS` | Es vol crear un element que ja existeix (ara mateix, un usuari amb un correu repetit) |
| `SERVER_ERROR` | Qualsevol altre error inesperat del servidor, com ara un error de la base de dades |

### Exemples

Element inexistent:
```json
{"command": "SHOW", "data": {"resource": "recipe", "id": 99}}
```
```json
{"status": "ERROR", "error": "NOT_FOUND", "message": "recipe amb id 99 no existeix"}
```

Falta un camp obligatori:
```json
{"command": "SHOW", "data": {"resource": "recipe"}}
```
```json
{"status": "ERROR", "error": "INVALID_DATA", "message": "Falta el camp 'id'"}
```

Camps obligatoris sense valor en crear:
```json
{"command": "CREATE", "data": {"resource": "recipe", "values": {"name": "Sense passos"}}}
```
```json
{"status": "ERROR", "error": "INVALID_DATA", "message": "Falten camps obligatoris: step_by_step"}
```

Correu repetit:
```json
{"status": "ERROR", "error": "ALREADY_EXISTS", "message": "Aquest email ja existeix"}
```

Comanda desconeguda:
```json
{"command": "DANCE", "data": {}}
```
```json
{"status": "ERROR", "error": "UNKNOWN_COMMAND", "message": "Comanda desconeguda: DANCE"}
```

Línia que no és JSON:
```json
{"status": "ERROR", "error": "INVALID_DATA", "message": "Missatge mal format"}
```

---

## 7. On és implementat

```
client/client.py      Menús de terminal. Només coneix el protocol; mai toca la BD.
common/protocol.py    El "contracte": constants, camps i funcions per construir i llegir missatges.
server/server.py      Socket: accepta clients, llegeix línies i envia respostes.
server/router.py      Router: identifica la comanda i la delega al servei; converteix errors en respostes.
server/service_layer/ Casos d'ús (services.py) i Unit of Work (unit_of_work.py).
server/adapters/      Repositoris i mapping de SQLAlchemy (orm.py).
server/domain/        Entitats del domini (Python pur, sense SQLAlchemy).
```

Recorregut d'una petició:

```
client → socket → server.py → router.py → services.py → unit_of_work.py → repositoris → BD
```

La resposta fa el camí invers. Per la xarxa només hi viatgen **diccionaris/JSON**: els models i els repositoris mai surten del servidor.

`common/protocol.py` ofereix quatre funcions:

| Funció | Qui la fa servir | Què fa |
|---|---|---|
| `build_request(command, data)` | Client | Construeix la petició (en bytes, amb `\n`) |
| `build_ok(data)` | Servidor | Construeix una resposta d'èxit |
| `build_error(error, message)` | Servidor | Construeix una resposta d'error |
| `parse_message(line)` | Tots dos | Converteix una línia rebuda en un diccionari |

### Fora de l'abast del protocol actual

- Relacions entre elements (wish lists, ingredients d'una recepta, perfil d'usuari): no hi ha comandes per gestionar-les.
- Inici de sessió (*login*) i permisos.

---

## 8. Com executar-ho

Cal tenir una base de dades configurada al fitxer `.env` (vegeu `server/config.py`) i les dependències instal·lades (`pip install -r requirements.txt`).

Des de la **carpeta arrel** del projecte, en dos terminals:

```
python -m server.server     # primer: engega el servidor i el deixa escoltant
python -m client.client     # després: obre el client
```

El servidor s'atura amb `Ctrl+C`.