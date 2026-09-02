"""Parser and validator for structured model decisions.

Extracts, validates, and normalizes model outputs into deterministic ModelDecision
objects. Rejects any untrusted model attempt to declare permissions, roles,
or workspace identities.
"""
import json
import logging
import re
from typing import Any

from forge_api.domain.agent import ModelDecision, ModelDecisionType
from forge_api.domain.errors import ValidationError
from forge_api.domain.llm import ChatResponse

logger = logging.getLogger(__name__)

# Keys strictly forbidden from being controlled by model output
_FORBIDDEN_MODEL_KEYS = frozenset({
    "authorized",
    "authorization",
    "approved",
    "approval",
    "role",
    "user_role",
    "workspace_id",
    "repository_id",
    "repo_root",
    "root",
    "permissions",
})


class ModelDecisionParser:
    """Parses and strictly validates model decisions using a dual strategy:

    1. Provider-level tool calling metadata if present.
    2. Deterministic JSON block parsing and validation as a fallback.
    """

    def parse(self, response: ChatResponse) -> ModelDecision:
        """Parse ChatResponse into a validated ModelDecision."""
        # 1. Check for native tool calling metadata
        if response.metadata and "tool_calls" in response.metadata:
            native_calls = response.metadata["tool_calls"]
            if isinstance(native_calls, list) and native_calls:
                call = native_calls[0]
                tool_name = call.get("name") or call.get("tool_name")
                raw_args = call.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        raw_args = json.loads(raw_args)
                    except Exception:
                        raw_args = {}
                if tool_name and isinstance(raw_args, dict):
                    self._sanitize_arguments(raw_args)
                    return ModelDecision(
                        type=ModelDecisionType.TOOL_CALL,
                        tool_name=tool_name,
                        arguments=raw_args,
                    )

        # 2. Parse text content
        content = (response.content or "").strip()
        if not content:
            raise ValidationError(
                "Model returned empty content without a structured decision.",
                code="malformed_model_decision",
            )

        payload = self._extract_json(content)
        return self._validate_payload(payload)

    def _extract_json(self, content: str) -> dict[str, Any]:
        """Extract a JSON object from text, checking markdown blocks and raw braces."""
        # Check markdown code block ```json ... ``` or ``` ... ```
        block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
        if block_match:
            try:
                return json.loads(block_match.group(1))
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f"Invalid JSON in model code block: {exc}",
                    code="malformed_model_decision",
                ) from None

        # Check raw braces
        brace_match = re.search(r"(\{[\s\S]*\})", content)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f"Malformed JSON in model output: {exc}",
                    code="malformed_model_decision",
                ) from None

        # Fallback: check if entire content is valid JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"Could not parse structured decision from model content: {exc}",
                code="malformed_model_decision",
            ) from None

    def _validate_payload(self, payload: Any) -> ModelDecision:
        """Validate parsed dictionary against the strict decision schema."""
        if not isinstance(payload, dict):
            raise ValidationError(
                "Model decision must be a JSON object.",
                code="invalid_model_decision",
            )

        decision_type_raw = payload.get("type")
        if not decision_type_raw or not isinstance(decision_type_raw, str):
            raise ValidationError(
                "Model decision must include a valid 'type' field ('tool_call' or 'complete').",
                code="invalid_model_decision",
            )

        try:
            decision_type = ModelDecisionType(decision_type_raw)
        except ValueError:
            raise ValidationError(
                f"Unsupported decision type: '{decision_type_raw}'. "
                "Must be 'tool_call' or 'complete'.",
                code="invalid_model_decision",
            ) from None


        if decision_type == ModelDecisionType.COMPLETE:
            reason = payload.get("reason", "")
            return ModelDecision(
                type=ModelDecisionType.COMPLETE,
                reason=str(reason) if reason else None,
            )

        if decision_type == ModelDecisionType.TOOL_CALL:
            tool_name = payload.get("tool_name")
            if not tool_name or not isinstance(tool_name, str) or not tool_name.strip():
                raise ValidationError(
                    "tool_call decision requires a non-empty string 'tool_name'.",
                    code="invalid_model_decision",
                )

            arguments = payload.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValidationError(
                    "'arguments' in tool_call decision must be a dictionary.",
                    code="invalid_model_decision",
                )

            self._sanitize_arguments(arguments)

            return ModelDecision(
                type=ModelDecisionType.TOOL_CALL,
                tool_name=tool_name.strip(),
                arguments=arguments,
            )

        raise ValidationError(
            f"Unhandled decision type '{decision_type}'.",
            code="invalid_model_decision",
        )

    def _sanitize_arguments(self, arguments: dict[str, Any]) -> None:
        """Scrub forbidden security fields that model might attempt to inject."""
        for forbidden in _FORBIDDEN_MODEL_KEYS:
            if forbidden in arguments:
                logger.warning(
                    "Scrubbed untrusted security argument '%s' from model tool call",
                    forbidden,
                )
                del arguments[forbidden]
