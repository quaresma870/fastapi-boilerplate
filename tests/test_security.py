"""
Unit tests for app.core.security's password hashing — no DB/HTTP needed.
"""

from app.core.security import hash_password, verify_password


class TestPasswordHashing:
    def test_round_trip(self):
        hashed = hash_password("correct-password-123")
        assert verify_password("correct-password-123", hashed) is True

    def test_wrong_password_rejected(self):
        hashed = hash_password("correct-password-123")
        assert verify_password("wrong-password", hashed) is False

    def test_malformed_hash_returns_false_not_raise(self):
        assert verify_password("anything", "not-a-real-hash") is False

    def test_empty_string_hash_does_not_raise(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("not-empty", hashed) is False

    def test_long_passwords_with_same_72_byte_prefix_are_distinguished(self):
        """Regression test: bcrypt only consumes the first 72 bytes of its
        input. Hashing the raw password directly (without a pre-hash step)
        means two different passwords sharing the same first 72 bytes hash
        identically and verify against each other — even though the
        registration schema explicitly allows passwords up to 128
        characters. SHA-256 pre-hashing fixes this; this test would fail
        without it."""
        hashed = hash_password("a" * 72 + "SECRETSUFFIX1")
        assert verify_password("a" * 72 + "TOTALLY_UNRELATED_TEXT_HERE_2", hashed) is False
        assert verify_password("a" * 72 + "SECRETSUFFIX1", hashed) is True

    def test_long_password_within_schema_limit_round_trips_correctly(self):
        """128 chars is the registration schema's max_length — confirm the
        full string's entropy is actually used, not just a truncated prefix."""
        long_pw = "Tr0ub4dor&3" * 11  # 121 chars, within the 128 limit
        hashed = hash_password(long_pw)
        assert verify_password(long_pw, hashed) is True
        assert verify_password(long_pw[:-1] + "X", hashed) is False  # last char matters

    def test_hash_is_not_the_plaintext(self):
        hashed = hash_password("correct-password-123")
        assert "correct-password-123" not in hashed

    def test_same_password_produces_different_hashes(self):
        """Confirms a fresh random salt is used each time (bcrypt.gensalt())."""
        h1 = hash_password("correct-password-123")
        h2 = hash_password("correct-password-123")
        assert h1 != h2
        assert verify_password("correct-password-123", h1) is True
        assert verify_password("correct-password-123", h2) is True
