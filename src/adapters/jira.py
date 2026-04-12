import json
import logging
import threading
import traceback
import requests
from config.settings import get_settings

logger = logging.getLogger("trinity.jira")

def create_bug_ticket(title: str, description: str, sync_block: bool = False):
    """
    Creates a Jira ticket for bugs and exceptions directly into the configured board.
    Fires in a background thread by default so it never blocks the trading worker.
    """
    settings = get_settings()
    domain = settings.jira_base_url or settings.jira_domain or ""
    email = settings.jira_email
    token = settings.jira_api_token.get_secret_value()
    project = settings.jira_project_key
    
    if not domain.startswith("http"):
        # Default to https if missing
        domain = f"https://{domain}"
        
    if not all([domain, email, token]):
        logger.warning("Jira integration disabled: Missing JIRA_DOMAIN, JIRA_EMAIL, or JIRA_API_TOKEN")
        return

    def _execute():
        url = f"{domain.rstrip('/')}/rest/api/3/issue"
        safe_title = title if len(title) <= 255 else title[:252] + "..."

        payload = {
            "fields": {
                "project": {"key": project},
                "summary": f"[BUG] {safe_title}"[:255],
                "issuetype": {"id": settings.jira_task_type_id},
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "codeBlock",
                            "attrs": {"language": "python"},
                            "content": [{"type": "text", "text": description}]
                        }
                    ]
                }
            }
        }

        try:
            response = requests.post(
                url,
                auth=(email, token),
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            if response.status_code in (200, 201):
                data = response.json()
                jira_key = data.get("key")
                logger.info("Successfully filed Jira Bug: %s", jira_key)

                try:
                    from src.adapters.discord import send_bug_alert_async
                    send_bug_alert_async(title, description, jira_key)
                except Exception as discord_err:
                    logger.warning("Failed to dispatch Discord Bug Alert: %s", discord_err)

                # v1.2 UI-02: Log to agent event feed (Redis Agentic View)
                try:
                    from src.adapters.redis_queue import get_redis as _get_redis
                    from src.services.agent_events import log_agent_event
                    log_agent_event(
                        _get_redis(),
                        event_type="jira_ticket",
                        message=f"Bug ticket created: {jira_key} — {title[:80]}",
                        jira_key=jira_key,
                    )
                except Exception as _ae:
                    logger.debug("agent_event log failed (non-critical): %s", _ae)
            else:
                logger.error("Failed to automatically file Jira Bug. Status: %s. Response: %s", response.status_code, response.text)
        except Exception as e:
            logger.error("Exception occurred while forwarding bug to Jira: %s", e)

    if sync_block:
        _execute()
    else:
        threading.Thread(target=_execute, daemon=True, name="JiraBugAsync").start()
