# Farmaciola Verda

Aplicació client-servidor amb sockets TCP **protegits amb TLS i certificats**. El **servidor** és l'únic que parla amb la base de dades (SQLAlchemy); el **client** és un programa de terminal que només envia peticions i mostra les respostes.

Aquest document descriu el **protocol de comunicació** entre els dos, la **capa de seguretat** (autenticació per certificats, clau de sessió i xifratge simètric), com **executar-ho** i com **provar-ho**.

## Índex

1. [Visió general](#1-visió-general)
2. [Format de la petició](#2-format-de-la-petició)
3. [Format de la resposta](#3-format-de-la-resposta)
4. [Operacions suportades](#4-operacions-suportades)
5. [Recursos](#5-recursos)
6. [Gestió d'errors](#6-gestió-derrors)
7. [On és implementat](#7-on-és-implementat)
8. [Com executar-ho](#8-com-executar-ho)
9. [Seguretat](#9-seguretat)
10. [Generació dels certificats](#10-generació-dels-certificats)
11. [Tests](#11-tests)
12. [Demostració multi-client](#12-demostració-multi-client)

---

## 1. Visió general

| Aspecte | Valor |
|---|---|
| Transport | TCP sobre **TLS** amb autenticació mútua per certificats (apartat 9) |
| Adreça per defecte | `127.0.0.1:5000` (definida a `common/protocol.py`) |
| Format dels missatges | JSON, codificat en UTF-8 i **xifrat amb la clau de sessió** abans d'enviar-lo |
| Delimitador | Cada missatge és **una sola línia** acabada en `\n` (un *token* Fernet en Base64, que no conté salts de línia) |
| Patró | Petició → resposta. Cada petició rep **exactament una** resposta |
| Clients | El servidor atén **diversos clients alhora** (`asyncio`: una *Task* per connexió) |

Com que TCP és un flux de bytes i no de missatges, el `\n` final és el que indica on acaba cada missatge. Per això un missatge **no pot contenir salts de línia reals** (dins del JSON, un salt de línia dins d'un text s'escriu com `\n` escapat, i `json.dumps` ja ho fa sol).

> Als exemples d'aquest document els JSON es mostren en diverses línies per facilitar-ne la lectura, però pel socket sempre viatgen en una sola línia **i xifrats**: el JSON que veus aquí és el contingut que el client xifra abans d'enviar i que el servidor desxifra en rebre.

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

- **Tota petició vàlida rep una resposta**, mai silenci: `OK` o `ERROR`. L'única excepció són els missatges que no es poden desxifrar (clau incorrecta, token manipulat o enviat en clar): el servidor els considera un error d'integritat, **tanca la connexió** i no respon (apartat 9).
- **Un error no tanca la connexió.** Després d'una resposta d'error, el client pot continuar enviant peticions pel mateix socket.
- **El servidor no cau** per una petició incorrecta. Tots els errors, previstos o no, es converteixen en una resposta `ERROR`.
- **Cada error té un codi estable** (`error`) i un text legible (`message`). Els programes han de mirar el codi.
- **Els errors interns no es detallen al client.** Només es retorna `SERVER_ERROR`; el detall queda al terminal del servidor.
- **Atomicitat.** Cada petició s'executa dins d'una transacció: si hi ha un error, es desfan tots els canvis d'aquella petició (*rollback*).
- **Errors de connexió** (servidor aturat, connexió tancada, certificat rebutjat): els gestiona el client, no formen part del protocol. El client els mostra i acaba.

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
client/src/client/client.py
                      Menús de terminal i connexió segura (TLS + clau de sessió). Només coneix el
                      protocol; mai toca la BD.
common/protocol.py    El "contracte": constants, camps i funcions per construir i llegir missatges.
server/server.py      Servidor asyncio (start_server): context TLS, autenticació per certificat,
                      clau de sessió, i una corutina per client que llegeix línies xifrades.
server/router.py      Router: identifica la comanda i la delega al servei; converteix errors en respostes.
server/service_layer/ Casos d'ús (services.py) i Unit of Work (unit_of_work.py).
server/adapters/      Repositoris i mapping de SQLAlchemy (orm.py).
server/domain/        Entitats del domini (Python pur, sense SQLAlchemy).
```

Recorregut d'una petició:

```
client → (TLS + Fernet) → server.py → router.py → services.py → unit_of_work.py → repositoris → BD
```

La resposta fa el camí invers. Per la xarxa només hi viatgen **diccionaris/JSON xifrats**: els models i els repositoris mai surten del servidor.

La seguretat viu **només** a `server.py` i al client. El router, els serveis, la unit of work i els repositoris no en saben res: reben la línia ja desxifrada i retornen la resposta en clar, que el servidor xifra abans d'enviar-la.

`common/protocol.py` ofereix quatre funcions:

| Funció | Qui la fa servir | Què fa |
|---|---|---|
| `build_request(command, data)` | Client | Construeix la petició (en bytes, amb `\n`) |
| `build_ok(data)` | Servidor | Construeix una resposta d'èxit |
| `build_error(error, message)` | Servidor | Construeix una resposta d'error |
| `parse_message(line)` | Tots dos | Converteix una línia rebuda en un diccionari |

### Fora de l'abast del protocol actual

- Relacions entre elements (wish lists, ingredients d'una recepta, perfil d'usuari): no hi ha comandes per gestionar-les.
- Permisos per usuari o per recurs: tots els clients autenticats (amb certificat vàlid) tenen els mateixos drets.
- Integritat per capçaleres HTTP (`X-Content-Digest`): no s'aplica, perquè la comunicació no és una API REST. La integritat la garanteix Fernet (HMAC-SHA256 dins de cada token).

---

## 8. Com executar-ho

Cal tenir una base de dades configurada al fitxer `.env` (vegeu `server/config.py`), les dependències instal·lades i els certificats generats a `certs/` (apartat 10).

```
python -m venv venv
venv\Scripts\activate            # a Linux/macOS: source venv/bin/activate
python -m pip install -r requirements.txt
```

Exemple de `.env` (**no hi posis credencials reals**):

```
ENVIRONMENT=development
DB_URL_DEVELOPMENT=sqlite:///build/FarmaciaVerda.db
DB_URL_TEST=sqlite:///:memory:
```

La carpeta `build/` ha d'existir a l'arrel del projecte (SQLite crea el fitxer, però no la carpeta).

Des de la **carpeta arrel** del projecte, en terminals separats:

```
python -m server.server                          # primer: engega el servidor
python -m client.src.client.client client1       # un client, amb el certificat de client1
python -m client.src.client.client client2       # un altre client alhora, amb client2
```

L'argument és el nom del certificat que fa servir el client (`certs/<nom>/<nom>.crt` i `.key`). Si no se'n dona cap, s'usa `client1`. El servidor s'atura amb `Ctrl+C`.

---

## 9. Seguretat

La seguretat combina **criptografia asimètrica** (per autenticar i per acordar una clau) i **simètrica** (per xifrar les dades). Tot passa abans d'acceptar qualsevol petició de negoci.

### 9.1 Flux d'una connexió

```
Client                                              Servidor
  |  1. Connexió TCP + handshake TLS                    |
  |  -- certificat del client (signat per la CA) -->    |
  |  <-- certificat del servidor (signat per la CA) --  |  2. Es validen contra ca.crt
  |                                                     |     (si falla: es tanca la connexió)
  |                                                     |  3. Es comprova que el certificat
  |                                                     |     no estigui ja connectat
  |                                                     |  4. Es genera una clau de sessió (Fernet)
  |  <-- clau de sessió xifrada amb la clau pública --  |     i es xifra amb la clau pública
  |      RSA del client (OAEP + SHA-256, Base64)        |     del certificat del client
  |  5. El client la desxifra amb la seva clau privada  |
  |  == a partir d'aquí, tot va xifrat amb Fernet ==    |
  |  -- token Fernet (petició JSON) -->                 |  6. Es desxifra i va al router
  |  <-- token Fernet (resposta JSON) --                |  7. La resposta es xifra i s'envia
```

### 9.2 Autenticació amb certificats

- El servidor usa un `SSLContext` amb `verify_mode = CERT_REQUIRED` i `ca.crt` com a única CA de confiança: **un client sense certificat, amb un certificat d'una altra CA o autosignat és rebutjat** durant el handshake i no pot enviar cap petició.
- El client també valida el certificat del servidor contra la mateixa CA (autenticació **mútua**). El certificat del servidor porta `subjectAltName = DNS:localhost, IP:127.0.0.1`.
- **Un mateix certificat no pot estar connectat dues vegades alhora**: el servidor guarda l'empremta SHA-256 de cada certificat actiu i tanca la segona connexió. L'empremta s'allibera quan el client es desconnecta.
- Els certificats de client han de ser **RSA** (la clau de sessió es xifra amb la seva clau pública). Si no ho són, el servidor tanca la connexió.

### 9.3 Clau de sessió i xifratge simètric

- Cada connexió rep una **clau de sessió nova** (`Fernet.generate_key()`), que no es reutilitza mai entre clients ni entre connexions.
- La clau viatja xifrada amb **RSA-OAEP (SHA-256)** i només la pot llegir el propietari de la clau privada del certificat.
- Les dades es xifren amb **Fernet** (AES-128-CBC amb HMAC-SHA256). Això dona **confidencialitat** i també **integritat**: un token modificat o xifrat amb una altra clau no es pot desxifrar (`InvalidToken`).
- Un missatge que no es pot desxifrar (enviat en clar, manipulat o d'una altra sessió) provoca el tancament de la connexió i un avís al log del servidor.
- El servidor limita la mida d'una línia (64 KiB). Si es supera, respon amb `INVALID_DATA` (xifrat) i tanca la connexió.

> **Sobre `X-Content-Digest`:** la comunicació és sobre sockets i no una API REST, de manera que no cal la capçalera de digest SHA-256 de l'enunciat. La integritat de cada missatge la verifica el HMAC de Fernet.

---

## 10. Generació dels certificats

Els certificats estan a `certs/`:

```
certs/
├── ca.crt, ca.key        Autoritat de certificació (ca.key és secreta: no es lliura ni es puja a git)
├── client.ext            Extensions dels clients (extendedKeyUsage = clientAuth)
├── servidor/             server.crt, server.key, server.ext (amb el subjectAltName)
├── client1/              client1.crt, client1.key
└── client2/              client2.crt, client2.key
```

Es generen amb OpenSSL (executar-ho a la carpeta `certs/`; **si ja els tens, no ho tornis a fer**, perquè se sobreescriurien):

```bash
# 1. CA
openssl genrsa -out ca.key 2048
openssl req -x509 -new -key ca.key -sha256 -days 365 -out ca.crt -subj "/CN=MiCA"

# 2. Servidor (server.ext conté: subjectAltName=DNS:localhost,IP:127.0.0.1)
openssl genrsa -out servidor/server.key 2048
openssl req -new -key servidor/server.key -out servidor/server.csr -subj "/CN=localhost"
openssl x509 -req -in servidor/server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out servidor/server.crt -days 365 -sha256 -extfile servidor/server.ext

# 3. Clients (repetir per a client1 i client2; client.ext conté: extendedKeyUsage=clientAuth)
openssl genrsa -out client1/client1.key 2048
openssl req -new -key client1/client1.key -out client1/client1.csr -subj "/CN=client1"
openssl x509 -req -in client1/client1.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out client1/client1.crt -days 365 -sha256 -extfile client.ext
```

Comprovació: `openssl verify -CAfile ca.crt servidor/server.crt client1/client1.crt client2/client2.crt` ha de mostrar `OK` tres vegades.

---

## 11. Tests

Des de l'arrel del projecte (els tests carreguen els certificats de `certs/` amb rutes relatives):

```
python -m pytest -v
```

| Fitxer | Què prova |
|---|---|
| `test_protocol.py` | Construcció i lectura de missatges |
| `test_validation.py` | Validació de dades |
| `test_services.py` | Casos d'ús (amb una BD falsa) |
| `test_unit_of_work.py` | Commit i rollback |
| `test_router.py` | Comandes, errors i codis de resposta |
| `test_server.py` | Capa de sockets: bucle de lectura/resposta, gestió d'errors de xarxa, i **diversos clients alhora** sobre un servidor real amb TLS (un client callat no bloqueja els altres; una petició lenta no congela el bucle d'events) |
| `test_security.py` | **Autenticació** (certificats vàlids acceptats; sense certificat, d'una altra CA, autosignat i duplicat rebutjats), **clau de sessió** (vàlida, diferent a cada connexió, només llegible amb la clau privada correcta) i **xifratge** (peticions en clar, tokens manipulats o d'una altra sessió rebutjats; res en clar pel cable) |
| `tls_helpers.py` | Utilitats: clients TLS reals i generació de certificats falsos al vol |

Resultat actual: **356 tests passen**. Per mesurar la cobertura:

```
python -m pytest --cov=server --cov=common --cov-report=term-missing
```

La capa de seguretat (`handle_client`), el router, els serveis i el protocol tenen cobertura completa. Els tests de seguretat comproven també el cas negatiu: si s'afebleix el servidor (per exemple, `CERT_NONE` en comptes de `CERT_REQUIRED`), fallen.

---

## 12. Demostració multi-client

El servidor atén els clients amb `asyncio`: una *Task* per connexió, i les consultes a la BD s'executen en fils (`asyncio.to_thread`) perquè una petició lenta no bloquegi el bucle d'events.

Per reproduir-ho, a la carpeta arrel i amb quatre terminals:

1. **Terminal 1:** `python -m server.server`
2. **Terminal 2:** `python -m client.src.client.client client1`
3. **Terminal 3:** `python -m client.src.client.client client2`
4. **Terminal 4:** `python -m client.src.client.client client1` (el mateix certificat que el Terminal 2)

Què s'hi ha de veure:

- Al log del servidor: `Client autenticat: CN=client1` i `CN=client2`, tots dos actius a la vegada.
- Als terminals 2 i 3: `client1` crea una recepta mentre `client2` en filtra o en llista d'altres, sense esperar-se.
- Al terminal 4: el client és rebutjat (`Connection with the server lost: El servidor ha rebutjat la connexió`) i al log del servidor apareix `certificat ja connectat`.

Proves de rebuig addicionals (automatitzades a `test_security.py`): client sense certificat, amb un certificat d'una altra CA o autosignat.

![Tests](docs/01_tests.png)
![Cobertura](docs/02_cobertura.png)
![Demostració multi-client](docs/03_multiclient.png)