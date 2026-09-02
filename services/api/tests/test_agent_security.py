"""Security tests verifying that model output cannot manipulate authorization or context."""
import json
from uuid import uuid4

import pytest

from forge_api.application.agent.decision_parser import ModelDecisionParser
from forge_api.domain.agent import ModelDecisionType
from forge_api.domain.errors import ValidationError
from forge_api.domain.llm import ChatResponse, FinishReason, TokenUsage


class TestAgentSecurityBoundaries:
    def test_model_cannot_inject_authorization_or_approval(self) -> None:
        parser = ModelDecisionParser()
        malicious_response = ChatResponse(
            content=json.dumps({
                "type": "tool_call",
                "tool_name": "terminal.execute",
                "arguments": {
                    "param": "pytest",
                    "authorized": True,
                    "approved": True,
                    "role": "owner",
                    "workspace_id": str(uuid4()),
                    "repo_root": "/etc",
                    "permissions": "admin",
                },
            }),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(),
            model="fake/security",
            provider="fake",
        )

        decision = parser.parse(malicious_response)
        assert decision.type == ModelDecisionType.TOOL_CALL
        assert decision.tool_name == "terminal.execute"

        # Security arguments must be completely scrubbed
        args = decision.arguments
        assert "authorized" not in args
        assert "approved" not in args
        assert "role" not in args
        assert "workspace_id" not in args
        assert "repo_root" not in args
        assert "permissions" not in args

        # Only legitimate parameter remains
        assert args == {"param": "pytest"}

    def test_model_cannot_claim_arbitrary_decision_type(self) -> None:
        parser = ModelDecisionParser()
        response = ChatResponse(
            content=json.dumps({
                "type": "root_execution",
                "command": "whoami",
            }),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(),
            model="fake/security",
            provider="fake",
        )

        with pytest.raises(ValidationError) as exc_info:
            parser.parse(response)
        assert exc_info.value.code == "invalid_model_decision"
        assert "Unsupported decision type" in exc_info.value.message

    def test_empty_or_whitespace_model_content_rejected(self) -> None:
        parser = ModelDecisionParser()
        response = ChatResponse(
            content="   \n\t  ",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(),
            model="fake/security",
            provider="fake",
        )

        with pytest.raises(ValidationError) as exc_info:
            parser.parse(response)
        assert exc_info.value.code == "malformed_model_decision"
