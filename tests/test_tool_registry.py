import pytest
from codeguard.tool import ToolDefinition
from codeguard.tool.registry import ToolRegistry


def test_register_and_lookup():
    registry = ToolRegistry()
    td = ToolDefinition(name="read_file", description="Read file", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    registry.register(td)
    assert registry.lookup("read_file") is td


def test_register_duplicate_raises():
    registry = ToolRegistry()
    td = ToolDefinition(name="read_file", description="", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    registry.register(td)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(td)


def test_lookup_unknown_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="Unknown tool"):
        registry.lookup("nonexistent")


def test_list_tools():
    registry = ToolRegistry()
    td1 = ToolDefinition(name="read_file", description="Read", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=False, default_risk="ALLOW", supported_modes=["TEST"])
    td2 = ToolDefinition(name="write_file", description="Write", parameters_schema={}, handler=lambda: None, category="FILE", side_effect=True, default_risk="REQUEST_APPROVAL", supported_modes=["TEST"])
    registry.register(td1)
    registry.register(td2)
    names = [t.name for t in registry.list_tools()]
    assert "read_file" in names
    assert "write_file" in names
    assert len(names) == 2