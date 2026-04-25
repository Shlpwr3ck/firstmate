"""
1st Mate (1m) — Personal AI Assistant
Signal bot | LLM API + Ollama fallback | Full tool suite
"""

import os
import json
import time
import base64
import logging
import requests
import anthropic
import ollama as ollama_client
from datetime import datetime, timezone
from dotenv import load_dotenv
from tools import TOOL_SCHEMAS, execute_tool
from tools.reminder_tool import set_current_sender, check_due_reminders

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SIGNAL_API_URL      = os.getenv("SIGNAL_API_URL", "http://localhost:8080")
SIGNAL_NUMBER       = os.getenv("SIGNAL_NUMBER")       # bot's number e.g. +13526918580
ALLOWED_NUMBER      = os.getenv("ALLOWED_NUMBER")       # your personal Signal number
ALLOWED_NUMBER_2    = os.getenv("ALLOWED_NUMBER_2")     # AP's Signal number
ALLOWED_UUID        = os.getenv("ALLOWED_UUID")         # your Signal UUID (used when sourceNumber is absent)
LLM_API_KEY         = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
OLLAMA_MODEL        = os.getenv("OLLAMA_MODEL", "1m-coder")
OLLAMA_HOST         = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL               = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
POLL_INTERVAL       = int(os.getenv("POLL_INTERVAL", "2"))  # seconds
CONV_LOG            = os.path.join(os.path.dirname(__file__), "memory", "conversation_log.jsonl")

# Agent routing — prefix a message with !agent to route DIRECTLY to that local model
# !prefix bypasses Claude entirely (free, local inference)
# No prefix = Claude API (full tools, internet, vision)
# !vision is handled by Claude natively (multimodal) — Ollama is offline fallback only
AGENT_MODELS = {
    "!nhn":    "1m-nhn",      # NHN network/security agent
    "!net":    "1m-nhn",
    "!sec":    "1m-sec",      # general security
    "!code":   "1m-coder",    # coding
    "!coder":  "1m-coder",
    "!reason": "1m-reason",   # deep reasoning
    "!think":  "1m-reason",
    "!assist": "1m-assist",   # AI/tech assistant
    "!ai":     "1m-assist",
    "!coach":  "1m-coach",    # workout coach
    "!fit":    "1m-coach",
    "!vision": "1m-vision",   # image/visual analysis (Claude primary, moondream fallback)
    "!gemma":  "gemma4-fast", # Gemma 4 E2B, thinking off — fast local general chat
}

llm = anthropic.Anthropic(api_key=LLM_API_KEY)

# In-session conversation history keyed by sender number
conversation_history: dict[str, list] = {}

# Last received image path per sender (persists across messages in the session)
last_image: dict[str, str] = {}

CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg":  ".jpg",
    "image/png":  ".png",
    "image/gif":  ".gif",
    "image/webp": ".webp",
}


def save_attachment_to_disk(b64_data: str, content_type: str) -> str:
    """Decode base64 image and save to ~/Downloads/. Returns saved path or empty string."""
    ext = CONTENT_TYPE_EXT.get(content_type.lower().split(";")[0].strip(), ".jpg")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    home = os.getenv("HOME", "/home/sh1pwr3ck")
    downloads = os.path.join(home, "Downloads")
    os.makedirs(downloads, exist_ok=True)
    path = os.path.join(downloads, f"signal_{ts}{ext}")
    try:
        with open(path, "wb") as f:
            f.write(base64.standard_b64decode(b64_data))
        logger.info(f"Attachment saved: {path}")
        return path
    except Exception as e:
        logger.error(f"Failed to save attachment: {e}")
        return ""


