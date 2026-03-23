"""密碼雜湊工具單元測試。"""

from src.api.password import hash_password, verify_password


class TestHashPassword:
    def test_returns_different_salt_each_call(self):
        h1, s1 = hash_password("test")
        h2, s2 = hash_password("test")
        assert s1 != s2
        assert h1 != h2  # same password, different salt → different hash

    def test_hash_and_salt_are_hex(self):
        h, s = hash_password("test")
        bytes.fromhex(h)
        bytes.fromhex(s)


class TestVerifyPassword:
    def test_correct_password(self):
        h, s = hash_password("mypassword")
        assert verify_password("mypassword", h, s) is True

    def test_wrong_password(self):
        h, s = hash_password("mypassword")
        assert verify_password("wrongpassword", h, s) is False

    def test_unicode_password(self):
        h, s = hash_password("密碼測試🔑")
        assert verify_password("密碼測試🔑", h, s) is True
        assert verify_password("密碼測試", h, s) is False
