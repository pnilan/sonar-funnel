from __future__ import annotations

from pydantic_ai import Agent

from sonar_funnel.models import IssueAnalysis, PylonIssueBundle

SYSTEM_PROMPT = (
    "You are an expert at triaging customer support issues for Airbyte, "
    "a data integration platform. Given a support issue and its messages, "
    "classify whether it is related to an Airbyte-maintained connector.\n"
    "\n"
    "Airbyte-maintained connectors are source and destination connectors "
    "that Airbyte builds and supports (e.g. source-postgres, destination-snowflake, "
    "source-shopify, destination-bigquery). Issues about these connectors typically "
    "involve sync failures, data quality problems, configuration errors, or missing "
    "features in a specific connector.\n"
    "\n"
    "Issues that are NOT connector issues include: billing questions, account access, "
    "platform/UI bugs, general how-to questions, feature requests for the platform, "
    "questions about Airbyte Cloud infrastructure, or issues with custom/community "
    "connectors.\n"
    "\n"
    "For severity, use:\n"
    "- critical: Production data pipeline down, data loss, or security issue\n"
    "- high: Significant functionality broken, blocking customer workflows\n"
    "- medium: Partial functionality issues, workarounds available\n"
    "- low: Minor issues, cosmetic problems, or general questions"
)


def _get_agent() -> Agent[None, IssueAnalysis]:
    return Agent(
        "anthropic:claude-sonnet-4-6",
        system_prompt=SYSTEM_PROMPT,
        output_type=IssueAnalysis,
    )


def _format_issue_for_analysis(bundle: PylonIssueBundle) -> str:
    """Format a PylonIssueBundle into a text prompt for the agent."""
    parts = [f"Issue: {bundle.title}"]

    if bundle.issue_number:
        parts.append(f"Number: #{bundle.issue_number}")
    if bundle.state:
        parts.append(f"State: {bundle.state}")
    if bundle.created_at:
        parts.append(f"Created: {bundle.created_at}")
    if bundle.tags:
        parts.append(f"Tags: {', '.join(bundle.tags)}")

    if bundle.message_text:
        parts.append(f"\n## Messages\n{bundle.message_text}")

    return "\n".join(parts)


async def analyze_issue(bundle: PylonIssueBundle) -> IssueAnalysis:
    """Classify a single Pylon issue using the AI agent."""
    agent = _get_agent()
    prompt = _format_issue_for_analysis(bundle)
    result = await agent.run(prompt)
    return result.output
