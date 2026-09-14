# Job Application Tracker MCP

A local Python MCP server that lets Claude Desktop add and query job applications stored in a Notion data source.

## Assignment scope

- Domain: Personal Productivity
- MCP endpoints: two tools and one prompt
- Authentication: Notion integration token in a local `.env` file
- Best practices: local rate limiting and safe error disclosure
- Transport: local `stdio`
- MCP SDK: Python SDK 1.x compatibility line, pinned below 2.0 for reliable
  Claude Desktop handshake support

### Tools

- `add_job_application`: adds an application to Notion.
- `list_job_applications`: lists applications with optional status and follow-up-date filters.

### Prompt

- `weekly_job_search_review`: guides Claude through a structured review without making unconfirmed changes.

## 1. Open the project in VS Code

Open this folder, not its parent folder:

```text
job-application-tracker-mcp
```

Install the recommended Python and Pylance extensions when VS Code asks.

## 2. Create the virtual environment

The assignment recommends `uv`:

```bash
uv venv --seed
source .venv/bin/activate
uv pip install -r requirements.txt
```

The `--seed` option installs `pip` in the environment. VS Code's Python
Environments extension uses `python -m pip list` to display installed packages,
so seeding prevents repeated `Error refreshing packages` notifications.

If `uv` is not installed, standard Python also works:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Confirm that VS Code selected `.venv/bin/python` as the interpreter.

## 3. Create the Notion data source

Create a Notion database with these exact property names and types:

| Property | Notion type |
|---|---|
| Role | Title |
| Company | Text |
| Status | Select |
| Applied Date | Date |
| Follow-up Date | Date |
| Job URL | URL |
| Notes | Text |

Add these Status options exactly:

- Wishlist
- Applied
- Interview
- Offer
- Rejected
- Withdrawn

## 4. Create and connect a Notion integration

1. Create an internal integration in the Notion developer portal.
2. Give it read and insert-content capabilities.
3. In the Notion database menu, choose **Add connections** and share the database with the integration.
4. Copy the integration token.
5. In the database settings, open **Manage data sources**, open the data
   source's `•••` menu, and choose **Copy data source ID**. A database ID and a
   data source ID are different in the current Notion API, so use the copied
   data source ID in `.env`.

The official API requires the target data source to be shared with the connection. An unshared source may appear as a `404` response.

## 5. Configure secrets

Copy the example file:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
NOTION_TOKEN=secret_your_real_token
NOTION_DATA_SOURCE_ID=your_real_data_source_id
MCP_RATE_LIMIT_CALLS=5
MCP_RATE_LIMIT_WINDOW_SECONDS=60
```

The application reads this file directly with `pathlib.Path` and `dotenv_values`. The populated `.env` is ignored by Git and must never be committed.

## 6. Run automated tests

The tests use fakes and do not call Notion:

```bash
python -m pytest
```

Expected result: all tests pass.

## 7. Inspect the MCP server

With the virtual environment active:

```bash
mcp dev server.py
```

The Inspector should show:

- Tools: `add_job_application`, `list_job_applications`
- Prompt: `weekly_job_search_review`

Running `python server.py` directly is also valid, but it will appear to wait silently because a stdio MCP server waits for a client.

## 8. Configure Claude Desktop

The included `claude_desktop_config.json` contains complete absolute paths for this checkout. Merge its `job-application-tracker` entry into the existing Claude Desktop configuration.

On macOS, the configuration file is normally located at:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Restart Claude Desktop after changing the configuration. Do not add the Notion token to the Claude configuration; the server loads it from the local `.env` file.

If the repository is moved or cloned elsewhere, update both absolute paths in the configuration file.

## 9. Demo script

1. Show that the server appears in Claude Desktop.
2. Ask: `Add an application for Adobe, Product Designer, applied today, using https://example.com/jobs/123.`
3. Show the new row in Notion.
4. Ask: `List applications that need follow-up before 2026-09-30.`
5. Select the `weekly_job_search_review` prompt.
6. Run the two exploit tests below.

## Best-practice exploit demonstrations

### Rate limiting

`tests/test_rate_limiting.py` performs five allowed calls in the same window and proves the sixth raises `RateLimitExceeded`. The check occurs before the Notion call, preventing needless external requests.

```bash
python -m pytest tests/test_rate_limiting.py -v
```

### Error disclosure

`tests/test_error_disclosure.py` raises a simulated internal exception containing a fake bearer token and local file path. It proves that the public result contains only `INTERNAL_ERROR` and a generic message.

```bash
python -m pytest tests/test_error_disclosure.py -v
```

## Error behavior

The server returns stable public codes:

- `INVALID_INPUT`
- `RATE_LIMIT_EXCEEDED`
- `CONFIGURATION_ERROR`
- `EXTERNAL_SERVICE_ERROR`
- `INTERNAL_ERROR`

Notion response bodies, authorization headers, tokens, local paths, and tracebacks are never returned to the MCP client.

## Repository checklist

- Commit the source, tests, README, `requirements.txt`, `.env.example`, and Claude configuration.
- Do not commit `.env` or `.venv`.
- Keep the GitHub repository private.
- Give the instructor and TA access.
- Submit the architecture diagram, summary table, and reflection to Canvas, not to this repository.

## Code references

- MCP server registration and stdio run pattern: [official MCP Python SDK v1.x](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)
- Notion page creation payload: [Notion Create a page](https://developers.notion.com/reference/post-page)
- Notion query filters: [Notion Query a data source](https://developers.notion.com/reference/query-a-data-source)

The application-specific design, validation, rate limiter, service layer, and tests were written for this project.
