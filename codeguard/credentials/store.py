import keyring

_SERVICE_NAME = "codeguard"


class KeyringCredentialStore:
    """Stores API keys via keyring (Windows Credential Manager on Windows).

    service_name: "codeguard"
    profile mapping: provider → username (e.g. "deepseek" → "deepseek:default")

    Fail-closed: if keyring backend is unavailable, all operations raise.
    """

    def __repr__(self) -> str:
        return f"KeyringCredentialStore(service={_SERVICE_NAME!r})"

    def set(self, provider: str, key: str) -> None:
        try:
            keyring.set_password(_SERVICE_NAME, provider, key)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Keyring backend unavailable: {e}"
            ) from e

    def get(self, provider: str) -> str | None:
        try:
            return keyring.get_password(_SERVICE_NAME, provider)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Keyring backend unavailable: {e}"
            ) from e

    def status(self, provider: str) -> str:
        key = self.get(provider)
        if key is None:
            return "Not set"
        return "Set (masked)"

    def clear(self, provider: str) -> None:
        try:
            keyring.delete_password(_SERVICE_NAME, provider)
        except keyring.errors.PasswordDeleteError:
            pass
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Keyring backend unavailable: {e}"
            ) from e