"""Unit tests for agent observation bounding, redaction, and compaction."""

from forge_api.application.agent.context_adapter import (
    AgentContextAdapter,
)


class TestAgentContextAdapter:
    def test_observation_tagging_as_untrusted(self) -> None:
        adapter = AgentContextAdapter()
        obs = adapter.format_observation(
            tool_name="repo.read",
            output="def hello(): pass",
            is_error=False,
        )
        assert '<observation untrusted="true" tool="repo.read" status="success">' in obs
        assert "</observation>" in obs
        assert "def hello(): pass" in obs

    def test_observation_error_status_tagging(self) -> None:
        adapter = AgentContextAdapter()
        obs = adapter.format_observation(
            tool_name="file.create",
            output="Permission denied",
            is_error=True,
        )
        assert 'status="error"' in obs
        assert "Permission denied" in obs

    def test_observation_bounding_at_8192_bytes(self) -> None:
        adapter = AgentContextAdapter(max_observation_bytes=100)
        large_output = "A" * 500
        obs = adapter.format_observation(
            tool_name="repo.search",
            output=large_output,
            is_error=False,
        )
        assert "exceeded 100 byte limit" in obs
        # Observation content inside tags is truncated
        assert len(large_output) > len(obs)

    def test_observation_redacts_secrets(self) -> None:
        adapter = AgentContextAdapter()
        raw = "Fetched key: sk-1234567890abcdef1234567890abcdef with bearer token"
        obs = adapter.format_observation(
            tool_name="repo.read",
            output=raw,
            is_error=False,
        )
        assert "sk-1234567890abcdef" not in obs
        assert "[REDACTED_API_KEY]" in obs

    def test_sliding_window_compaction(self) -> None:
        adapter = AgentContextAdapter(max_full_observations=2)
        observations = [
            (
                '<observation untrusted="true" tool="repo.list_files" status="success">\n'
                "files: 10\n"
                "</observation>"
            ),
            (
                '<observation untrusted="true" tool="repo.read" status="success">\n'
                "content: abc\n"
                "</observation>"
            ),
            (
                '<observation untrusted="true" tool="file.create" status="success">\n'
                "created\n"
                "</observation>"
            ),
            (
                '<observation untrusted="true" tool="git.commit" status="success">\n'
                "committed\n"
                "</observation>"
            ),
        ]


        compacted = adapter.compact_history(observations)
        assert len(compacted) == 4

        # First two should be compacted into single-line summaries
        assert "[Compacted previous step: repo.list_files completed with success]" in compacted[0]
        assert "[Compacted previous step: repo.read completed with success]" in compacted[1]

        # Last two remain in full
        assert observations[2] == compacted[2]
        assert observations[3] == compacted[3]
