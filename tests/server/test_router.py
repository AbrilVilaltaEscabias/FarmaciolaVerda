from unittest.mock import MagicMock

import pytest

from src.common.operations import Entity as E, Operation as O
from src.common.protocol import ErrorCode, Request
from src.server.domain.exceptions import AlreadyExistsError, NotFoundError
from src.server.router import Router


class DummyDTO:
    def __init__(self, value):
        self.value = value

    def to_dict(self):
        return {"value": self.value}


def router_with(handler, entity=E.USER, operation=O.READ) -> Router:
    router = Router()
    router.register(entity, operation, handler)
    return router


class TestRouter:
    def test_calls_handler_with_request_data(self):
        handler = MagicMock(return_value={"id": 1})
        response = router_with(handler).handle(
            Request(O.READ, E.USER, {"id": 1})
        )
        handler.assert_called_once_with({"id": 1})
        assert response.is_ok and response.data == {"id": 1}

    def test_dto_is_converted_to_dict(self):
        router = router_with(lambda data: DummyDTO(7))
        assert router.handle(Request(O.READ, E.USER, {})).data == {"value": 7}

    def test_list_of_dtos_is_converted(self):
        router = router_with(lambda data: [DummyDTO(1), DummyDTO(2)])
        response = router.handle(Request(O.READ, E.USER, {}))
        assert response.data == [{"value": 1}, {"value": 2}]

    def test_none_result_is_ok_with_no_data(self):
        response = router_with(lambda data: None).handle(
            Request(O.READ, E.USER, {})
        )
        assert response.is_ok and response.data is None

    def test_unregistered_route_is_unsupported(self):
        response = router_with(MagicMock()).handle(
            Request(O.DELETE, E.CATEGORY, {})
        )
        assert not response.is_ok
        assert response.error["code"] == ErrorCode.UNKNOWN_OPERATION.value

    @pytest.mark.parametrize(
        "error, code",
        [
            (NotFoundError("missing"), ErrorCode.NOT_FOUND),
            (AlreadyExistsError("dup"), ErrorCode.CONFLICT),
        ],
    )
    def test_business_errors_become_error_responses(self, error, code):
        handler = MagicMock(side_effect=error)
        response = router_with(handler).handle(Request(O.READ, E.USER, {}))
        assert response.error == {"code": code.value, "message": str(error)}

    def test_unexpected_errors_are_not_swallowed(self):
        handler = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            router_with(handler).handle(Request(O.READ, E.USER, {}))

    def test_registering_a_route_twice_fails(self):
        router = router_with(MagicMock())
        with pytest.raises(ValueError):
            router.register(E.USER, O.READ, MagicMock())
