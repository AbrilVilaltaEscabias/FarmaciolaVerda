"""TCP server entry point. Handles one client at a time (blocking sockets).

Run with:  python -m src.server.server
"""
import logging
import socket
from functools import partial

from src.common.protocol import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ErrorCode,
    ProtocolError,
    Response,
    deserialize_request,
    read_message,
    serialize_response,
)
from src.server.router import Router
from src.server.validation import ValidationError, validate_request

HOST = DEFAULT_HOST
PORT = DEFAULT_PORT

logger = logging.getLogger(__name__)


class Server:
    def __init__(self, router: Router, host: str = HOST, port: int = PORT):
        self._router = router
        self._host = host
        self._port = port

    def process_message(self, raw: bytes) -> Response:
        """bytes -> Request -> validation -> router -> Response.

        Free of socket code, so it is easy to unit test.
        """
        try:
            request = deserialize_request(raw)
            validate_request(request)
            return self._router.handle(request)
        except ProtocolError as exc:
            return Response.failure(exc.code, exc.message)
        except ValidationError as exc:
            return Response.failure(ErrorCode.VALIDATION_ERROR, str(exc))
        except Exception:  # noqa: BLE001 - last line of defence
            logger.exception("Unexpected error while processing request")
            return Response.failure(
                ErrorCode.INTERNAL_ERROR, "Internal server error"
            )

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((self._host, self._port))
            server_sock.listen(1)
            logger.info("Listening on %s:%s", self._host, self._port)

            while True:
                conn, address = server_sock.accept()
                logger.info("Client connected: %s", address)
                with conn:
                    self._serve_client(conn)
                logger.info("Client disconnected: %s", address)

    def _serve_client(self, conn: socket.socket) -> None:
        with conn.makefile("rb") as reader:
            while True:
                try:
                    raw = read_message(reader)
                except ProtocolError as exc:
                    self._send(conn, Response.failure(exc.code, exc.message))
                    return  # stream is out of sync: close the connection
                except ConnectionError:
                    return
                if raw is None:
                    return  # client closed the connection
                try:
                    self._send(conn, self.process_message(raw))
                except ConnectionError:
                    return

    @staticmethod
    def _send(conn: socket.socket, response: Response) -> None:
        conn.sendall(serialize_response(response))


def build_router() -> Router:
    """Composition root: the only place that knows the real database.

    Imports are local so that importing this module (e.g. from the tests)
    never loads the database configuration.
    """
    from src.server.infrastructure.db import Session
    from src.server.infrastructure.unit_of_work import UnitOfWork
    from src.server.routes import (
        register_ingredient_routes,
        register_recipe_routes,
        register_user_routes,
    )
    from src.server.services.ingredient_service import IngredientService
    from src.server.services.recipe_service import RecipeService
    from src.server.services.user_service import UserService

    uow_factory = partial(UnitOfWork, Session)

    router = Router()
    register_user_routes(router, UserService(uow_factory))
    register_recipe_routes(router, RecipeService(uow_factory))
    register_ingredient_routes(router, IngredientService(uow_factory))
    return router


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    Server(build_router()).serve_forever()


if __name__ == "__main__":
    main()
