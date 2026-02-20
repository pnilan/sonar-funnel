from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv

from sonar_funnel.agent import analyze_issue
from sonar_funnel.models import IssueAnalysis, PylonIssueBundle
from sonar_funnel.pylon_source import fetch_recent_issues, get_connector
from sonar_funnel.slack_report import format_slack_report, get_slack_connector, post_report


async def run(days: int, *, dry_run: bool = False) -> None:
    connector = get_connector()

    slack_connector = None
    slack_channel_id = None
    if not dry_run:
        slack_connector, slack_channel_id = get_slack_connector()

    print(f"Fetching Pylon issues from the last {days} day(s)...", file=sys.stderr)
    bundles = await fetch_recent_issues(connector, days_back=days)

    if not bundles:
        print("No issues found.", file=sys.stderr)
        if slack_connector and slack_channel_id:
            await post_report(slack_connector, slack_channel_id, f"No new Pylon issues found in the last {days} day(s).")
            print("Report posted to Slack.", file=sys.stderr)
        return

    print(f"Found {len(bundles)} issue(s). Analyzing...\n", file=sys.stderr)

    results: list[tuple[PylonIssueBundle, IssueAnalysis]] = []

    for bundle in bundles:
        print(f"  Analyzing: {bundle.title}...", file=sys.stderr)
        analysis = await analyze_issue(bundle)
        results.append((bundle, analysis))

    for bundle, analysis in results:
        connector_label = (
            f" [{analysis.affected_connector_or_service}]"
            if analysis.affected_connector_or_service
            else ""
        )
        flag = "CONNECTOR" if analysis.is_airbyte_connector_issue else "other"

        print(f"## #{bundle.issue_number or bundle.issue_id} — {bundle.title}")
        if bundle.link:
            print(f"  Link: {bundle.link}")
        print(f"  Classification: {flag}{connector_label}")
        print(f"  Severity: {analysis.severity}")
        print(f"  Area: {analysis.impacted_area}")
        print(f"  Summary: {analysis.problem_summary}")
        print(f"  Reasoning: {analysis.reasoning}")
        print()

    if slack_connector and slack_channel_id:
        report_text = format_slack_report(results)
        await post_report(slack_connector, slack_channel_id, report_text)
        print("Report posted to Slack.", file=sys.stderr)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Triage Pylon support issues using AI classification.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back for issues (default: 7)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (includes HTTP requests)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Run the full flow including posting to Slack",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip posting to Slack (stdout output only)",
    )
    args = parser.parse_args()

    if args.debug:
        level = logging.DEBUG
    elif args.verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if not args.debug:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    asyncio.run(run(args.days, dry_run=args.dry_run))
