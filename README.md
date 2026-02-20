# sonar-funnel

Automated triage of customer support issues. Fetches recent issues and their messages, uses an AI agent (Claude) to classify each one, and posts a summary report to Slack.

Built with [Airbyte Agent Connectors](https://github.com/airbytehq/airbyte-agent-connectors) for API integrations:
- [`airbyte-agent-pylon`](https://pypi.org/project/airbyte-agent-pylon/) — fetches support issues and messages from Pylon
- [`airbyte-agent-slack`](https://pypi.org/project/airbyte-agent-slack/) — posts reports to Slack

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
# Fill in your keys in .env
```

### Environment variables

| Variable | Description |
|---|---|
| `PYLON_API_TOKEN` | Pylon API token (admin user) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `SLACK_API_TOKEN` | Slack bot token (requires `chat:write` scope) |
| `SLACK_CHANNEL_ID` | Slack channel ID to post the report to |

## Usage

Either `--execute` or `--dry-run` must be provided:

```bash
# Full run: analyze and post to Slack
uv run sonar-funnel --execute

# Dry run: analyze and print to stdout only (no Slack)
uv run sonar-funnel --dry-run

# Look back 1 day
uv run sonar-funnel --days 1 --execute

# Verbose logging (shows fetch/pagination progress)
uv run sonar-funnel --days 3 -v --execute

# Debug logging (includes HTTP requests)
uv run sonar-funnel --days 1 --debug --dry-run
```

### Output

Results are always printed to stdout. With `--execute`, a summary is also posted to the configured Slack channel (including links to the original issues). With `--dry-run`, only stdout output is produced. Status and progress messages go to stderr, so you can pipe results cleanly.

```
## #123 — Sync failing after upgrade
  Link: https://support.example.com/issues/123
  Classification: CONNECTOR [source-postgres]
  Severity: high
  Area: connectors
  Summary: Customer reports incremental sync fails after upgrading
  Reasoning: The issue describes a failure in a specific connector's sync process

## #456 — How do I invite team members?
  Link: https://support.example.com/issues/456
  Classification: other
  Severity: low
  Area: platform
  Summary: Customer asking how to add users to their workspace
  Reasoning: This is a general platform question, not related to any connector
```

Each issue includes:

- **Link** — URL to the original issue (when available)
- **Classification** — issue category
- **Severity** — `critical`, `high`, `medium`, or `low`
- **Area** — Part of the product affected
- **Affected connector/service** — Specific name, if identifiable
- **Summary** — Brief description of the problem
- **Reasoning** — Explanation of the classification decision

## Rate limiting

API calls to Pylon and Slack include automatic retry with exponential backoff when rate-limited (HTTP 429). Retries start at 5 seconds, double each attempt (capped at 2 minutes), and respect the `Retry-After` header when provided. The process will keep retrying indefinitely until it succeeds or the total runtime exceeds 1 hour.

## Project structure

```
src/sonar_funnel/
├── main.py           # CLI entry point and orchestration
├── pylon_source.py   # Pylon connector and issue/message fetching
├── slack_report.py   # Slack connector setup, report formatting, and posting
├── retry.py          # Shared retry logic with exponential backoff
├── agent.py          # PydanticAI classification agent
└── models.py         # Shared Pydantic models
```
