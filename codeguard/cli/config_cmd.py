"""CLI config command — show effective configuration."""

from codeguard.config.loader import ConfigLoader


def config_command(args: list[str]) -> str:
    """Show effective configuration.

    Returns a string representation of the current configuration.
    """
    parts = ["Effective configuration:"]
    parts.append("  mode: test (default)")
    parts.append("  workspace: (not set)")

    loader = ConfigLoader()
    try:
        user_cfg = loader.load_file("codeguard.toml")
        if user_cfg:
            parts.append("  project_config: codeguard.toml (loaded)")
            for section, values in user_cfg.items():
                for key, val in values.items():
                    parts.append(f"    {section}.{key}: {val}")
        else:
            parts.append("  project_config: (not found)")
    except Exception:
        parts.append("  project_config: (not found)")

    return "\n".join(parts)