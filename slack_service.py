"""
slack_service.py - Slack notifications for DevOps Autopilot.

Sends the incident summary and approval request. Tokens are read from the
environment and never included in any message or error text.
No Streamlit code lives in this file.
"""

import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

logger = logging.getLogger("devops_autopilot.slack")

SEVERITY_EMOJI = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}


class SlackServiceError(Exception):
    """An error whose message is safe to show to the user."""


def _esc(text: Any, limit: int = 600) -> str:
    """Escape Slack control characters and shorten long text."""
    value = str(text or "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _get_client_and_channel():
    token = (os.getenv("SLACK_BOT_TOKEN") or "").strip()
    channel = (os.getenv("SLACK_CHANNEL_ID") or "").strip()
    missing = [
        var for var, val in (("SLACK_BOT_TOKEN", token), ("SLACK_CHANNEL_ID", channel))
        if not val or val.startswith("your_")
    ]
    if missing:
        raise SlackServiceError("Missing Slack configuration: " + ", ".join(missing))
    return WebClient(token=token), channel


def build_incident_message(incident_id: str, report: Dict[str, Any], diagnosis: Dict[str, Any],
                           risk_level: str, validation_status: str,
                           pr_info: Optional[Dict[str, Any]], approval_status: str) -> str:
    severity = str(report.get("severity", "UNKNOWN")).upper()
    pr_line = f"<{pr_info['url']}|PR #{pr_info['number']}>" if pr_info else "Not created yet"
    return (
        f"🚨 *DEVOPS AUTOPILOT INCIDENT* (`{_esc(incident_id, 60)}`)\n\n"
        f"*Severity:* {SEVERITY_EMOJI.get(severity, '⚪')} {severity}\n"
        f"*Service:* {_esc(report.get('affected_service'), 100)}\n"
        f"*Incident:* {_esc(report.get('incident_summary'))}\n\n"
        f"*Root Cause:* {_esc(diagnosis.get('root_cause'))}\n"
        f"*Affected File:* `{_esc(diagnosis.get('affected_file'), 150)}`\n"
        f"*Proposed Fix:* {_esc(diagnosis.get('proposed_fix'))}\n\n"
        f"*Risk:* {_esc(risk_level, 20)}\n"
        f"*Validation:* {_esc(validation_status, 20)}\n"
        f"*GitHub PR:* {pr_line}\n"
        f"*Approval:* {_esc(approval_status, 20)}\n\n"
        "_Human approval required before any merge or deployment. "
        "Approve/Reject in the DevOps Autopilot dashboard (prototype)._"
    )


def send_incident_alert(incident_id: str, report: Dict[str, Any], diagnosis: Dict[str, Any],
                        risk_level: str, validation_status: str = "NOT RUN",
                        pr_info: Optional[Dict[str, Any]] = None,
                        approval_status: str = "PENDING") -> Dict[str, Any]:
    """Post the incident summary + approval request to the configured channel."""
    client, channel = _get_client_and_channel()
    text = build_incident_message(incident_id, report, diagnosis, risk_level,
                                  validation_status, pr_info, approval_status)
    try:
        response = client.chat_postMessage(channel=channel, text=text, mrkdwn=True)
    except SlackApiError as exc:
        code = ""
        try:
            code = exc.response.get("error", "")
        except Exception:  # noqa: BLE001
            pass
        hints = {
            "invalid_auth": "Slack authentication failed. Check SLACK_BOT_TOKEN.",
            "not_authed": "Slack authentication failed. Check SLACK_BOT_TOKEN.",
            "token_revoked": "The Slack token was revoked.",
            "channel_not_found": "Slack channel not found. Check SLACK_CHANNEL_ID.",
            "not_in_channel": "Invite the bot to the channel first (/invite @your-bot).",
            "missing_scope": "The bot token needs the chat:write scope.",
        }
        raise SlackServiceError(hints.get(code, f"Slack API error ({code or 'unknown'}).")) from None
    except Exception:  # noqa: BLE001
        raise SlackServiceError("Could not reach Slack.") from None
    logger.info("Slack notification sent")
    return {"ok": True, "channel": channel, "ts": response.get("ts")}
