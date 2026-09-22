# Gmail Interview Scheduler MCP

Course: ENMGT 4405

Assignment: Assignment 4 — Calling Services: Model Context Protocol

A local Python MCP server that reads interview invitations from Gmail, previews
this week's schedule in Claude Desktop, and writes only user-confirmed
interviews to a Notion timeline.

## Assignment scope

- Domain: Personal Productivity
- MCP endpoints: two tools and one prompt
- Authentication: read-only Gmail OAuth plus a Notion integration token
- Best practices: local rate limiting and safe error disclosure
- Transport: local `stdio`
- Privacy: email bodies and OAuth tokens stay on the local computer

### Tools

- `list_weekly_interview_invites`: reads Gmail and returns calendar-backed
  interviews plus possible invitation emails that need manual review.
- `add_interview_to_notion`: writes one confirmed interview to Notion and
  prevents duplicate rows using the Gmail message ID.

### Prompt

- `weekly_interview_schedule_review`: guides Claude through preview,
  confirmation, syncing, conflict review, and interview preparation.

## 1. Open the project in VS Code

Open this folder, not its parent folder:

```text
gmail-interview-scheduler-mcp
```

Install the recommended Python and Pylance extensions when VS Code asks.

## 2. Create the virtual environment

Use Python 3.11 or newer. This checkout has been verified with Python 3.13.

```bash
uv venv --seed
source .venv/bin/activate
uv pip install -r requirements.txt
```

If `uv` is unavailable:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Confirm that VS Code selected `.venv/bin/python` as the interpreter.

## 3. Create the Notion interview schedule

Create a Notion database with these exact property names and types:

| Property | Notion type |
|---|---|
| Interview | Title |
| Company | Text |
| Role | Text |
| Time | Date |
| Status | Select |
| Location | Text |
| Meeting URL | URL |
| Recruiter | Text |
| Gmail URL | URL |
| Gmail Message ID | Text |
| Notes | Text |

Add a `Scheduled` option to the Status property. A Notion calendar or timeline
view can use the `Time` property.

Create an internal Notion integration, give it read and insert-content
capabilities, and connect the database to it. In **Manage data sources**, copy
the data source ID (not the database ID).

## 4. Authorize Gmail with read-only access

This server requests only the official `gmail.readonly` scope. It cannot send,
delete, archive, label, or modify email.

1. In Google Cloud, enable the Gmail API.
2. Configure the Google Auth consent screen. For a personal Gmail account,
   choose **External** and add your own address as a test user.
3. Create an OAuth client with application type **Desktop app**.
4. Download the JSON file and save it in this project as `credentials.json`.
5. With the virtual environment active, run:

```bash
python authorize_gmail.py
```

The browser asks you to grant read-only Gmail permission. The script stores the
local refresh token in `token.json`. Both OAuth files are ignored by Git.

## 5. Configure Notion and local paths

Copy the example file:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
NOTION_TOKEN=secret_your_real_notion_token
NOTION_INTERVIEW_DATA_SOURCE_ID=your_interview_data_source_id
GMAIL_TOKEN_PATH=token.json
MCP_RATE_LIMIT_CALLS=5
MCP_RATE_LIMIT_WINDOW_SECONDS=60
```

The application reads `.env` directly with `pathlib.Path` and
`dotenv_values`. It never copies credentials into process environment
variables. `.env`, `credentials.json`, and `token.json` must never be
committed.

## 6. Run automated tests

The tests use fakes and do not access Gmail or Notion:

```bash
python -m pytest
```

Expected result: all tests pass.

## 7. Inspect the MCP server

```bash
mcp dev server.py
```

The Inspector should show:

- Tools: `list_weekly_interview_invites`, `add_interview_to_notion`
- Prompt: `weekly_interview_schedule_review`

Running `python server.py` directly waits silently for a stdio MCP client.

## 8. Configure Claude Desktop

Merge the included `claude_desktop_config.json` server entry into the existing
Claude Desktop configuration, then restart Claude Desktop. Do not put Gmail or
Notion credentials in the Claude configuration; the server loads local files.

On macOS, Claude's configuration is normally located at:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

If the repository moves, update the two absolute paths in the included config.

## 9. Safe usage flow

Ask Claude:

```text
Use weekly_interview_schedule_review to find my interviews for this week.
Show me what you found before writing anything to Notion.
```

Calendar-backed invitations are parsed from iCalendar data. Keyword-matched
emails without an attached calendar event appear under `needs_review`; Claude
must ask for missing details rather than inventing them. Nothing is written to
Notion until the user confirms it.

## Best-practice exploit demonstrations

### Rate limiting

The rate-limit exploit makes five allowed calls and proves the sixth is blocked
before Gmail or Notion is called:

```bash
python -m pytest tests/test_rate_limiting.py -v
```

### Error disclosure

The disclosure exploit raises an internal exception containing a fake OAuth
token, email excerpt, and local path. It proves that the public tool result
contains only a stable code and generic message:

```bash
python -m pytest tests/test_error_disclosure.py -v
```

## Known limitations

- Invitations with valid iCalendar data are detected most reliably.
- Keyword-matched email without an event is shown for manual review.
- The default Gmail lookback is 90 days and the maximum result limit is 50.
- OAuth setup is local and per user; another user must authorize their own
  Gmail account and connect their own Notion database.
- The in-memory rate limiter resets when the server restarts.

## Repository checklist

- Commit source, tests, README, `requirements.txt`, `.env.example`, and the
  Claude configuration.
- Never commit `.env`, `credentials.json`, `token.json`, or `.venv`.
- Keep the GitHub repository private and grant the instructor and TA access.
- Submit the architecture diagram, summary table, and reflection to Canvas,
  not to this repository.

## Code references

- MCP registration and stdio run pattern: [official MCP Python SDK v1.x](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)
- Gmail local OAuth flow: [official Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
- Gmail search query behavior: [Search and filter messages](https://developers.google.com/workspace/gmail/api/guides/filtering)
- Notion page creation payload: [Notion Create a page](https://developers.notion.com/reference/post-page)
- Notion duplicate lookup: [Notion Query a data source](https://developers.notion.com/reference/query-a-data-source)

The application-specific tool design, invitation parsing, confirmation flow,
validation, rate limiter, service layer, and tests were written for this
project.
