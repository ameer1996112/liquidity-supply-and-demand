import os
import json
import logging
import threading
import traceback
import requests

logger = logging.getLogger("trinity.jira")

def create_bug_ticket(title: str, description: str, sync_block: bool = False):
    """
    Creates a Jira ticket for bugs and exceptions directly into the configured board.
    Fires in a background thread by default so it never blocks the trading worker.
    """
    domain = os.getenv("JIRA_DOMAIN", "")
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    project = os.getenv("JIRA_PROJECT_KEY", "DEV")
    
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
                "issuetype": {"id": os.getenv("JIRA_TASK_TYPE_ID", "10003")},
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
                logger.info("Successfully filed Jira Bug: %s", data.get("key"))
                
                try:
                    from src.adapters.discord import send_bug_alert_async
                    send_bug_alert_async(title, description, data.get("key"))
                except Exception as discord_err:
                    logger.warning("Failed to dispatch Discord Bug Alert: %s", discord_err)
            else:
                logger.error("Failed to automatically file Jira Bug. Status: %s. Response: %s", response.status_code, response.text)
        except Exception as e:
            logger.error("Exception occurred while forwarding bug to Jira: %s", e)

    if sync_block:
        _execute()
    else:
        threading.Thread(target=_execute, daemon=True, name="JiraBugAsync").start()
