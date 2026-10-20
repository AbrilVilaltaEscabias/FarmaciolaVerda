"""Unit of Work real (SqlAlchemyUnitOfWork) amb la sessió mockejada."""
from unittest.mock import MagicMock

import pytest

from server.adapters.sqlalchemy_repositories import (
    CategoryRepository, IngredientRepository, RecipeRepository, UserRepository,
)
from server.service_layer.unit_of_work import AbstractUnitOfWork, SqlAlchemyUnitOfWork


@pytest.fixture
def session():
    return MagicMock(name="session")


@pytest.fixture
def uow(session):
    return SqlAlchemyUnitOfWork(session_factory=MagicMock(return_value=session))


def test_is_an_abstract_uow_subclass(uow):
    assert isinstance(uow, AbstractUnitOfWork)


def test_abstract_uow_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AbstractUnitOfWork()


def test_session_is_created_lazily_on_enter(session):
    factory = MagicMock(return_value=session)
    uow = SqlAlchemyUnitOfWork(session_factory=factory)
    factory.assert_not_called()
    with uow:
        factory.assert_called_once_with()


def test_enter_returns_the_uow(uow):
    with uow as u:
        assert u is uow


def test_repositories_are_the_right_types(uow):
    with uow:
        assert isinstance(uow.recipes, RecipeRepository)
        assert isinstance(uow.users, UserRepository)
        assert isinstance(uow.categories, CategoryRepository)
        assert isinstance(uow.ingredients, IngredientRepository)


def test_all_repositories_share_the_same_session(uow, session):
    with uow:
        repos = [uow.recipes, uow.users, uow.categories, uow.ingredients]
        assert all(r.session is session for r in repos)


def test_commit_and_close_on_success(uow, session):
    with uow:
        pass
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()


def test_rollback_and_close_on_exception(uow, session):
    with pytest.raises(RuntimeError):
        with uow:
            raise RuntimeError("boom")
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()
    session.close.assert_called_once_with()


def test_exception_is_not_swallowed(uow):
    with pytest.raises(ValueError, match="x"):
        with uow:
            raise ValueError("x")


def test_flush_commit_rollback_delegate_to_session(uow, session):
    with uow:
        uow.flush()
        session.flush.assert_called_once_with()
        session.commit.reset_mock()
        uow.commit()
        session.commit.assert_called_once_with()
        uow.rollback()
        session.rollback.assert_called_once_with()


def test_each_with_block_gets_a_fresh_session():
    s1, s2 = MagicMock(), MagicMock()
    uow = SqlAlchemyUnitOfWork(session_factory=MagicMock(side_effect=[s1, s2]))
    with uow:
        assert uow.session is s1
    with uow:
        assert uow.session is s2


def test_default_session_factory_is_server_db_session():
    from server.db import Session
    assert SqlAlchemyUnitOfWork().session_factory is Session
