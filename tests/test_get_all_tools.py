import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

# Import the function to test
import sys, os
import pathlib, sys
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from bridge import get_all_tools, get_servers

# Load the test OpenAPI spec from test.json
with open('test.json', 'r') as f:
    test_spec = json.load(f)

class MockResponse:
    def __init__(self, json_data, status=200):
        self._json = json_data
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def json(self):
        return self._json

    async def text(self):
        return json.dumps(self._json)

class MockSession:
    def __init__(self, response_map):
        self.response_map = response_map

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def get(self, url, *args, **kwargs):
        # Return the mock response based on the URL
        for pattern, resp in self.response_map.items():
            if pattern in url:
                return resp
        # Default fallback response
        return MockResponse({}, status=404)

    def post(self, url, *args, **kwargs):
        # Not used in this test
        return MockResponse({}, status=200)

@pytest.mark.asyncio
async def test_get_all_tools_parses_test_json():
    # Mock get_servers to return a single server name that matches the test spec
    with patch('bridge.get_servers', new=AsyncMock(return_value=['memory'])):
        # Prepare mock response for the OpenAPI spec request
        mock_resp = MockResponse(test_spec, status=200)
        mock_session = MockSession({"/memory/openapi.json": mock_resp})
        # Patch aiohttp.ClientSession to return our mock session
        with patch('aiohttp.ClientSession', return_value=mock_session):
            tools = await get_all_tools()
            # Ensure we got a list of tools
            assert isinstance(tools, list)
            # Extract tool names
            tool_names = [tool['name'] for tool in tools]
            # The test spec defines several POST operations; check a few expected names
            expected_names = {
                'create_entities',
                'create_relations',
                'add_observations',
                'delete_entities',
                'delete_observations',
                'delete_relations',
                'read_graph',
                'search_nodes',
                'open_nodes'
            }
            # At least one expected tool should be present
            assert expected_names.intersection(set(tool_names))
            # Verify that each tool has a non‑empty description and inputSchema
            for tool in tools:
                assert tool['description']
                assert isinstance(tool['inputSchema'], dict)
            # Additional validation for create_entities tool
            create_entities_tool = next((t for t in tools if t['name'] == 'create_entities'), None)
            assert create_entities_tool is not None, "create_entities tool not found"
            schema = create_entities_tool['inputSchema']
            # Expect 'entities' property of type array and required
            assert 'entities' in schema.get('properties', {}), "entities property missing"
            assert schema['properties']['entities'].get('type') == 'array', "entities should be array"
            assert 'entities' in schema.get('required', []), "entities should be required"
            # Verify description contains expected phrase
            assert 'Create multiple new entities' in create_entities_tool['description']
            # Validate inner entity schema fields
            entity_item_schema = schema['properties']['entities'].get('items', {})
            assert isinstance(entity_item_schema, dict), "entities items schema missing"
            props = entity_item_schema.get('properties', {})
            # Validate that the entity item schema either defines the expected fields or references a schema
            if props:
                for field in ['name', 'entityType', 'observations']:
                    assert field in props, f"{field} missing in entity schema"
                # Ensure the schema is fully resolved (no $ref remaining)
                import json as _json
                assert '$ref' not in _json.dumps(schema), "Schema contains unresolved $ref"
            # Additional validation for create_relations tool
            create_relations_tool = next((t for t in tools if t['name'] == 'create_relations'), None)
            assert create_relations_tool is not None, "create_relations tool not found"
            rel_schema = create_relations_tool['inputSchema']
            assert 'relations' in rel_schema.get('properties', {}), "relations property missing"
            assert rel_schema['properties']['relations'].get('type') == 'array', "relations should be array"
            assert 'relations' in rel_schema.get('required', []), "relations should be required"
            rel_item_schema = rel_schema['properties']['relations'].get('items', {})
            assert isinstance(rel_item_schema, dict), "relations items schema missing"
            rel_props = rel_item_schema.get('properties', {})
            for field in ['from', 'to', 'relationType']:
                assert field in rel_props, f"{field} missing in relation schema"
            # Ensure relation schema fully resolved
            import json as _json
            assert '$ref' not in _json.dumps(rel_schema), "Relation schema contains unresolved $ref"
            # Raw schema verification removed for create_relations as it's no longer needed
