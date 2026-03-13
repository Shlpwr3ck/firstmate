# 1st Mate (1m)

Personal AI assistant for home lab and small business management. Telegram bot powered by an **LLM API** with **Ollama** local fallback and a full tool suite for managing a home network.

## Features

- **Agentic tool loop** — LLM calls tools, gets results, and keeps going until it has an answer
- **Ollama fallback** — drops to local LLM if the API is unavailable
- **Session memory** — 30-message conversation history per session
- **Persistent memory** — save/recall facts across restarts

## Tools

| Tool | Description |
|---|---|
| `ssh_command` | Run commands on any machine on the home network |
| `read_file` / `write_file` | Read and write files on the home server |
| `list_directory` / `search_files` | Browse the filesystem |
| `send_email` | Send email via msmtp |
| `get_calendar_events` | Read Thunderbird calendar (SQLite) |
| `web_search` | DuckDuckGo search |
| `fetch_webpage` | Fetch and read web page content |
| `github` | Manage GitHub repos via gh CLI |
| `save_memory` / `get_memory` | Persistent key-value memory |
| `list_memories` / `delete_memory` | Memory management |
| `get_system_status` | System health — uptime, disk, memory |
| `check_service` | Check systemd service status |
| `list_docker_containers` | List running Docker containers |

## Stack

- Python 3.12
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v21
- LLM API — default: haiku
- [Ollama](https://ollama.ai/) (llama3.2 fallback)
- Docker + docker-compose

## Setup

1. Copy `.env.example` to `.env` and fill in your values
2. `docker compose up -d --build`

## Environment Variables

```
TELEGRAM_BOT_TOKEN=     # From @BotFather
ALLOWED_USER_ID=        # Your Telegram user ID
LLM_API_KEY=            # LLM provider API key
LLM_MODEL=              # Default: claude-haiku-4-5-20251001
OLLAMA_HOST=            # Default: http://127.0.0.1:11434
OLLAMA_MODEL=           # Default: llama3.2
GITHUB_TOKEN=           # GitHub PAT for gh CLI tool
GITHUB_USER=            # Your GitHub username
HOSTS_CONFIG=           # JSON: {"hostname": ["user", "ip"]}
```

## Architecture

```
Telegram → handle_message()
              ↓
         run_with_tools()  ← agentic loop (max 8 iterations)
              ↓
         LLM API (tool_use)
              ↓
         execute_tool()  → filesystem / ssh / email / etc.
              ↓
         feed results back → LLM → end_turn → reply
              ↓ (on API failure)
         Ollama fallback (no tools)
```

---

Built by [Jax Jackson / Noble Technologies LLC](https://nobletechnologiesllc.com)
