import pytest
from decimal import Decimal
from codeguard.config.merger import ConfigMerger


class TestConfigMerger:
    def test_merge_intersection_enabled_tools(self):
        merger = ConfigMerger()
        user = {"tools": {"enabled_tools": ["read_file", "write_file", "search_text"]}}
        project = {"tools": {"enabled_tools": ["read_file", "run_process"]}}
        merged = merger.merge(user, project)
        assert set(merged["tools"]["enabled_tools"]) == {"read_file"}

    def test_merge_union_disabled_tools(self):
        merger = ConfigMerger()
        user = {"tools": {"disabled_tools": ["tool_a"]}}
        project = {"tools": {"disabled_tools": ["tool_b"]}}
        merged = merger.merge(user, project)
        assert "tool_a" in merged["tools"]["disabled_tools"]
        assert "tool_b" in merged["tools"]["disabled_tools"]

    def test_merge_stricter_max_steps(self):
        merger = ConfigMerger()
        merged = merger.merge(
            {"loop": {"max_steps": 50}},
            {"loop": {"max_steps": 30}}
        )
        assert merged["loop"]["max_steps"] == 30

    def test_merge_stricter_user_keeps_smaller(self):
        merger = ConfigMerger()
        merged = merger.merge(
            {"loop": {"max_steps": 50}},
            {"loop": {"max_steps": 100}}
        )
        assert merged["loop"]["max_steps"] == 50

    def test_merge_cli_override(self):
        merger = ConfigMerger()
        merged = merger.merge(
            {"llm": {"provider": "deepseek", "model": "v1"}},
            {},
            cli_overrides={"llm.provider": "openai"}
        )
        assert merged["llm"]["provider"] == "openai"
        assert merged["llm"]["model"] == "v1"

    def test_merge_union_required_sensors(self):
        merger = ConfigMerger()
        user = {"sensors": {"required_sensors": ["pytest", "ruff"]}}
        project = {"sensors": {"required_sensors": ["mypy"]}}
        merged = merger.merge(user, project)
        assert set(merged["sensors"]["required_sensors"]) == {"pytest", "ruff", "mypy"}

    def test_merge_union_additional_protected_paths(self):
        merger = ConfigMerger()
        user = {"workspace": {"additional_protected_paths": ["/etc"]}}
        project = {"workspace": {"additional_protected_paths": ["/var"]}}
        merged = merger.merge(user, project)
        assert "/etc" in merged["workspace"]["additional_protected_paths"]
        assert "/var" in merged["workspace"]["additional_protected_paths"]

    def test_merge_union_excluded_paths(self):
        merger = ConfigMerger()
        user = {"workspace": {"excluded_paths": ["/tmp"]}}
        project = {"workspace": {"excluded_paths": ["/cache"]}}
        merged = merger.merge(user, project)
        assert "/tmp" in merged["workspace"]["excluded_paths"]
        assert "/cache" in merged["workspace"]["excluded_paths"]

    def test_merge_intersection_allowed_types(self):
        merger = ConfigMerger()
        user = {"memory": {"allowed_types": ["project_convention", "approved_decision"]}}
        project = {"memory": {"allowed_types": ["project_convention"]}}
        merged = merger.merge(user, project)
        assert merged["memory"]["allowed_types"] == ["project_convention"]

    def test_merge_stricter_memory_limits(self):
        merger = ConfigMerger()
        user = {"memory": {"max_records": 100, "top_k": 10, "context_budget": 2048}}
        project = {"memory": {"max_records": 50, "top_k": 5, "context_budget": 1024}}
        merged = merger.merge(user, project)
        assert merged["memory"]["max_records"] == 50
        assert merged["memory"]["top_k"] == 5
        assert merged["memory"]["context_budget"] == 1024

    def test_merge_stricter_numeric_fields(self):
        merger = ConfigMerger()
        user = {"loop": {
            "max_llm_calls": 100, "max_repair_attempts": 3,
            "session_timeout": 600, "tool_timeout": 30,
            "no_progress_threshold": 3, "token_budget": 100000,
            "cost_budget": 0.5
        }}
        project = {"loop": {
            "max_llm_calls": 50, "max_repair_attempts": 2,
            "session_timeout": 300, "tool_timeout": 15,
            "no_progress_threshold": 2, "token_budget": 50000,
            "cost_budget": 0.25
        }}
        merged = merger.merge(user, project)
        assert merged["loop"]["max_llm_calls"] == 50
        assert merged["loop"]["max_repair_attempts"] == 2
        assert merged["loop"]["session_timeout"] == 300
        assert merged["loop"]["tool_timeout"] == 15
        assert merged["loop"]["no_progress_threshold"] == 2
        assert merged["loop"]["token_budget"] == 50000
        assert merged["loop"]["cost_budget"] == 0.25

    def test_merge_stricter_llm_limits(self):
        merger = ConfigMerger()
        user = {"llm": {"max_output_tokens": 4096, "request_timeout": 60}}
        project = {"llm": {"max_output_tokens": 2048, "request_timeout": 30}}
        merged = merger.merge(user, project)
        assert merged["llm"]["max_output_tokens"] == 2048
        assert merged["llm"]["request_timeout"] == 30

    def test_merge_stricter_sensor_limits(self):
        merger = ConfigMerger()
        user = {"sensors": {"timeout_per_sensor": 30, "output_limit": 4096}}
        project = {"sensors": {"timeout_per_sensor": 15, "output_limit": 2048}}
        merged = merger.merge(user, project)
        assert merged["sensors"]["timeout_per_sensor"] == 15
        assert merged["sensors"]["output_limit"] == 2048

    def test_merge_memory_enabled_upper_overrides(self):
        merger = ConfigMerger()
        user = {"memory": {"enabled": False}}
        project = {"memory": {"enabled": True}}
        merged = merger.merge(user, project)
        assert merged["memory"]["enabled"] is False

    def test_merge_approval_timeout_project_only_shortens(self):
        merger = ConfigMerger()
        user = {"ui": {"approval_timeout": 30}}
        project = {"ui": {"approval_timeout": 60}}
        merged = merger.merge(user, project)
        assert merged["ui"]["approval_timeout"] == 30

    def test_merge_cli_timeout_project_cannot_set(self):
        merger = ConfigMerger()
        user = {"approval": {"cli_timeout": 300}}
        project = {"approval": {"cli_timeout": 999}}
        merged = merger.merge(user, project)
        assert merged["approval"]["cli_timeout"] == 300

    def test_merge_credential_profile_upper_overrides(self):
        merger = ConfigMerger()
        user = {"llm": {"credential_profile": "work"}}
        project = {"llm": {"credential_profile": "hijack"}}
        merged = merger.merge(user, project)
        assert merged["llm"]["credential_profile"] == "work"

    def test_merge_project_root_upper_overrides(self):
        merger = ConfigMerger()
        user = {"workspace": {"project_root": "/user/project"}}
        project = {"workspace": {"project_root": "/hijack/root"}}
        merged = merger.merge(user, project)
        assert merged["workspace"]["project_root"] == "/user/project"

    def test_merge_provider_model_cli_only_overrides(self):
        merger = ConfigMerger()
        user = {"llm": {"provider": "deepseek", "model": "v1"}}
        project = {"llm": {"provider": "hijack", "model": "evil"}}
        merged = merger.merge(user, project)
        assert merged["llm"]["provider"] == "deepseek"
        assert merged["llm"]["model"] == "v1"

    def test_merge_sensor_order_append_dedup(self):
        merger = ConfigMerger()
        user = {"sensors": {"sensor_order": ["pytest", "ruff"]}}
        project = {"sensors": {"sensor_order": ["mypy", "ruff"]}}
        merged = merger.merge(user, project)
        assert merged["sensors"]["sensor_order"] == ["pytest", "ruff", "mypy"]

    def test_merge_per_tool_timeouts_stricter_per_tool(self):
        merger = ConfigMerger()
        user = {"tools": {"per_tool_timeouts": {"read_file": 10, "write_file": 20}}}
        project = {"tools": {"per_tool_timeouts": {"read_file": 5, "write_file": 30}}}
        merged = merger.merge(user, project)
        assert merged["tools"]["per_tool_timeouts"]["read_file"] == 5
        assert merged["tools"]["per_tool_timeouts"]["write_file"] == 20

    def test_merge_mode_not_upgradable(self):
        merger = ConfigMerger()
        user = {"mode": {"mode": "test"}}
        project = {"mode": {"mode": "local"}}
        merged = merger.merge(user, project)
        assert merged["mode"]["mode"] == "test"

    def test_merge_bind_address_project_cannot_change(self):
        merger = ConfigMerger()
        user = {"ui": {"bind_address": "127.0.0.1"}}
        project = {"ui": {"bind_address": "0.0.0.0"}}
        merged = merger.merge(user, project)
        assert merged["ui"]["bind_address"] == "127.0.0.1"

    def test_merge_web_port_cli_override(self):
        merger = ConfigMerger()
        merged = merger.merge(
            {"ui": {"web_port": 8080, "bind_address": "127.0.0.1"}},
            {},
            cli_overrides={"ui.web_port": "3000"}
        )
        assert merged["ui"]["web_port"] == "3000"
        assert merged["ui"]["bind_address"] == "127.0.0.1"

    def test_merge_empty_user_uses_project(self):
        merger = ConfigMerger()
        merged = merger.merge({}, {"workspace": {"project_root": "/project"}})
        assert merged["workspace"]["project_root"] == "/project"

    def test_merge_empty_project_uses_user(self):
        merger = ConfigMerger()
        merged = merger.merge({"workspace": {"project_root": "/user"}}, {})
        assert merged["workspace"]["project_root"] == "/user"

    def test_merge_does_not_modify_inputs(self):
        merger = ConfigMerger()
        user = {"loop": {"max_steps": 50}}
        project = {"loop": {"max_steps": 30}}
        user_copy = {"loop": {"max_steps": 50}}
        project_copy = {"loop": {"max_steps": 30}}
        merger.merge(user, project)
        assert user == user_copy
        assert project == project_copy

    def test_merge_same_input_same_output(self):
        merger = ConfigMerger()
        user = {"loop": {"max_steps": 50}}
        project = {"loop": {"max_steps": 30}}
        result1 = merger.merge(user, project)
        result2 = merger.merge(user, project)
        assert result1 == result2