"""
1st Mate (1m) — Personal AI Assistant
Signal bot | LLM API + Ollama fallback | Full tool suite
"""

import os
import time
import logging
import requests
import anthropic
import ollama as ollama_client
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

# Agent routing — prefix a message with !agent to invoke a specific local model
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
    "!vision": "1m-vision",   # image/visual analysis
}

llm = anthropic.Anthropic(api_key=LLM_API_KEY)

# In-session conversation history keyed by sender number
conversation_history: dict[str, list] = {}

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


def extract_message(envelope: dict) -> tuple[str | None, str | None]:
    """Extract sender number and message text from a signal-cli envelope."""
    sender = envelope.get("sourceNumber") or envelope.get("source")
    data = envelope.get("dataMessage", {})
    text = data.get("message")
    return sender, text


def run_with_tools(messages: list) -> str:
    """Agentic loop: LLM calls tools until it has a final answer."""
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


def handle_message(sender: str, text: str):
    """Process an incoming message and send a reply."""
    if sender not in conversation_history:
        conversation_history[sender] = []

    # Resolve agent prefix before storing in history
    ollama_model, clean_text = resolve_agent(text)
    agent_tag = f" _[{ollama_model}]_" if ollama_model != OLLAMA_MODEL else ""

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
                sender, text = extract_message(envelope)

                if not sender or not text:
                    continue
                if not is_authorized(sender):
                    logger.warning(f"Unauthorized message from {sender}")
                    continue

                logger.info(f"Message from {sender}: {text[:80]}")

                if text.startswith("/"):
                    handle_command(sender, text.strip().split()[0])
                else:
                    handle_message(sender, text)

        except Exception as e:
            logger.error(f"Poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
