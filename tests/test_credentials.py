import pytest
import keyring
import keyring.backends.fail
from codeguard.credentials.store import KeyringCredentialStore


class FakeKeyringBackend(keyring.backends.fail.KeyringBackend):
    """In-memory keyring backend for testing. Never touches real OS keychain."""

    def __init__(self):
        self._store = {}

    @property
    def priority(self):
        return 1

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    backend = FakeKeyringBackend()
    keyring.set_keyring(backend)
    # Also patch get_keyring for direct calls
    monkeypatch.setattr(keyring, 'get_keyring', lambda: backend)
    return backend


class TestKeyringCredentialStore:
    def test_set_and_get(self):
        store = KeyringCredentialStore()
        store.set("deepseek", "sk-test-key-12345")
        assert store.get("deepseek") == "sk-test-key-12345"

    def test_get_nonexistent_returns_none(self):
        store = KeyringCredentialStore()
        assert store.get("nonexistent_provider") is None

    def test_status_not_set(self):
        store = KeyringCredentialStore()
        assert store.status("deepseek") == "Not set"

    def test_status_set_shows_no_key(self):
        store = KeyringCredentialStore()
        store.set("deepseek", "sk-test-key-12345")
        status = store.status("deepseek")
        assert "sk-test-key-12345" not in status
        assert "sk-test" not in status
        assert "Set" in status

    def test_status_short_key_masked(self):
        store = KeyringCredentialStore()
        store.set("deepseek", "short")
        status = store.status("deepseek")
        assert "short" not in status

    def test_clear_removes_key(self):
        store = KeyringCredentialStore()
        store.set("deepseek", "sk-test-key-12345")
        store.clear("deepseek")
        assert store.get("deepseek") is None

    def test_clear_nonexistent_no_error(self):
        store = KeyringCredentialStore()
        store.clear("nonexistent_provider")

    def test_update_overwrites(self):
        store = KeyringCredentialStore()
        store.set("deepseek", "sk-old-key")
        store.set("deepseek", "sk-new-key")
        assert store.get("deepseek") == "sk-new-key"

    def test_service_name_is_codeguard(self):
        store = KeyringCredentialStore()
        store.set("deepseek", "sk-test-key")
        backend = keyring.get_keyring()
        found = backend.get_password("codeguard", "deepseek")
        assert found == "sk-test-key"

    def test_key_not_in_repr(self):
        store = KeyringCredentialStore()
        r = repr(store)
        assert "secret" not in r.lower()

    def test_get_uses_default_profile(self):
        store = KeyringCredentialStore()
        store.set("deepseek", "sk-test-key")
        assert store.get("deepseek") == "sk-test-key"


class TestKeyringCredentialStoreFailClosed:
    def test_get_fail_closed_when_backend_unavailable(self, monkeypatch):
        def raise_runtime_error(*args, **kwargs):
            raise RuntimeError("Keyring backend not available")

        monkeypatch.setattr(keyring, 'get_password', raise_runtime_error)
        store = KeyringCredentialStore()
        with pytest.raises(RuntimeError, match="backend"):
            store.get("deepseek")

    def test_set_fail_closed_when_backend_unavailable(self, monkeypatch):
        def raise_runtime_error(*args, **kwargs):
            raise RuntimeError("Keyring backend not available")

        monkeypatch.setattr(keyring, 'set_password', raise_runtime_error)
        store = KeyringCredentialStore()
        with pytest.raises(RuntimeError, match="backend"):
            store.set("deepseek", "sk-test-key")