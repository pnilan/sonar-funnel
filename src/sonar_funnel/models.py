from __future__ import annotations

from pydantic import BaseModel, Field


class IssueAnalysis(BaseModel):
    """Agent output: structured classification of a Pylon support issue."""

    problem_summary: str = Field(description="Brief summary of the customer's problem")
    severity: str = Field(
        description="Estimated severity: critical, high, medium, or low"
    )
    impacted_area: str = Field(
        description="Area of the product affected (e.g. connectors, platform, cloud, docs)"
    )
    affected_connector_or_service: str | None = Field(
        default=None,
        description="Specific connector or service name if identifiable",
    )
    is_airbyte_connector_issue: bool = Field(
        description="Whether this is an issue with an Airbyte-maintained connector"
    )
    reasoning: str = Field(
        description="Brief explanation of the classification decision"
    )


class PylonIssueBundle(BaseModel):
    """Internal data container: a Pylon issue with its flattened message text."""

    issue_id: str
    issue_number: int | None = None
    title: str
    link: str | None = None
    state: str | None = None
    created_at: str | None = None
    tags: list[str] = Field(default_factory=list)
    message_text: str = Field(description="Concatenated message content for analysis")
