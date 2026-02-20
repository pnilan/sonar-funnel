from __future__ import annotations

import logging
import os

from airbyte_agent_slack import SlackConnector
from airbyte_agent_slack.models import SlackTokenAuthenticationAuthConfig

from sonar_funnel.models import IssueAnalysis, PylonIssueBundle
from sonar_funnel.retry import with_retry

logger = logging.getLogger(__name__)


def get_slack_connector() -> tuple[SlackConnector, str]:
    """Create a SlackConnector and return it with the target channel ID."""
    api_token = os.environ.get("SLACK_API_TOKEN")
    if not api_token:
        raise SystemExit("Error: SLACK_API_TOKEN environment variable must be set.")

    channel_id = os.environ.get("SLACK_CHANNEL_ID")
    if not channel_id:
        raise SystemExit("Error: SLACK_CHANNEL_ID environment variable must be set.")

    logger.info("Creating Slack connector (local mode)")
    connector = SlackConnector(
        auth_config=SlackTokenAuthenticationAuthConfig(api_token=api_token),
    )
    return connector, channel_id


def format_slack_report(
    results: list[tuple[PylonIssueBundle, IssueAnalysis]],
) -> str:
    """Build a single mrkdwn-formatted summary message from analyzed issues."""
    lines: list[str] = []
    lines.append(f":mag: *Sonar Funnel Report* — {len(results)} issue(s) analyzed\n")

    for bundle, analysis in results:
        connector_label = (
            f" [{analysis.affected_connector_or_service}]"
            if analysis.affected_connector_or_service
            else ""
        )
        flag = "CONNECTOR" if analysis.is_airbyte_connector_issue else "other"
        issue_ref = f"#{bundle.issue_number}" if bundle.issue_number else bundle.issue_id

        lines.append(f"*{issue_ref} — {bundle.title}*")
        lines.append(f">  Classification: `{flag}`{connector_label}")
        lines.append(f">  Severity: `{analysis.severity}`")
        lines.append(f">  Area: {analysis.impacted_area}")
        lines.append(f">  Summary: {analysis.problem_summary}")
        lines.append("")

    return "\n".join(lines)


async def post_report(
    connector: SlackConnector,
    channel_id: str,
    text: str,
) -> None:
    """Post a message to a Slack channel with rate-limit retry handling."""
    logger.info("Posting report to Slack channel %s", channel_id)
    await with_retry(connector.messages.create, channel=channel_id, text=text)
