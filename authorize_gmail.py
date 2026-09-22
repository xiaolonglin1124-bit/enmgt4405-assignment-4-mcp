"""One-time local OAuth setup for read-only Gmail access."""

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from gmail_interview_scheduler_mcp.gmail_client import GMAIL_READONLY_SCOPE

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize read-only Gmail access")
    parser.add_argument(
        "--credentials",
        type=Path,
        default=PROJECT_ROOT / "credentials.json",
        help="Google OAuth desktop-client JSON file",
    )
    parser.add_argument(
        "--token",
        type=Path,
        default=PROJECT_ROOT / "token.json",
        help="Where to store the local OAuth token",
    )
    args = parser.parse_args()

    credentials_path = args.credentials.expanduser().resolve()
    token_path = args.token.expanduser().resolve()
    if not credentials_path.is_file():
        raise SystemExit(
            f"Missing {credentials_path}. Download a Desktop app OAuth file from "
            "Google Cloud and save it as credentials.json."
        )

    # OAuth flow follows Google's official Gmail Python quickstart:
    # https://developers.google.com/workspace/gmail/api/quickstart/python
    flow = InstalledAppFlow.from_client_secrets_file(
        credentials_path,
        [GMAIL_READONLY_SCOPE],
    )
    credentials = flow.run_local_server(port=0)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    token_path.chmod(0o600)
    print(f"Gmail authorization saved to {token_path}")


if __name__ == "__main__":
    main()
