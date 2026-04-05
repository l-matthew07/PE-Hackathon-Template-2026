"""
Discord reaction bot for alert acknowledgment and escalation.

✅ reaction  → silences all active alerts in Alertmanager for 1 hour
⬆️ reaction  → escalates based on WHO reacts:
                - on-call member reacts → goes to senior-eng
                - senior-eng member reacts → jumps straight to lead
                - anyone else → goes to next tier from current

Auto-escalation: if alert unacknowledged after 30min per tier, escalates to next.

Bot auto-adds ✅ and ⬆️ reactions to firing alert messages.
Reactions on resolved messages are silently ignored.
"""

import asyncio
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

import discord
import redis

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_ALERT_CHANNEL_ID"])
GUILD_ID = int(os.environ.get("DISCORD_GUILD_ID", "1490040458481762384"))
INCIDENT_CATEGORY_ID = int(os.environ.get("DISCORD_INCIDENT_CATEGORY_ID", "1490097852096053418"))
ALERTMANAGER_URL = os.environ.get("ALERTMANAGER_URL", "http://alertmanager:9093")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/1")

ESCALATION_ROLES = [
    os.environ.get("DISCORD_ONCALL_ROLE_ID", "1490051693251919962"),
    os.environ.get("DISCORD_SENIOR_ROLE_ID", "1490081907839471908"),
    os.environ.get("DISCORD_LEAD_ROLE_ID", "1490082322383376526"),
]
ROLE_NAMES = ["on-call", "senior-eng", "lead"]

AUTO_ESCALATE_MINUTES = 30

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

client = discord.Client(intents=intents)
rdb = redis.from_url(REDIS_URL, decode_responses=True)

# alert_key -> {first_seen, tier, message_id, acknowledged, resolved, incident_channel_id}
active_alerts: dict[str, dict] = {}
# message_id -> alert_key (for fast lookup on reaction)
message_to_alert: dict[int, str] = {}


def _serialize_state(state: dict) -> dict:
    """Convert state to Redis-compatible form (no bools or None)."""
    s = {}
    for k, v in state.items():
        if isinstance(v, datetime):
            s[k] = v.isoformat()
        elif isinstance(v, bool):
            s[k] = str(v)
        elif v is None:
            s[k] = ""
        else:
            s[k] = v
    return s


def _deserialize_state(state: dict) -> dict:
    """Restore types from Redis."""
    s = state.copy()
    if isinstance(s.get("first_seen"), str):
        s["first_seen"] = datetime.fromisoformat(s["first_seen"])
    if "message_id" in s:
        s["message_id"] = int(s["message_id"])
    if "incident_channel_id" in s and s["incident_channel_id"]:
        s["incident_channel_id"] = int(s["incident_channel_id"])
    for bool_key in ("acknowledged", "resolved"):
        if bool_key in s:
            s[bool_key] = str(s[bool_key]).lower() == "true"
    if "tier" in s:
        s["tier"] = int(s["tier"])
    return s


def persist_alert(alert_key: str, state: dict) -> None:
    rdb.hset(f"alert:{alert_key}", mapping=_serialize_state(state))
    rdb.expire(f"alert:{alert_key}", 86400)  # 24h TTL


def persist_message(message_id: int, alert_key: str) -> None:
    rdb.set(f"msg:{message_id}", alert_key, ex=86400)


def load_state() -> None:
    """Restore active_alerts and message_to_alert from Redis on startup."""
    for key in rdb.scan_iter("alert:*"):
        alert_key = key[len("alert:"):]
        raw = rdb.hgetall(key)
        if raw:
            state = _deserialize_state(raw)
            if not state.get("resolved"):
                active_alerts[alert_key] = state
    for key in rdb.scan_iter("msg:*"):
        message_id = int(key[len("msg:"):])
        alert_key = rdb.get(key)
        if alert_key and alert_key in active_alerts:
            message_to_alert[message_id] = alert_key
    print(f"Restored {len(active_alerts)} active alerts from Redis", flush=True)


