from codeguard.tool import ToolDefinition


class ToolRegistry:
    """Registry for tool definitions. Supports register, lookup, list."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition):
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' already registered")
        self._tools[definition.name] = definition

    def lookup(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())