# 1st Mate (1m)

Personal AI assistant for sh1pwr3ck. Telegram bot powered by **Claude API** with **Ollama** local fallback and a full tool suite for managing a home network and homestead.

## Features

- **Agentic tool loop** — Claude calls tools, gets results, and keeps going until it has an answer
- **Ollama fallback** — drops to local LLM if Claude API is unavailable
- **Session memory** — 30-message conversation history per session
- **Persistent memory** — save/recall facts across restarts

## Tools

| Tool | Description |
|---|---|
| `ssh_command` | Run commands on any machine on the home network |
| `read_file` / `write_file` | Read and write files on the home server |
| `list_directory` / `search_files` | Browse the filesystem |
| `send_email` | Send email from Noble Technologies address via msmtp |
| `get_calendar_events` | Read Thunderbird calendar (SQLite) |
| `web_search` | DuckDuckGo search |
| `fetch_webpage` | Fetch and read web page content |
| `save_memory` / `get_memory` | Persistent key-value memory |
| `list_memories` / `delete_memory` | Memory management |
| `get_system_status` | System health — uptime, disk, memory |
| `check_service` | Check systemd service status |
| `list_docker_containers` | List running Docker containers |

## Stack

- Python 3.12
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v21
- [Anthropic Claude API](https://docs.anthropic.com/) (claude-haiku-4-5)
- [Ollama](https://ollama.ai/) (llama3.2 fallback)
- Docker + docker-compose

## Setup

1. Copy `.env.example` to `.env` and fill in your values
2. `docker compose up -d --build`

## Environment Variables

```
TELEGRAM_BOT_TOKEN=     # From @BotFather
ALLOWED_USER_ID=        # Your Telegram user ID
ANTHROPIC_API_KEY=      # From console.anthropic.com
CLAUDE_MODEL=           # Default: claude-haiku-4-5-20251001
OLLAMA_HOST=            # Default: http://127.0.0.1:11434
OLLAMA_MODEL=           # Default: llama3.2
```

## Architecture

```
Telegram → handle_message()
              ↓
         run_claude_with_tools()  ← agentic loop (max 8 iterations)
              ↓
         Claude API (tool_use)
              ↓
         execute_tool()  → filesystem / ssh / email / etc.
              ↓
         feed results back → Claude → end_turn → reply
              ↓ (on Claude failure)
         Ollama fallback (no tools)
```

---

Built by [Jax Jackson / Noble Technologies LLC](https://nobletechnologiesllc.com)