async def create_incident_channel(alert_key: str, acknowledged_by: discord.Member | None, guild: discord.Guild) -> discord.TextChannel | None:
    """Create a private incident channel visible only to on-call roles."""
    channel_name = f"incident-{alert_key.lower().replace(' ', '-')}"

    # Build permission overwrites: deny everyone, allow each escalation role
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    for role_id in ESCALATION_ROLES:
        role = guild.get_role(int(role_id))
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )
    # Also allow the acknowledging member explicitly
    if acknowledged_by:
        overwrites[acknowledged_by] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )

    try:
        category = guild.get_channel(INCIDENT_CATEGORY_ID)
        channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)
        state = active_alerts.get(alert_key, {})
        first_seen = state.get("first_seen", datetime.now(timezone.utc))
        ack_name = str(acknowledged_by) if acknowledged_by else "unknown"
        await channel.send(
            f"🚨 **Incident: {alert_key}**\n"
            f"• First detected: <t:{int(first_seen.timestamp())}:R>\n"
            f"• Acknowledged by: {f'<@{acknowledged_by.id}>' if acknowledged_by else ack_name}\n"
            f"• Use this channel to coordinate the fix.\n"
            f"• Channel will be deleted automatically when the alert resolves."
        )
        print(f"Created incident channel: #{channel_name}", flush=True)
        return channel
    except Exception as e:
        print(f"Failed to create incident channel: {e}", flush=True)
        return None


async def close_incident_channel(alert_key: str) -> None:
    """Delete the incident channel for a resolved alert."""
    state = active_alerts.get(alert_key)
    if not state:
        return
    channel_id = state.get("incident_channel_id")
    if not channel_id:
        return
    channel = client.get_channel(channel_id)
    if channel:
        try:
            await channel.send(f"✅ Alert **{alert_key}** has been resolved. Closing this channel in 30 seconds.")
            await asyncio.sleep(30)
            await channel.delete(reason=f"Alert {alert_key} resolved")
            print(f"Deleted incident channel for {alert_key}", flush=True)
        except Exception as e:
            print(f"Failed to delete incident channel: {e}", flush=True)


