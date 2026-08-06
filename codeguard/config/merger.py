from copy import deepcopy


class ConfigMerger:
    """Merges user-level, project-level, and CLI configs per SPEC §3.8 rules.

    Priority: defaults → user config → project config → CLI flags.

    Merge rules per field:
    - intersection: enabled_tools, allowed_types
    - union: disabled_tools, additional_protected_paths, excluded_paths,
      required_sensors
    - stricter (min): max_steps, max_llm_calls, max_repair_attempts,
      session_timeout, tool_timeout, no_progress_threshold, token_budget,
      cost_budget, max_output_tokens, request_timeout, timeout_per_sensor,
      output_limit, max_records, top_k, context_budget
    - user_override: project_root, provider, model, credential_profile,
      enabled, mode, bind_address, cli_timeout
    - project_only_shortens (min): approval_timeout
    - sensor_order: append + dedup
    - per_tool_timeouts: per-tool stricter (min)
    """

    _INTERSECTION = {
        "tools.enabled_tools",
        "memory.allowed_types",
    }

    _UNION = {
        "tools.disabled_tools",
        "workspace.additional_protected_paths",
        "workspace.excluded_paths",
        "sensors.required_sensors",
    }

    _STRICTER = {
        "loop.max_steps", "loop.max_llm_calls", "loop.max_repair_attempts",
        "loop.session_timeout", "loop.tool_timeout", "loop.no_progress_threshold",
        "loop.token_budget", "loop.cost_budget",
        "llm.max_output_tokens", "llm.request_timeout",
        "sensors.timeout_per_sensor", "sensors.output_limit",
        "memory.max_records", "memory.top_k", "memory.context_budget",
    }

    _USER_OVERRIDE = {
        "workspace.project_root",
        "llm.provider", "llm.model", "llm.credential_profile",
        "memory.enabled",
        "mode.mode",
        "ui.bind_address",
        "approval.cli_timeout",
    }

    _PROJECT_ONLY_SHORTENS = {
        "ui.approval_timeout",
    }

    def merge(self, user_config: dict, project_config: dict,
              cli_overrides: dict | None = None) -> dict:
        user_config = deepcopy(user_config)
        project_config = deepcopy(project_config)

        merged = {}
        all_sections = set(user_config.keys()) | set(project_config.keys())

        for section in all_sections:
            merged[section] = {}
            user_section = user_config.get(section, {})
            project_section = project_config.get(section, {})
            all_fields = set(user_section.keys()) | set(project_section.keys())

            for field in all_fields:
                key = f"{section}.{field}"
                user_val = user_section.get(field)
                project_val = project_section.get(field)

                if key == "sensors.sensor_order":
                    merged[section][field] = self._merge_sensor_order(
                        user_val, project_val)
                elif key == "tools.per_tool_timeouts":
                    merged[section][field] = self._merge_per_tool_timeouts(
                        user_val, project_val)
                elif key in self._INTERSECTION:
                    merged[section][field] = self._merge_intersection(
                        user_val, project_val)
                elif key in self._UNION:
                    merged[section][field] = self._merge_union(
                        user_val, project_val)
                elif key in self._STRICTER:
                    merged[section][field] = self._merge_stricter(
                        user_val, project_val)
                elif key in self._PROJECT_ONLY_SHORTENS:
                    merged[section][field] = self._merge_stricter(
                        user_val, project_val)
                elif key in self._USER_OVERRIDE:
                    merged[section][field] = self._merge_user_override(
                        user_val, project_val)
                else:
                    merged[section][field] = self._merge_override(
                        user_val, project_val)

        if cli_overrides:
            for dotted_key, value in cli_overrides.items():
                parts = dotted_key.split(".", 1)
                section, field = parts[0], parts[1]
                if section not in merged:
                    merged[section] = {}
                merged[section][field] = value

        return merged

    def _merge_intersection(self, user_val, project_val):
        if user_val is None:
            return project_val or []
        if project_val is None:
            return user_val or []
        user_set = set(user_val)
        proj_set = set(project_val)
        return [v for v in user_val if v in proj_set]

    def _merge_union(self, user_val, project_val):
        if user_val is None:
            return project_val or []
        if project_val is None:
            return user_val or []
        seen = set()
        result = []
        for v in user_val + project_val:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result

    def _merge_stricter(self, user_val, project_val):
        if user_val is None:
            return project_val
        if project_val is None:
            return user_val
        return min(user_val, project_val)

    def _merge_user_override(self, user_val, project_val):
        return user_val if user_val is not None else project_val

    def _merge_override(self, user_val, project_val):
        return project_val if project_val is not None else user_val

    def _merge_sensor_order(self, user_val, project_val):
        user_list = user_val or []
        proj_list = project_val or []
        seen = set(user_list)
        result = list(user_list)
        for v in proj_list:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result

    def _merge_per_tool_timeouts(self, user_val, project_val):
        user_dict = user_val or {}
        proj_dict = project_val or {}
        all_tools = set(user_dict.keys()) | set(proj_dict.keys())
        result = {}
        for tool in all_tools:
            u = user_dict.get(tool)
            p = proj_dict.get(tool)
            if u is not None and p is not None:
                result[tool] = min(u, p)
            elif u is not None:
                result[tool] = u
            elif p is not None:
                result[tool] = p
        return result