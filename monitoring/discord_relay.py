"""
Minimal Alertmanager -> Discord webhook relay.
Puts the role mention in `content` so Discord actually pings.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
ONCALL_ROLE_ID = os.environ.get("DISCORD_ONCALL_ROLE_ID", "")


def log(msg):
    print(msg, flush=True)
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def send_to_discord(payload: dict) -> None:
    alerts = payload.get("alerts", [])
    if not alerts:
        return

    firing = [a for a in alerts if a.get("status") == "firing"]

    embeds = []
    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        is_firing = alert.get("status") == "firing"

        name = labels.get("alertname", "Alert")
        instance = labels.get("instance", "")
        if is_firing:
            summary = annotations.get("summary", name)
            description = annotations.get("description", "").strip()
        else:
            summary = annotations.get("resolved_summary", annotations.get("summary", name))
            description = annotations.get("resolved_description", annotations.get("description", "")).strip()

        color = 0xFF0000 if is_firing else 0x00FF00
        state = "FIRING" if is_firing else "RESOLVED"

        embed = {
            "title": f"[{state}] {name}",
            "description": f"**{summary}**\n{description}",
            "color": color,
        }
        if instance:
            embed["fields"] = [{"name": "Instance", "value": instance, "inline": True}]
        embeds.append(embed)

    mention = f"<@&{ONCALL_ROLE_ID}> " if ONCALL_ROLE_ID and firing else ""
    icon = "🚨" if firing else "✅"
    alert_keys = ", ".join(
        f"{a['labels'].get('alertname', 'Alert')}:{a['labels'].get('instance', '')}"
        if a['labels'].get('instance') else a['labels'].get('alertname', 'Alert')
        for a in alerts
    )
    content = f"{mention}{icon} {alert_keys}"

    discord_payload = json.dumps({"content": content, "embeds": embeds}).encode()
    log(f"Sending to Discord: {discord_payload.decode()}")

    req = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=discord_payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AlertmanagerDiscordRelay/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            log(f"Discord responded: {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        log(f"Discord HTTP error {e.code}: {body}")
        raise
    except Exception as e:
        log(f"Discord request failed: {e}")
        raise


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            log(f"Received payload: {json.dumps(payload)}")
            send_to_discord(payload)
            self.send_response(200)
        except Exception as e:
            log(f"Error handling request: {e}")
            self.send_response(500)
        self.end_headers()

    def log_message(self, fmt, *args):
        log(f"{self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9094))
    log(f"Listening on :{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