def silence_alert(alert_key: str, created_by: str) -> None:
    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(hours=1)
    # alert_key may be "alertname:instance" or just "alertname"
    if ":" in alert_key:
        alertname, instance = alert_key.split(":", 1)
        matchers = [
            {"name": "alertname", "value": alertname, "isRegex": False, "isEqual": True},
            {"name": "instance", "value": instance, "isRegex": False, "isEqual": True},
        ]
    else:
        matchers = [{"name": "alertname", "value": alert_key, "isRegex": False, "isEqual": True}]
    silence = {
        "matchers": matchers,
        "startsAt": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endsAt": ends_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "createdBy": created_by,
        "comment": f"Acknowledged via Discord reaction by {created_by}",
    }
    req = urllib.request.Request(
        f"{ALERTMANAGER_URL}/api/v2/silences",
        data=json.dumps(silence).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
        silence_id = body.get("silenceID", "")
        print(f"Silence created for {alert_key}: {resp.status} id={silence_id}", flush=True)
        return silence_id


def expire_silence(silence_id: str) -> None:
    """Delete a silence by ID."""
    try:
        req = urllib.request.Request(
            f"{ALERTMANAGER_URL}/api/v2/silence/{silence_id}",
            method="DELETE",
        )
        with urllib.request.urlopen(req) as resp:
            print(f"Silence {silence_id} deleted: {resp.status}", flush=True)
    except Exception as e:
        print(f"Failed to delete silence {silence_id}: {e}", flush=True)


def get_member_tier(member: discord.Member | None) -> int | None:
    """Returns the escalation tier index of the member based on their roles, or None."""
    if member is None:
        return None
    member_role_ids = {str(r.id) for r in member.roles}
    # Check from highest tier down so a lead who is also senior-eng gets lead tier
    for i in range(len(ESCALATION_ROLES) - 1, -1, -1):
        if ESCALATION_ROLES[i] in member_role_ids:
            return i
    return None


async def escalate(
    alert_key: str,
    channel: discord.TextChannel,
    reason: str,
    source_message: discord.Message | None = None,
    target_tier: int | None = None,
) -> None:
    state = active_alerts.get(alert_key)
    if state is None:
        return

    if target_tier is None:
        next_tier = state["tier"] + 1
    else:
        next_tier = target_tier

    if next_tier >= len(ESCALATION_ROLES):
        msg = f"🚨 **{alert_key}** has reached maximum escalation — **{ROLE_NAMES[-1]}** is already notified."
        if source_message:
            await source_message.reply(msg)
        else:
            await channel.send(msg)
        return

    role_id = ESCALATION_ROLES[next_tier]
    role_name = ROLE_NAMES[next_tier]
    active_alerts[alert_key]["tier"] = next_tier

    msg = f"⬆️ <@&{role_id}> — **{alert_key}** escalated to **{role_name}**. {reason}"
    if source_message:
        await source_message.reply(msg)
    else:
        await channel.send(msg)

    print(f"Escalated {alert_key} to tier {next_tier} ({role_name})", flush=True)


def get_active_alertmanager_keys() -> set[str]:
    """Return the set of 'alertname:instance' keys currently active in Alertmanager."""
    try:
        req = urllib.request.Request(f"{ALERTMANAGER_URL}/api/v2/alerts")
        with urllib.request.urlopen(req) as resp:
            alerts = json.loads(resp.read())
        keys = set()
        for a in alerts:
            if a["status"]["state"] == "suppressed":
                continue
            name = a["labels"]["alertname"]
            instance = a["labels"].get("instance", "")
            keys.add(f"{name}:{instance}" if instance else name)
        return keys
    except Exception as e:
        print(f"Failed to query Alertmanager alerts: {e}", flush=True)
        return set()


async def auto_escalation_loop() -> None:
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    while not client.is_closed():
        await asyncio.sleep(60)

        if channel is None:
            continue

        now = datetime.now(timezone.utc)
        active_in_am = get_active_alertmanager_keys()

        for alert_key, state in list(active_alerts.items()):
            if state.get("resolved"):
                continue

            # If alert was acknowledged (silenced) and is no longer in Alertmanager, it resolved
            if state.get("acknowledged") and alert_key not in active_in_am:
                state["resolved"] = True
                persist_alert(alert_key, state)
                print(f"Silenced alert resolved: {alert_key}", flush=True)
                # Expire the silence so it doesn't linger
                silence_id = state.get("silence_id")
                if silence_id:
                    await asyncio.get_event_loop().run_in_executor(None, expire_silence, silence_id)
                # Reply to the original alert message if possible
                resolved_msg = f"✅ **[RESOLVED] {alert_key}** — The service has recovered and is back to normal."
                message_id = state.get("message_id")
                try:
                    if message_id:
                        original = await channel.fetch_message(int(message_id))
                        await original.reply(resolved_msg)
                    else:
                        await channel.send(resolved_msg)
                except Exception:
                    await channel.send(resolved_msg)
                asyncio.get_event_loop().create_task(close_incident_channel(alert_key))
                continue

            current_tier = state["tier"]
            if current_tier >= len(ESCALATION_ROLES) - 1:
                continue

            age_minutes = (now - state["first_seen"]).total_seconds() / 60
            escalation_threshold = AUTO_ESCALATE_MINUTES * (current_tier + 1)

            if age_minutes >= escalation_threshold:
                tier_name = ROLE_NAMES[current_tier]
                await escalate(
                    alert_key,
                    channel,
                    f"No acknowledgment from **{tier_name}** after {int(age_minutes)} minutes.",
                )


@client.event
async def on_ready():
    load_state()
    print(f"Discord bot ready as {client.user}", flush=True)
    client.loop.create_task(auto_escalation_loop())


@client.event
async def on_message(message: discord.Message):
    if message.channel.id != CHANNEL_ID:
        return
    if not message.author.bot:
        return
    # Ignore our own messages to avoid parsing escalation replies as alerts
    if message.author.id == client.user.id:
        return

    content = message.content or ""

    # Track new firing alerts and add reaction shortcuts
    if "🚨" in content:
        after_siren = content.split("🚨", 1)[-1].strip()
        for chunk in after_siren.split(","):
            alert_key = chunk.strip()
            if alert_key and not alert_key.startswith("<"):
                if alert_key not in active_alerts:
                    state = {
                        "first_seen": datetime.now(timezone.utc),
                        "tier": 0,
                        "message_id": message.id,
                        "acknowledged": False,
                        "resolved": False,
                    }
                    active_alerts[alert_key] = state
                    message_to_alert[message.id] = alert_key
                    persist_alert(alert_key, state)
                    persist_message(message.id, alert_key)
                    print(f"Tracking alert: {alert_key}", flush=True)

        # Auto-add reaction shortcuts so users can easily respond
        try:
            await message.add_reaction("✅")
            await message.add_reaction("⬆️")
        except Exception as e:
            print(f"Failed to add reactions: {e}", flush=True)

    # Mark resolved — relay posts "✅ AlertName" content for resolved messages
    if "✅" in content and "acknowledged" not in content.lower() and "silenced" not in content.lower():
        after_check = content.split("✅", 1)[-1].strip()
        print(f"Resolved message detected, content after ✅: '{after_check}', active alerts: {list(active_alerts.keys())}", flush=True)
        for chunk in after_check.split(","):
            alert_key = chunk.strip()
            print(f"Checking alert_key: '{alert_key}'", flush=True)
            if alert_key in active_alerts:
                active_alerts[alert_key]["resolved"] = True
                print(f"Alert resolved: {alert_key}", flush=True)
                asyncio.get_event_loop().create_task(close_incident_channel(alert_key))


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.channel_id != CHANNEL_ID:
        return
    if payload.user_id == client.user.id:
        return

    channel = client.get_channel(payload.channel_id)
    if channel is None:
        return

    message = await channel.fetch_message(payload.message_id)
    if not message.author.bot:
        return

    # Only handle reactions on original alert messages (ones the bot added reactions to)
    alert_key = message_to_alert.get(payload.message_id)
    # Fallback: check Redis directly in case bot restarted and lost in-memory map
    if alert_key is None:
        alert_key = rdb.get(f"msg:{payload.message_id}")
        if alert_key and alert_key in active_alerts:
            message_to_alert[payload.message_id] = alert_key
        else:
            alert_key = None
    if alert_key is None:
        return

    state = active_alerts.get(alert_key)
    if state is None:
        return

    # Silently ignore reactions on resolved alerts
    if state.get("resolved"):
        return

    emoji = str(payload.emoji)
    member = payload.member
    display_name = str(member) if member else str(payload.user_id)

    if emoji == "✅":
        if state.get("acknowledged") or state.get("resolved"):
            return
        try:
            silence_id = await asyncio.get_event_loop().run_in_executor(None, silence_alert, alert_key, display_name)
            state["acknowledged"] = True
            state["silence_id"] = silence_id

            # Create private incident channel
            incident_channel = None
            guild = client.get_guild(GUILD_ID)
            if guild:
                incident_channel = await create_incident_channel(alert_key, member, guild)
                if incident_channel:
                    state["incident_channel_id"] = incident_channel.id

            persist_alert(alert_key, state)
            channel_mention = f" See <#{incident_channel.id}> to coordinate." if incident_channel else ""
            await message.reply(
                f"✅ Acknowledged by <@{payload.user_id}> — **{alert_key}** silenced for 1 hour. "
                f"Escalation stopped.{channel_mention}"
            )
        except Exception as e:
            print(f"Failed to silence: {e}", flush=True)
            await message.reply(f"⚠️ Failed to silence alert: {e}")

    elif emoji == "⬆️":
        if state.get("resolved"):
            return

        # Role-aware escalation: jump based on who is reacting
        member_tier = get_member_tier(member)
        if member_tier is not None:
            # Escalate to the tier above the reactor's role
            target_tier = member_tier + 1
        else:
            # Not a known role — go to next tier from current
            target_tier = state["tier"] + 1

        await escalate(
            alert_key,
            channel,
            f"Manual escalation by <@{payload.user_id}> ({ROLE_NAMES[member_tier] if member_tier is not None else 'unknown'}).",
            source_message=message,
            target_tier=target_tier,
        )


client.run(TOKEN)
