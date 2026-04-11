"""
Tests for ArchitectureAnalyzer._parse_json and _repair_json.
No LLM API calls - all responses are mocked strings.
"""

import pytest
from src.analysis.analyzer import ArchitectureAnalyzer
from src.analysis.llm_client import LLMClient, LLMConfig


def make_analyzer() -> ArchitectureAnalyzer:
    # Dummy config - LLM is never called in these tests
    config = LLMConfig(provider="openai", api_key="test-key", model="gpt-4o")
    client = LLMClient(config=config)
    return ArchitectureAnalyzer(client=client, language="pt")


VALID_JSON = """{
  "project_name": "TestProject",
  "description": "A test project.",
  "tech_stack": ["Python", "FastAPI"],
  "layers": [
    {
      "id": "layer_1",
      "name": "Ingestion",
      "description": "Reads data",
      "color": "#2d6a4f",
      "components": [{"name": "Scanner", "description": "Scans files", "tech": "Python", "type": "process"}],
      "connections_to": ["layer_2"]
    }
  ],
  "good_practices": ["Uses dataclasses"],
  "improvement_points": ["Add tests"],
  "validation_questions": ["Is the ingestion layer correct?"]
}"""


class TestParseJsonDirect:
    def test_parses_clean_json(self):
        az = make_analyzer()
        result = az._parse_json(VALID_JSON)
        assert result["project_name"] == "TestProject"
        assert len(result["layers"]) == 1

    def test_strips_json_markdown_fence(self):
        az = make_analyzer()
        wrapped = f"```json\n{VALID_JSON}\n```"
        result = az._parse_json(wrapped)
        assert result["project_name"] == "TestProject"

    def test_strips_plain_markdown_fence(self):
        az = make_analyzer()
        wrapped = f"```\n{VALID_JSON}\n```"
        result = az._parse_json(wrapped)
        assert result["project_name"] == "TestProject"

    def test_extracts_json_with_prose_before(self):
        az = make_analyzer()
        text = f"Here is the analysis:\n{VALID_JSON}\nHope this helps!"
        result = az._parse_json(text)
        assert result["project_name"] == "TestProject"

    def test_raises_on_completely_invalid(self):
        az = make_analyzer()
        with pytest.raises(ValueError, match="did not return valid JSON"):
            az._parse_json("This is not JSON at all, sorry.")


class TestRepairJson:
    def test_repairs_truncated_layers_array(self):
        az = make_analyzer()
        # Simulate JSON truncated mid-way through layers list
        truncated = """{
  "project_name": "Truncated",
  "description": "Cut off",
  "tech_stack": ["Python"],
  "layers": [
    {
      "id": "layer_1",
      "name": "Ingestion"""
        result = az._repair_json(truncated)
        # Should at minimum parse without exception and have project_name
        assert result["project_name"] == "Truncated"

    def test_repairs_missing_closing_braces(self):
        az = make_analyzer()
        partial = '{"project_name": "X", "layers": [{"id": "l1", "name": "Layer 1"'
        result = az._repair_json(partial)
        assert result["project_name"] == "X"

    def test_complete_object_returned_as_is(self):
        az = make_analyzer()
        data = '{"project_name": "Complete", "tech_stack": ["Go"]}'
        result = az._repair_json(data)
        assert result["project_name"] == "Complete"
        assert result["tech_stack"] == ["Go"]

    def test_raises_when_no_object_found(self):
        az = make_analyzer()
        with pytest.raises(ValueError, match="No JSON object found"):
            az._repair_json("no curly brace here at all")


class TestBuildResult:
    def test_builds_result_from_full_data(self):
        import json
        az = make_analyzer()
        data = json.loads(VALID_JSON)
        result = az._build_result(data)
        assert result.project_name == "TestProject"
        assert result.description == "A test project."
        assert result.tech_stack == ["Python", "FastAPI"]
        assert len(result.layers) == 1
        assert result.good_practices == ["Uses dataclasses"]
        assert result.improvement_points == ["Add tests"]
        assert result.validation_questions == ["Is the ingestion layer correct?"]

    def test_builds_result_with_missing_fields(self):
        az = make_analyzer()
        # Should not raise, should use defaults
        result = az._build_result({})
        assert result.project_name == "Unknown Project"
        assert result.tech_stack == []
        assert result.layers == []
