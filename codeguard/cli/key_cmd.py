"""CLI key command — manage API keys via Windows Credential Manager."""

import getpass
import sys
from codeguard.credentials.store import KeyringCredentialStore


def key_set_command(args: list[str]) -> None:
    """Store an API key for a provider.

    Reads the key interactively via getpass (hidden input, never echoed).
    """
    provider = "deepseek"
    for i, arg in enumerate(args):
        if arg == "--provider" and i + 1 < len(args):
            provider = args[i + 1]
            break

    store = KeyringCredentialStore()
    key = getpass.getpass(f"Enter API key for {provider}: ").strip()
    if not key:
        print("Error: key must not be empty", file=sys.stderr)
        sys.exit(1)
    store.set(provider, key)
    print(f"API key for {provider} stored successfully.")
    sys.exit(0)


def key_status_command(args: list[str]) -> None:
    """Check whether an API key is set for a provider."""
    provider = "deepseek"
    for i, arg in enumerate(args):
        if arg == "--provider" and i + 1 < len(args):
            provider = args[i + 1]
            break

    store = KeyringCredentialStore()
    status = store.status(provider)
    print(f"  {provider}: {status}")
    sys.exit(0)


def key_update_command(args: list[str]) -> None:
    """Update an existing API key (alias for set)."""
    key_set_command(args)


def key_clear_command(args: list[str]) -> None:
    """Remove a stored API key for a provider."""
    provider = "deepseek"
    for i, arg in enumerate(args):
        if arg == "--provider" and i + 1 < len(args):
            provider = args[i + 1]
            break

    store = KeyringCredentialStore()
    store.clear(provider)
    print(f"API key for {provider} cleared.")
    sys.exit(0)