"""Tool registry — schemas for Claude + dispatcher."""
from .filesystem import read_file, write_file, list_directory, search_files
from .ssh_tool import ssh_command
from .email_tool import send_email
from .calendar_tool import get_calendar_events
from .search import web_search, fetch_webpage
from .memory import save_memory, get_memory, list_memories, delete_memory
from .system import get_system_status, check_service, list_docker_containers
from .github_tool import github

TOOL_SCHEMAS = [
    {
        "name": "read_file",
        "description": "Read a file from SW's filesystem on dead-reckoning.",
        "input_schema": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Absolute file path"}
        }, "required": ["path"]}
    },
    {
        "name": "write_file",
        "description": "Write or update a file on dead-reckoning.",
        "input_schema": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"}
        }, "required": ["path", "content"]}
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory on dead-reckoning.",
        "input_schema": {"type": "object", "properties": {
            "path": {"type": "string"}
        }, "required": ["path"]}
    },
    {
        "name": "search_files",
        "description": "Search for files matching a glob pattern recursively.",
        "input_schema": {"type": "object", "properties": {
            "directory": {"type": "string"},
            "pattern": {"type": "string", "description": "Glob pattern e.g. *.md"}
        }, "required": ["directory", "pattern"]}
    },
    {
        "name": "ssh_command",
        "description": "Run a shell command on a remote machine via SSH. Hosts: dead-reckoning, macbook, kali, hacktop, proxmox, frigate, ubuntuserver, noble-wordpress, linode, mint.",
        "input_schema": {"type": "object", "properties": {
            "host": {"type": "string"},
            "command": {"type": "string"}
        }, "required": ["host", "command"]}
    },
    {
        "name": "send_email",
        "description": "Send an email from jax@nobletechnologiesllc.com via msmtp.",
        "input_schema": {"type": "object", "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"}
        }, "required": ["to", "subject", "body"]}
    },
    {
        "name": "get_calendar_events",
        "description": "Get upcoming calendar events from Thunderbird.",
        "input_schema": {"type": "object", "properties": {
            "days_ahead": {"type": "integer", "description": "How many days to look ahead (default 7)"}
        }, "required": []}
    },
    {
        "name": "web_search",
        "description": "Search the web via DuckDuckGo.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string"}
        }, "required": ["query"]}
    },
    {
        "name": "fetch_webpage",
        "description": "Fetch and read the text content of a webpage.",
        "input_schema": {"type": "object", "properties": {
            "url": {"type": "string"}
        }, "required": ["url"]}
    },
    {
        "name": "save_memory",
        "description": "Save something to persistent memory that survives restarts. Use this when SW asks you to remember something.",
        "input_schema": {"type": "object", "properties": {
            "key": {"type": "string", "description": "Short descriptive key"},
            "value": {"type": "string", "description": "What to remember"}
        }, "required": ["key", "value"]}
    },
    {
        "name": "get_memory",
        "description": "Retrieve a saved memory by key.",
        "input_schema": {"type": "object", "properties": {
            "key": {"type": "string"}
        }, "required": ["key"]}
    },
    {
        "name": "list_memories",
        "description": "List all saved persistent memories.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "delete_memory",
        "description": "Delete a saved memory by key.",
        "input_schema": {"type": "object", "properties": {
            "key": {"type": "string"}
        }, "required": ["key"]}
    },
    {
        "name": "github",
        "description": "Run a gh CLI command against GitHub. Examples: 'repo list', 'pr list', 'issue create', 'repo view Shlpwr3ck/firstmate'.",
        "input_schema": {"type": "object", "properties": {
            "command": {"type": "string", "description": "gh CLI arguments, e.g. 'repo list' or 'api user'"}
        }, "required": ["command"]}
    },
    {
        "name": "get_system_status",
        "description": "Get dead-reckoning system health: uptime, disk, memory.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "check_service",
        "description": "Check if a systemd service is active on dead-reckoning.",
        "input_schema": {"type": "object", "properties": {
            "service": {"type": "string"}
        }, "required": ["service"]}
    },
    {
        "name": "list_docker_containers",
        "description": "List all running Docker containers on dead-reckoning.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
]


def execute_tool(name: str, inputs: dict) -> str:
    dispatch = {
        "read_file":             lambda i: read_file(i["path"]),
        "write_file":            lambda i: write_file(i["path"], i["content"]),
        "list_directory":        lambda i: list_directory(i["path"]),
        "search_files":          lambda i: search_files(i["directory"], i["pattern"]),
        "ssh_command":           lambda i: ssh_command(i["host"], i["command"]),
        "send_email":            lambda i: send_email(i["to"], i["subject"], i["body"]),
        "get_calendar_events":   lambda i: get_calendar_events(i.get("days_ahead", 7)),
        "web_search":            lambda i: web_search(i["query"]),
        "fetch_webpage":         lambda i: fetch_webpage(i["url"]),
        "save_memory":           lambda i: save_memory(i["key"], i["value"]),
        "get_memory":            lambda i: get_memory(i["key"]),
        "list_memories":         lambda i: list_memories(),
        "delete_memory":         lambda i: delete_memory(i["key"]),
        "github":                lambda i: github(i["command"]),
        "get_system_status":     lambda i: get_system_status(),
        "check_service":         lambda i: check_service(i["service"]),
        "list_docker_containers": lambda i: list_docker_containers(),
    }
    if name not in dispatch:
        return f"Unknown tool: {name}"
    try:
        return dispatch[name](inputs)
    except Exception as e:
        return f"Tool error ({name}): {e}"
