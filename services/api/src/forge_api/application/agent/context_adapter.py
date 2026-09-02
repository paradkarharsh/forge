"""Observation bounding, secret redaction, and compaction for agent context.

Guarantees that all tool outputs and repository data remain bounded, structurally
tagged as untrusted, and prevented from growing unboundedly across agent steps.
"""
import logging
import re
from typing import Any

from forge_api.domain.tool import redact_secrets

logger = logging.getLogger(__name__)

MAX_OBSERVATION_BYTES = 8_192


class AgentContextAdapter:
    """Manages the lifecycle and bounds of agent observations in context."""

    def __init__(
        self,
        *,
        max_observation_bytes: int = MAX_OBSERVATION_BYTES,
        max_full_observations: int = 5,
    ) -> None:
        self._max_observation_bytes = max_observation_bytes
        self._max_full_observations = max_full_observations

    def format_observation(
        self,
        *,
        tool_name: str,
        output: str,
        is_error: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Format a tool result into a bounded, redacted, and untrusted observation tag."""
        raw_text = output or ""
        # 1. Scrub credentials and secrets
        redacted = redact_secrets(raw_text)

        # 2. Bound observation to max_observation_bytes
        raw_bytes = redacted.encode("utf-8")
        if len(raw_bytes) > self._max_observation_bytes:
            truncated = raw_bytes[: self._max_observation_bytes].decode(
                "utf-8", errors="ignore"
            )
            bounded_text = (
                f"{truncated}\n[... Observation truncated: exceeded "
                f"{self._max_observation_bytes} byte limit ...]"
            )
        else:
            bounded_text = redacted

        status = "error" if is_error else "success"
        # 3. Structurally wrap as untrusted external data
        return (
            f'<observation untrusted="true" tool="{tool_name}" status="{status}">\n'
            f"{bounded_text}\n"
            f"</observation>"
        )

    def compact_history(self, observations: list[str]) -> list[str]:
        """Apply sliding-window compaction to prevent unbounded context growth."""
        if len(observations) <= self._max_full_observations:
            return list(observations)

        split_index = len(observations) - self._max_full_observations
        compacted: list[str] = []

        # Summarize older observations
        for obs in observations[:split_index]:
            tool_match = re.search(r'tool="([^"]+)"', obs)
            status_match = re.search(r'status="([^"]+)"', obs)
            tool_name = tool_match.group(1) if tool_match else "unknown"
            status = status_match.group(1) if status_match else "unknown"
            compacted.append(
                f"[Compacted previous step: {tool_name} completed with {status}]"
            )

        # Keep recent observations in full
        compacted.extend(observations[split_index:])
        return compacted