def log_exchange(sender: str, user_msg: str, assistant_msg: str, model: str, via_claude: bool):
    """Append a conversation exchange to the JSONL log file."""
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sender": sender,
        "user": user_msg,
        "assistant": assistant_msg,
        "model": model,
        "via_claude": via_claude
    }
    try:
        with open(CONV_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write conversation log: {e}")


def load_history(n_exchanges: int = 20):
    """Seed conversation_history from the last n_exchanges in CONV_LOG on startup."""
    if not os.path.exists(CONV_LOG):
        return
    try:
        with open(CONV_LOG, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
        recent = lines[-n_exchanges:]
        loaded = 0
        for line in recent:
            try:
                entry = json.loads(line)
                sender = entry.get("sender")
                if not sender:
                    continue
                if sender not in conversation_history:
                    conversation_history[sender] = []
                conversation_history[sender].append({"role": "user",      "content": entry["user"]})
                conversation_history[sender].append({"role": "assistant", "content": entry["assistant"]})
                loaded += 1
            except (json.JSONDecodeError, KeyError):
                continue
        logger.info(f"Loaded {loaded} exchanges from conversation log")
    except Exception as e:
        logger.error(f"Failed to load conversation history: {e}")


def _build_system_prompt() -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    return f"""You are 1st Mate (1m), a personal AI assistant for James Jackson ("Jax").

Today's date: {today}

## WHO JAX IS
- U.S. Navy Retired PO1, Gunner's Mate, 20 years service — retired with full benefits (DFAS/Tricare)
- Owner of Noble Technologies LLC — IT consulting + cybersecurity firm, Dunnellon FL 34431
- Career goal: Grow Noble Technologies into a large, successful business — this is the #1 priority. Jax is NOT pursuing employment elsewhere.
- CompTIA Security+ ✓, Network+ ✓, PenTest+ in progress (exam June 24, 2026 — rescheduled from Apr 1)
- Homesteader — food forest, vegetable garden, fence/pasture build-out underway

## FAMILY
- AP (Anna) — wife, Marion County Sheriff's Office (MCSO)
- Ipo — oldest (2006) | JD — son (2018) | Ali — daughter (2020), nickname "Ali Gator"
- Business phone: (352) 691-8580 | Personal: (813) 893-4620
- AP authorized on this bot (+12629491542) — same access as Jax

## NOBLE TECHNOLOGIES LLC
- EIN: 33-1426232 | FL LLC active since Oct 4, 2024
- Services: IT consulting, cybersecurity, church tech, managed services
- Rate: $50/hr | FL sales tax: 6.5%
- Website: nobletechnologiesllc.com (WordPress on noble-wordpress .12, Cloudflare Tunnel)
- Billing: Invoice Ninja at invoice.nobletechnologiesllc.com (self-hosted on dead-reckoning)
- Analytics: Umami at analytics.nobletechnologiesllc.com
- Active clients: FBCD (First Baptist Church Dunnellon), LRBC (Lake Rousseau Baptist — thelrbc.org), Ms. Cali (security camera proposal sent Apr 21), Joan (tablet migration)
- Square payment gateway (app ID sq0idp-84t5bv3pIit6i2PXYumqRg — capital I, not l)

## NETWORK / HOMELAB
Subnet: 10.34.43.0/24

Machine aliases — always use these exact names in ssh_command:
- dead-reckoning  → 10.34.43.5  — primary workstation, Wazuh Manager, 1st Mate runs here
- macbook         → 10.34.43.7  — MacBook Pro M1 Max 2021 (2TB SSD, 64GB RAM)
- ubuntuserver    → 10.34.43.11 — Pi-hole, ntopng, Jellyfin, Twingate connector
- noble-wordpress → 10.34.43.12 — WordPress, Umami analytics, Cloudflare Tunnel
- proxmox         → 10.34.43.10 — Proxmox VE hypervisor (VMs: UbuntuServer=101, Kali=102, WP=103, Metasploitable=104)
- kali            → 10.34.43.41 — Kali Linux VM (pentesting)
- hacktop         → 10.34.43.45 — Parrot OS physical laptop
- frigate         → 10.34.43.31 — Frigate NVR v0.16.3 (cameras: front, garage, office, kitchen, safe, backdoor)
- linode          → 194.195.212.217 — RustDesk relay server

Local tools (dead-reckoning only): get_system_status, check_service, list_docker_containers
Remote access: ssh_command with host name above
Camera snapshots: frigate_snapshot (camera: front/garage/office/kitchen/safe/backdoor)

## CALENDAR
- Platform: iCloud CalDAV — syncs to iPhone, MacBook, Thunderbird (Nextcloud is decommissioned)
- Calendar name: "Noble Tech"
- get_calendar_events — read upcoming events (days_ahead param, default 7)
- create_calendar_event — create events; start_dt/end_dt format: "YYYY-MM-DD HH:MM" (Eastern time)
- delete_calendar_event — delete by partial title match
- replace_calendar — full ICS replace (use for workouts calendar)

## FILESYSTEM (dead-reckoning)
Home: /home/sh1pwr3ck — always use full absolute paths
Key paths:
- Business:       ~/noble-technologies-llc/
- AI directives:  ~/AI-DIRECTIVES.md
- 1st Mate:       ~/firstmate/
- Homestead:      ~/homestead/
- Obsidian vault: ~/Documents/NTK/

## AI-KNOWLEDGE VAULT (Obsidian)
Path: ~/Documents/NTK/AI-Knowledge/ — synced to iPhone + MacBook via Obsidian Sync
Read these before re-deriving known info:
- Network & Infrastructure.md — IPs, hosts, SSH, RustDesk, services
- Noble Technologies.md — business, clients, pricing, compliance
- 1st Mate.md — Signal bot, agents, Ollama stack, tool list, versions
- Homelab.md — Wazuh, Pi-hole, Frigate, Docker, storage
- Clients/FBCD.md | Clients/LRBC.md

## VISION TASKS (!vision prefix or image attached)
- Extract all useful content from the image
- For social media posts: pull text, author, topic, actionable info
- Format as clean Obsidian markdown note with relevant tags
- Homestead content → /home/sh1pwr3ck/homestead/ (food-forest/, vegetable-garden/ subdirs)
- Use write_file to save automatically — do not just describe it, save it
- If topic is unclear, ask before saving

## YOUR PERSONALITY
- Direct, efficient. Military clarity — concise, actionable, no fluff.
- When you CAN do something (check a service, search the web, read a file) — DO IT immediately.
- You are a private assistant for Jax and AP only. Act accordingly.
- Never add disclaimers, caveats, or hedge language unless security-critical.
- Email requires explicit JRJ authorization each time before sending — no exceptions.
"""

SYSTEM_PROMPT = _build_system_prompt()


def is_authorized(sender: str) -> bool:
    return sender in filter(None, [ALLOWED_NUMBER, ALLOWED_NUMBER_2, ALLOWED_UUID])


def send_signal_message(recipient: str, message: str):
    """Send a message via signal-cli REST API. Splits messages over 4000 chars."""
    max_len = 4000
    chunks = [message[i:i+max_len] for i in range(0, len(message), max_len)]
    for chunk in chunks:
        try:
            resp = requests.post(
                f"{SIGNAL_API_URL}/v2/send",
                json={"message": chunk, "number": SIGNAL_NUMBER, "recipients": [recipient]},
                timeout=10
            )
            if resp.status_code not in (200, 201):
                logger.error(f"Signal send failed {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Signal send error: {e}")


def receive_signal_messages() -> list:
    """Poll for new messages from signal-cli REST API."""
    try:
        resp = requests.get(
            f"{SIGNAL_API_URL}/v1/receive/{SIGNAL_NUMBER}",
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json() or []
    except Exception as e:
        logger.error(f"Signal receive error: {e}")
    return []


def extract_message(envelope: dict) -> tuple[str | None, str | None, list]:
    """Extract sender number, message text, and attachments from a signal-cli envelope."""
    sender = envelope.get("sourceNumber") or envelope.get("source")
    data = envelope.get("dataMessage", {})
    text = data.get("message")
    attachments = data.get("attachments", [])
    return sender, text, attachments


def fetch_attachment_b64(attachment: dict) -> tuple[str, str] | None:
    """Fetch an attachment from signal-cli and return (base64_data, media_type)."""
    attachment_id = attachment.get("id")
    content_type = attachment.get("contentType", "image/jpeg")
    if not attachment_id:
        return None
    try:
        resp = requests.get(f"{SIGNAL_API_URL}/v1/attachments/{attachment_id}", timeout=30)
        if resp.status_code == 200:
            b64 = base64.standard_b64encode(resp.content).decode("utf-8")
            return b64, content_type
        logger.error(f"Attachment fetch failed {resp.status_code} for id {attachment_id}")
    except Exception as e:
        logger.error(f"Failed to fetch attachment {attachment_id}: {e}")
    return None


def run_with_tools(messages: list) -> str:
    """Agentic loop: LLM calls tools until it has a final answer."""
    # Sanitize: remove any messages with empty string content before sending to Claude
    messages = [m for m in messages if not (isinstance(m.get("content"), str) and not m["content"].strip())]
    sys_prompt = _build_system_prompt()
    for iteration in range(8):
        response = llm.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=sys_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, 'text'):
                    logger.info(f"LLM OK — {response.usage.input_tokens} in / {response.usage.output_tokens} out (iter {iteration+1})")
                    return block.text
            return "(no response)"

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Tool call: {block.name}({block.input})")
                    result = execute_tool(block.name, block.input)
                    logger.info(f"Tool result: {str(result)[:100]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

    return "Reached max tool iterations — something went wrong."


def run_with_vision(prompt: str, image_b64: str, image_type: str) -> str:
    """Send an image + prompt to Claude and return the response (with tool use)."""
    messages = [{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_type,
                    "data": image_b64
                }
            },
            {
                "type": "text",
                "text": prompt if prompt else "Extract all content from this image and save it as an Obsidian note in the appropriate homestead directory."
            }
        ]
    }]
    # Use run_with_tools logic but seed with the vision message
    sys_prompt = _build_system_prompt()
    for iteration in range(8):
        response = llm.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=sys_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, 'text'):
                    logger.info(f"Vision OK — {response.usage.input_tokens} in / {response.usage.output_tokens} out (iter {iteration+1})")
                    return block.text
            return "(no response)"

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Vision tool call: {block.name}({block.input})")
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

    return "Reached max tool iterations — something went wrong."


