import pytest
from pathlib import Path
from codeguard.config.loader import ConfigLoader


class TestConfigLoader:
    def test_load_valid_toml(self, temp_workspace):
        path = temp_workspace / "codeguard.toml"
        path.write_text("""
[workspace]
project_root = "/home/user/project"
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"
""")
        loader = ConfigLoader()
        config = loader.load_file(str(path))
        assert config["workspace"]["project_root"] == "/home/user/project"
        assert config["llm"]["provider"] == "deepseek"
        assert config["llm"]["model"] == "deepseek-v4-flash"

    def test_load_file_not_found_returns_empty(self):
        loader = ConfigLoader()
        config = loader.load_file("/nonexistent/path/config.toml")
        assert config == {}

    def test_load_unknown_section_fails(self, temp_workspace):
        path = temp_workspace / "codeguard.toml"
        path.write_text("[unknown_section]\nkey = \"value\"\n")
        loader = ConfigLoader()
        with pytest.raises(ValueError, match="Unknown"):
            loader.load_file(str(path))

    def test_load_corrupted_toml_fails(self, temp_workspace):
        path = temp_workspace / "codeguard.toml"
        path.write_text("this is not valid toml {{{")
        loader = ConfigLoader()
        with pytest.raises(ValueError, match="Invalid TOML"):
            loader.load_file(str(path))

    def test_load_known_sections_pass(self, temp_workspace):
        path = temp_workspace / "codeguard.toml"
        path.write_text("""
[workspace]
project_root = "."
[llm]
provider = "deepseek"
[loop]
max_steps = 50
[tools]
enabled_tools = ["read_file"]
[sensors]
required_sensors = ["pytest"]
[memory]
enabled = true
[ui]
web_port = 8080
[approval]
cli_timeout = 300
[mode]
mode = "test"
""")
        loader = ConfigLoader()
        config = loader.load_file(str(path))
        assert "workspace" in config
        assert "llm" in config
        assert "loop" in config
        assert "tools" in config
        assert "sensors" in config
        assert "memory" in config
        assert "ui" in config
        assert "approval" in config
        assert "mode" in config

    def test_load_no_include_support(self, temp_workspace):
        path = temp_workspace / "codeguard.toml"
        path.write_text("[workspace]\ninclude = \"other.toml\"\n")
        loader = ConfigLoader()
        config = loader.load_file(str(path))
        assert config["workspace"]["include"] == "other.toml"

    def test_load_no_env_var_interpolation(self, temp_workspace):
        path = temp_workspace / "codeguard.toml"
        path.write_text("[workspace]\nproject_root = \"$HOME/project\"\n")
        loader = ConfigLoader()
        config = loader.load_file(str(path))
        assert config["workspace"]["project_root"] == "$HOME/project"

    def test_load_empty_file(self, temp_workspace):
        path = temp_workspace / "codeguard.toml"
        path.write_text("")
        loader = ConfigLoader()
        config = loader.load_file(str(path))
        assert config == {}

    def test_load_returns_dict_with_all_known_sections(self, temp_workspace):
        path = temp_workspace / "codeguard.toml"
        path.write_text("[workspace]\nproject_root = \".\"\n")
        loader = ConfigLoader()
        config = loader.load_file(str(path))
        assert isinstance(config, dict)
        assert "workspace" in config