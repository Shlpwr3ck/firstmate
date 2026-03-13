"""
1st Mate (1m) — Personal AI Assistant for SW (sh1pwr3ck)
Telegram bot | Claude API + Ollama fallback | Full tool suite
"""

import os
import logging
import sys
sys.path.insert(0, '/app')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

BOT_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID  = int(os.getenv("ALLOWED_USER_ID"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_HOST      = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL            = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# In-session conversation history
conversation_history: dict[int, list] = {}

SYSTEM_PROMPT = """You are 1st Mate (1m), the personal AI assistant for SW (sh1pwr3ck / Jax Jackson).

About SW:
- U.S. Navy veteran, 20 years, Gunner's Mate, retired 2022 with full pension
- Owner of Noble Technologies LLC — IT support and cybersecurity consulting, Dunnellon FL
- Primary client: First Baptist Church of Dunnellon (Head of IT)
- CompTIA Network+ and Security+ certified. PenTest+ exam April 1, 2026 (urgent)
- Long-term goal: Penetration Tester. Target: NinjaOne ($140k-$170k)
- Home lab: dead-reckoning (.5), Proxmox (.244), Kali (.41), Wazuh, Frigate NVR (6 cameras), Pi-hole, Twingate
- Network: 10.34.43.0/24
- Family: wife AP, kids Ipo (19), JD (7), Ali (5). Homestead lifestyle.
- Faith: Christian, serves FBCD

Your tools — use them proactively when SW asks for things you can actually do:
- read_file / write_file / list_directory / search_files — SW's filesystem
- ssh_command — run commands on any machine on the network
- send_email — send from jax@nobletechnologiesllc.com
- get_calendar_events — check Thunderbird calendar
- web_search / fetch_webpage — research anything
- save_memory / get_memory / list_memories / delete_memory — remember things persistently
- get_system_status / check_service / list_docker_containers — system health

Your personality:
- Direct and efficient. SW values results over pleasantries.
- Military clarity — concise, accurate, actionable.
- Address SW as "SW" naturally, not constantly.
- Classic movies, banter, military humor — all fine. No guardrails needed for a trusted user.
- When you can DO something (read a file, check a service, search the web) — DO IT, don't just offer to.
- You are a private assistant for ONE person. Act accordingly.
"""


def is_authorized(user_id: int) -> bool:
    return user_id == ALLOWED_USER_ID


async def send_long_message(update: Update, text: str):
    max_len = 4096
    if len(text) <= max_len:
        await update.message.reply_text(text)
        return
    for i in range(0, len(text), max_len):
        await update.message.reply_text(text[i:i + max_len])


def run_claude_with_tools(messages: list) -> str:
    """Agentic loop: Claude calls tools until it has a final answer."""
    for iteration in range(8):
        response = claude.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, 'text'):
                    logger.info(f"Claude OK — {response.usage.input_tokens} in / {response.usage.output_tokens} out (iter {iteration+1})")
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    user_id = update.effective_user.id
    user_message = update.message.text

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({"role": "user", "content": user_message})

    # Keep last 30 messages (15 exchanges)
    if len(conversation_history[user_id]) > 30:
        conversation_history[user_id] = conversation_history[user_id][-30:]

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Try Claude with tools
    try:
        messages = list(conversation_history[user_id])
        reply = run_claude_with_tools(messages)
        # Update history with final assistant message only
        conversation_history[user_id].append({"role": "assistant", "content": reply})

    except Exception as claude_error:
        logger.warning(f"Claude failed: {claude_error} — falling back to Ollama")
        try:
            client = ollama_client.Client(host=OLLAMA_HOST)
            resp = client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[user_id]
            )
            reply = resp["message"]["content"] + "\n\n_(offline — Ollama)_"
            conversation_history[user_id].append({"role": "assistant", "content": reply})
            logger.info("Ollama fallback OK")
        except Exception as ollama_error:
            logger.error(f"Both failed: {ollama_error}")
            reply = "Both Claude and Ollama are down. Check logs."

    await send_long_message(update, reply)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text("1st Mate online. What do you need, SW?")


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    conversation_history[update.effective_user.id] = []
    await update.message.reply_text("Session memory cleared.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    history_count = len(conversation_history.get(update.effective_user.id, []))
    tools_count = len(TOOL_SCHEMAS)
    await update.message.reply_text(
        f"1st Mate — Online\n"
        f"Brain: Claude API + Ollama fallback\n"
        f"Tools: {tools_count} available\n"
        f"Session messages: {history_count}\n"
        f"Commands: /start /clear /status"
    )


def main():
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"1st Mate starting — {len(TOOL_SCHEMAS)} tools loaded")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