def handle_command(sender: str, command: str):
    """Handle /start /clear /status commands."""
    if command == "/start":
        send_signal_message(sender, "1st Mate online. What do you need?")
    elif command == "/clear":
        conversation_history[sender] = []
        send_signal_message(sender, "Session memory cleared.")
    elif command == "/status":
        history_count = len(conversation_history.get(sender, []))
        agents = "\n".join(f"  {k} → {v}" for k, v in AGENT_MODELS.items() if k in ["!nhn","!sec","!code","!reason","!assist","!coach","!vision","!gemma"])
        send_signal_message(
            sender,
            f"1st Mate — Online\n"
            f"Tools: {len(TOOL_SCHEMAS)} available\n"
            f"Session messages: {history_count}\n"
            f"Default fallback: {OLLAMA_MODEL}\n\n"
            f"Agents (prefix message):\n{agents}\n\n"
            f"Commands: /start /clear /status"
        )
    elif command == "/tools":
        lines = ["🛠️ 1st Mate — Available Tools\n"]
        for t in TOOL_SCHEMAS:
            desc = t.get("description", "").split(".")[0]
            lines.append(f"• {t['name']} — {desc}")
        send_signal_message(sender, "\n".join(lines))
    else:
        send_signal_message(sender, f"Unknown command: {command}\nCommands: /start /clear /status /tools")


