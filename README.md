# sonar-funnel

Automated triage of customer support issues from Pylon. Fetches recent issues and their messages, then uses an AI agent (Claude) to classify each as connector-related or not, extracting structured analysis.

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

## Usage

```bash
# Analyze issues from the last 7 days (default)
uv run sonar-funnel

# Look back 1 day
uv run sonar-funnel --days 1

# Verbose logging (shows fetch/pagination progress)
uv run sonar-funnel --days 3 -v

# Debug logging (includes HTTP requests)
uv run sonar-funnel --days 1 --debug
```

### Output

Results are printed to stdout. Status and progress messages go to stderr, so you can pipe results cleanly.

```
## #123 — Sync failing for source-postgres
  Classification: CONNECTOR [source-postgres]
  Severity: high
  Area: connectors
  Summary: Customer reports incremental sync fails with CDC enabled
  Reasoning: The issue describes a failure in the source-postgres connector's CDC replication

## #456 — How do I invite team members?
  Classification: other
  Severity: low
  Area: platform
  Summary: Customer asking how to add users to their workspace
  Reasoning: This is a general platform question, not related to any connector
```

Each issue is classified with:

- **Classification** — `CONNECTOR` (Airbyte-maintained connector issue) or `other`
- **Severity** — `critical`, `high`, `medium`, or `low`
- **Area** — Part of the product affected (connectors, platform, cloud, docs, etc.)
- **Affected connector** — Specific connector name, if identifiable
- **Summary** — Brief description of the problem
- **Reasoning** — Explanation of the classification decision

## Rate limiting

API calls to Pylon include automatic retry with exponential backoff when rate-limited (HTTP 429). Retries start at 5 seconds, double each attempt (capped at 2 minutes), and respect the `Retry-After` header when provided. The process will keep retrying indefinitely until it succeeds or the total runtime exceeds 1 hour.

## Project structure

```
src/sonar_funnel/
├── main.py           # CLI entry point and orchestration
├── pylon_source.py   # Pylon connector, issue/message fetching, retry logic
├── agent.py          # PydanticAI classification agent
└── models.py         # Shared Pydantic models
```
