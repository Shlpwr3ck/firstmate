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

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SIGNAL_API_URL      = os.getenv("SIGNAL_API_URL", "http://localhost:8080")
SIGNAL_NUMBER       = os.getenv("SIGNAL_NUMBER")       # bot's number e.g. +13526918580
ALLOWED_NUMBER      = os.getenv("ALLOWED_NUMBER")       # your personal Signal number
ALLOWED_UUID        = os.getenv("ALLOWED_UUID")         # your Signal UUID (used when sourceNumber is absent)
LLM_API_KEY         = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
OLLAMA_MODEL        = os.getenv("OLLAMA_MODEL", "1m-coder")
OLLAMA_HOST         = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL               = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
POLL_INTERVAL       = int(os.getenv("POLL_INTERVAL", "2"))  # seconds
CONV_LOG            = os.path.join(os.path.dirname(__file__), "memory", "conversation_log.jsonl")

# Agent routing — prefix a message with !agent to invoke a specific local model
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
}

llm = anthropic.Anthropic(api_key=LLM_API_KEY)

# In-session conversation history keyed by sender number
conversation_history: dict[str, list] = {}


def log_exchange(user_msg: str, assistant_msg: str, model: str, via_claude: bool):
    """Append a conversation exchange to the JSONL log file."""
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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


SYSTEM_PROMPT = """You are 1st Mate (1m), a personal AI assistant for a home lab and small business owner.

Context:
- Owner of a small IT consulting and cybersecurity firm (Noble Technologies LLC)
- Manages a home lab with multiple Linux servers, a Proxmox hypervisor, Kali, Wazuh SIEM, Frigate NVR, Pi-hole, and Twingate
- CompTIA Network+ and Security+ certified, pursuing PenTest+

Your tools — use them proactively when asked for things you can actually do:
- read_file / write_file / list_directory / search_files — filesystem access
- ssh_command — run commands on any machine on the home network
- send_email — send email via configured SMTP
- get_calendar_events — check calendar
- web_search / fetch_webpage — research anything
- save_memory / get_memory / list_memories / delete_memory — remember things persistently
- get_system_status / check_service / list_docker_containers — system health
- github — manage GitHub repos and profile via gh CLI

Vision tasks (!vision prefix or image sent with message):
- Extract all useful content from the image
- For social media posts: pull the text, author, topic, and any actionable info
- Format as a clean Obsidian markdown note with relevant tags
- Obsidian paths: homestead content → /home/sh1pwr3ck/homestead/
  - food forest, plants, seeds → /home/sh1pwr3ck/homestead/food-forest/
  - garden, vegetables → /home/sh1pwr3ck/homestead/vegetable-garden/
  - general homestead notes → /home/sh1pwr3ck/homestead/
- If the content topic is unclear, ask before saving
- Use write_file to save the note automatically — don't just describe it, save it

Your personality:
- Direct and efficient. Results over pleasantries.
- Military clarity — concise, accurate, actionable.
- When you can DO something (read a file, check a service, search the web) — DO IT, don't just offer to.
- You are a private assistant for ONE person. Act accordingly.
"""


def is_authorized(sender: str) -> bool:
    return sender in filter(None, [ALLOWED_NUMBER, ALLOWED_UUID])


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
    for iteration in range(8):
        response = llm.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
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
    for iteration in range(8):
        response = llm.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
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
        agents = "\n".join(f"  {k} → {v}" for k, v in AGENT_MODELS.items() if k in ["!nhn","!sec","!code","!reason","!assist","!coach","!vision"])
        send_signal_message(
            sender,
            f"1st Mate — Online\n"
            f"Tools: {len(TOOL_SCHEMAS)} available\n"
            f"Session messages: {history_count}\n"
            f"Default fallback: {OLLAMA_MODEL}\n\n"
            f"Agents (prefix message):\n{agents}\n\n"
            f"Commands: /start /clear /status"
        )
    else:
        send_signal_message(sender, f"Unknown command: {command}")


def resolve_agent(text: str) -> tuple[str, str]:
    """Check for !agent prefix. Returns (model_name, cleaned_text)."""
    first_word = text.strip().split()[0].lower() if text.strip() else ""
    if first_word in AGENT_MODELS:
        model = AGENT_MODELS[first_word]
        cleaned = text.strip()[len(first_word):].strip()
        return model, cleaned
    return OLLAMA_MODEL, text


def handle_message(sender: str, text: str, attachments: list):
    """Process an incoming message and send a reply."""
    if sender not in conversation_history:
        conversation_history[sender] = []

    # Resolve agent prefix
    ollama_model, clean_text = resolve_agent(text)
    agent_tag = f" _[{ollama_model}]_" if ollama_model != OLLAMA_MODEL else ""
    is_vision = ollama_model == "1m-vision"

    # Filter to image attachments only
    image_attachments = [a for a in attachments if a.get("contentType", "").startswith("image/")]

    # Vision: image present — route to Claude multimodal
    if image_attachments:
        attachment_data = fetch_attachment_b64(image_attachments[0])
        if attachment_data:
            img_b64, img_type = attachment_data
            prompt = clean_text or ("Extract all content from this image and save as an Obsidian note in the appropriate homestead directory." if is_vision else "Describe this image.")
            logger.info(f"Vision request from {sender}: {prompt[:80]}")
            try:
                reply = run_with_vision(prompt, img_b64, img_type)
                log_exchange(f"[image] {prompt}", reply, MODEL, via_claude=True)
            except Exception as e:
                logger.warning(f"Vision via Claude failed: {e} — falling back to moondream")
                try:
                    client = ollama_client.Client(host=OLLAMA_HOST)
                    resp = client.chat(
                        model="1m-vision",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    reply = resp["message"]["content"] + "\n\n_(offline — moondream)_"
                    log_exchange(f"[image] {prompt}", reply, "1m-vision", via_claude=False)
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

    conversation_history[sender].append({"role": "user", "content": clean_text})

    # Keep last 30 messages (15 exchanges)
    if len(conversation_history[sender]) > 30:
        conversation_history[sender] = conversation_history[sender][-30:]

    try:
        messages = list(conversation_history[sender])
        reply = run_with_tools(messages)
        conversation_history[sender].append({"role": "assistant", "content": reply})
        log_exchange(clean_text, reply, MODEL, via_claude=True)
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
            log_exchange(clean_text, reply, ollama_model, via_claude=False)
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

                if text.startswith("/"):
                    handle_command(sender, text.strip().split()[0])
                else:
                    handle_message(sender, text, attachments)

        except Exception as e:
            logger.error(f"Poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