def resolve_agent(text: str) -> tuple[str, str, bool]:
    """Check for !agent prefix. Returns (model_name, cleaned_text, prefix_matched)."""
    first_word = text.strip().split()[0].lower() if text.strip() else ""
    if first_word in AGENT_MODELS:
        model = AGENT_MODELS[first_word]
        cleaned = text.strip()[len(first_word):].strip()
        return model, cleaned, True
    return OLLAMA_MODEL, text, False


def handle_message(sender: str, text: str, attachments: list):
    """Process an incoming message and send a reply."""
    if sender not in conversation_history:
        conversation_history[sender] = []

    # Resolve agent prefix
    ollama_model, clean_text, prefix_matched = resolve_agent(text)
    agent_tag = f" _[{ollama_model}]_" if ollama_model != OLLAMA_MODEL else ""
    is_vision = ollama_model == "1m-vision"

    # Filter to image attachments only
    image_attachments = [a for a in attachments if a.get("contentType", "").startswith("image/")]

    # Vision: image present — route to Claude multimodal
    if image_attachments:
        attachment_data = fetch_attachment_b64(image_attachments[0])
        if attachment_data:
            img_b64, img_type = attachment_data

            # Save to disk immediately so follow-up text commands can reference it
            saved_path = save_attachment_to_disk(img_b64, img_type)
            if saved_path:
                last_image[sender] = saved_path

            base_prompt = clean_text or ("Extract all content from this image and save as an Obsidian note in the appropriate homestead directory." if is_vision else "Describe this image.")
            # Tell Claude where the image lives so it can act on transfer requests
            path_note = f"\n\n[System: Image auto-saved to {saved_path} on dead-reckoning. Use this path if asked to copy, send, or move the file.]" if saved_path else ""
            prompt = base_prompt + path_note
            logger.info(f"Vision request from {sender}: {base_prompt[:80]}")
            try:
                reply = run_with_vision(prompt, img_b64, img_type)
                log_exchange(sender, f"[image] {base_prompt}", reply, MODEL, via_claude=True)
            except Exception as e:
                logger.warning(f"Vision via Claude failed: {e} — falling back to moondream")
                try:
                    client = ollama_client.Client(host=OLLAMA_HOST)
                    resp = client.chat(
                        model="1m-vision",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    reply = resp["message"]["content"] + "\n\n_(offline — moondream)_"
                    log_exchange(sender, f"[image] {prompt}", reply, "1m-vision", via_claude=False)
                except Exception as ollama_error:
                    logger.error(f"Vision both failed: {ollama_error}")
                    reply = "Vision unavailable. Check logs."
            send_signal_message(sender, reply)
            return
        else:
            send_signal_message(sender, "Couldn't retrieve the image. Try again.")
            return

    # No image — text only path
    if not clean_text:
        send_signal_message(sender, f"Using {ollama_model}. What do you need?")
        return

    # Inject last-image path if sender has one and message may reference it
    user_text = clean_text
    if last_image.get(sender) and any(w in clean_text.lower() for w in ["image", "picture", "photo", "screenshot", "that", "this", "send", "save", "file", "it", "copy", "move", "download"]):
        user_text += f"\n\n[System: Last received image is at {last_image[sender]} on dead-reckoning. Reference this path if the user is asking about a recent image or file.]"

    conversation_history[sender].append({"role": "user", "content": user_text})

    # Keep last 30 messages (15 exchanges)
    if len(conversation_history[sender]) > 30:
        conversation_history[sender] = conversation_history[sender][-30:]

    # !prefix → route directly to Ollama (free, local, no Claude charge)
    if prefix_matched:
        try:
            client = ollama_client.Client(host=OLLAMA_HOST)
            resp = client.chat(
                model=ollama_model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[sender]
            )
            reply = resp["message"]["content"] + f"\n\n_[{ollama_model}]_"
            conversation_history[sender].append({"role": "assistant", "content": reply})
            log_exchange(sender, clean_text, reply, ollama_model, via_claude=False)
            logger.info(f"Ollama direct route OK ({ollama_model})")
        except Exception as ollama_error:
            logger.error(f"Ollama direct route failed ({ollama_model}): {ollama_error}")
            reply = f"Agent {ollama_model} unavailable. Check logs."
        send_signal_message(sender, reply)
        return

    # No prefix → Claude API (tools, internet, vision)
    try:
        messages = list(conversation_history[sender])
        reply = run_with_tools(messages)
        conversation_history[sender].append({"role": "assistant", "content": reply})
        log_exchange(sender, clean_text, reply, MODEL, via_claude=True)
    except Exception as llm_error:
        logger.warning(f"LLM failed: {llm_error} — falling back to Ollama ({ollama_model})")
        try:
            client = ollama_client.Client(host=OLLAMA_HOST)
            resp = client.chat(
                model=ollama_model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[sender]
            )
            reply = resp["message"]["content"] + f"\n\n_(offline — {ollama_model}){agent_tag}_"
            conversation_history[sender].append({"role": "assistant", "content": reply})
            log_exchange(sender, clean_text, reply, ollama_model, via_claude=False)
            logger.info(f"Ollama fallback OK ({ollama_model})")
        except Exception as ollama_error:
            logger.error(f"Both failed: {ollama_error}")
            reply = "AI unavailable. Check logs."

    send_signal_message(sender, reply)


def main():
    if not SIGNAL_NUMBER:
        raise ValueError("SIGNAL_NUMBER not set")
    if not ALLOWED_NUMBER and not ALLOWED_UUID:
        raise ValueError("ALLOWED_NUMBER or ALLOWED_UUID must be set")
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY not set")

    logger.info(f"1st Mate starting — Signal {SIGNAL_NUMBER} — {len(TOOL_SCHEMAS)} tools loaded")
    load_history()

    while True:
        try:
            envelopes = receive_signal_messages()
            for item in envelopes:
                envelope = item.get("envelope", {})
                sender, text, attachments = extract_message(envelope)

                if not sender or (not text and not attachments):
                    continue
                if not is_authorized(sender):
                    logger.warning(f"Unauthorized message from {sender}")
                    continue

                # Default text to empty string if only attachments were sent
                text = text or ""
                logger.info(f"Message from {sender}: {text[:80]} ({len(attachments)} attachments)")

                set_current_sender(sender)
                if text.startswith("/"):
                    handle_command(sender, text.strip().split()[0])
                else:
                    handle_message(sender, text, attachments)

            # Deliver any due reminders
            for reminder in check_due_reminders():
                recipient = reminder.get("sender") or ALLOWED_NUMBER
                send_signal_message(recipient, f"⏰ Reminder: {reminder['message']}")
                logger.info(f"Reminder delivered to {recipient}: {reminder['message']}")

        except Exception as e:
            logger.error(f"Poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
