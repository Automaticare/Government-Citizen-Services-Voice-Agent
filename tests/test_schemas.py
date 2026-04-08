"""
Tests for system tool schemas.
"""

from agent.tools.schemas import (
    get_system_tool_configs,
    SYSTEM_TOOL_SCHEMAS,
)


class TestSystemToolSchemas:

    def test_deployable_system_tools(self):
        """Only tools without _deploy=False are returned."""
        tools = get_system_tool_configs()
        names = {t["name"] for t in tools}
        assert "language_detection" in names
        assert "end_call" in names
        # transfer_to_number excluded until Twilio configured
        assert "transfer_to_number" not in names

    def test_all_system_tools_in_registry(self):
        """All 3 system tools exist in the registry."""
        assert len(SYSTEM_TOOL_SCHEMAS) == 3
        assert "transfer_to_number" in SYSTEM_TOOL_SCHEMAS

    def test_system_tools_format(self):
        for tool in get_system_tool_configs():
            assert tool["type"] == "system"
            assert "name" in tool
            assert "params" in tool
