import asyncio

from common import protocol
from server import router
from server.db import Base, engine

from server.adapters import orm


async def handle_client(reader, writer):
    """Atén un client: llegeix línies, les passa al router i envia la resposta.

    Cada connexió s'executa com una Task pròpia (ho fa asyncio.start_server),
    així que molts clients poden ser atesos alhora amb un sol fil.
    """
    addr = writer.get_extra_info("peername")
    print(f"[+] Client connectat: {addr}")
    try:
        # readline() espera (sense bloquejar el bucle) fins que arriba un \n.
        # Retorna b"" quan el client tanca la connexió.
        while line := await reader.readline():
            # El router i SQLAlchemy són síncrons (bloquegen mentre esperen la BD).
            # to_thread els executa en un altre fil perquè no congelin el bucle
            # d'events i la resta de clients puguin seguir avançant.
            response = await asyncio.to_thread(router.handle, line)
            writer.write(response)
            await writer.drain()  # espera si el buffer d'enviament està ple
    except ValueError:
        # Línia més llarga que el límit del lector (64 KiB): no es pot resincronitzar.
        print(f"[!] Missatge massa llarg de {addr}")
        writer.write(protocol.build_error(protocol.INVALID_DATA, "Missatge massa llarg"))
    except (ConnectionError, OSError) as e:
        print(f"[!] Connexió perduda amb {addr}: {e}")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass  # el client ja havia marxat; no hi ha res més a tancar
    print(f"[-] Client desconnectat: {addr}")


async def main():

    # 1. Enllaçar les classes del domini amb les taules
    orm.start_mappers()

    # 2. Crear les taules si no existeixen
    orm.metadata.create_all(engine)

    # 3. Crear les taules si no existeixen
    Base.metadata.create_all(engine)

    # 4. Arrencar el servidor: crea el socket, fa bind/listen i, per cada nova
    #    connexió, llança handle_client(reader, writer) com una Task nova.
    server = await asyncio.start_server(handle_client, protocol.HOST, protocol.PORT)
    addresses = [s.getsockname() for s in server.sockets]
    print(f"Servidor escoltant a {addresses}")

    # 5. Servir fins que es cancel·li (Ctrl+C)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor aturat")
