from src.server.services.security import hash_password, verify_password


def test_hash_is_not_the_plain_password():
    assert "secret" not in hash_password("secret")


def test_same_password_gives_different_hashes():
    assert hash_password("secret") != hash_password("secret")


def test_verify_accepts_the_right_password_only():
    stored = hash_password("secret")
    assert verify_password("secret", stored)
    assert not verify_password("other", stored)


def test_verify_rejects_malformed_hashes():
    assert not verify_password("secret", "not-a-hash")
