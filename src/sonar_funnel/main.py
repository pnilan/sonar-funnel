from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv

from sonar_funnel.agent import analyze_issue
from sonar_funnel.pylon_source import fetch_recent_issues, get_connector


async def run(days: int) -> None:
    connector = get_connector()

    print(f"Fetching Pylon issues from the last {days} day(s)...", file=sys.stderr)
    bundles = await fetch_recent_issues(connector, days_back=days)

    if not bundles:
        print("No issues found.", file=sys.stderr)
        return

    print(f"Found {len(bundles)} issue(s). Analyzing...\n", file=sys.stderr)

    for bundle in bundles:
        print(f"  Analyzing: {bundle.title}...", file=sys.stderr)
        analysis = await analyze_issue(bundle)

        connector_label = (
            f" [{analysis.affected_connector_or_service}]"
            if analysis.affected_connector_or_service
            else ""
        )
        flag = "CONNECTOR" if analysis.is_airbyte_connector_issue else "other"

        print(f"## #{bundle.issue_number or bundle.issue_id} — {bundle.title}")
        print(f"  Classification: {flag}{connector_label}")
        print(f"  Severity: {analysis.severity}")
        print(f"  Area: {analysis.impacted_area}")
        print(f"  Summary: {analysis.problem_summary}")
        print(f"  Reasoning: {analysis.reasoning}")
        print()


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

    asyncio.run(run(args.days))
