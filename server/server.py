import socket
import threading
 
from common import protocol
from server import router
from server.db import Base, engine

from server.adapters import orm
 
 
def handle_client(conn, addr):
    """Atén un client: llegeix línies, les passa al handler i envia la resposta."""
    print(f"[+] Client connectat: {addr}")
    try:
        with conn, conn.makefile("rb") as reader:
            #
            for line in reader:                      # una iteració per missatge (fins al \n)
                response = router.handle(line)     # retorna bytes
                conn.sendall(response)
    except (ConnectionError, OSError) as e:
        print(f"[!] Connexió perduda amb {addr}: {e}")
    print(f"[-] Client desconnectat: {addr}")
 
 
def main():

    # 1. Enllaçar les classes del domini amb les taules
    orm.start_mappers()

    # 2. Crear les taules si no existeixen
    orm.metadata.create_all(engine)

    # 3. Crear les taules si no existeixen
    Base.metadata.create_all(engine)
 
    # 4. Arrencar el socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: # crea un socket TCP sobre IPv4
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # evita "address already in use"
        s.bind((protocol.HOST, protocol.PORT)) # associa el socket a una adreça i un port
        s.listen() # el posa en mode escolta, esperant que algú es connecti
        print(f"Servidor escoltant a {protocol.HOST}:{protocol.PORT}")
 
        # 5. Acceptar clients en bucle, un fil per cadascun
        while True:
            conn, addr = s.accept() # espera fins que un client es connecta. Quan ho fa, retorna dos valors: conn (un socket nou, exclusiu per parlar amb aquell client) i addr (la seva adreça).
            handle_client(conn, addr)
 
 
if __name__ == "__main__":
    main()