"""Tool registry — schemas for LLM tool use + dispatcher."""
from .filesystem import read_file, write_file, list_directory, search_files
from .ssh_tool import ssh_command
from .email_tool import send_email
from .calendar_tool import get_calendar_events
from .calendar_write import create_calendar_event
from .calendar_replace import replace_calendar
from .search import web_search, fetch_webpage
from .memory import save_memory, get_memory, list_memories, delete_memory
from .system import get_system_status, check_service, list_docker_containers
from .github_tool import github
from .signal_tool import send_signal_file
from .frigate_tool import frigate_snapshot

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
        "name": "create_calendar_event",
        "description": "Add an event to a subscribable ICS calendar hosted at http://10.34.43.11:8088/{calendar_name}.ics. iPhone subscribes to this URL for live updates. Use calendar_name='workouts' for fitness events.",
        "input_schema": {"type": "object", "properties": {
            "calendar_name": {"type": "string", "description": "Calendar file name without .ics, e.g. 'workouts'"},
            "summary": {"type": "string", "description": "Event title"},
            "start_dt": {"type": "string", "description": "Start datetime: YYYY-MM-DD HH:MM (Eastern)"},
            "end_dt": {"type": "string", "description": "End datetime: YYYY-MM-DD HH:MM (Eastern)"},
            "description": {"type": "string", "description": "Event details or workout instructions"},
            "recurrence": {"type": "string", "description": "Optional RRULE e.g. FREQ=WEEKLY;BYDAY=MO,WE,FR"}
        }, "required": ["calendar_name", "summary", "start_dt", "end_dt"]}
    },
    {
        "name": "replace_calendar",
        "description": "Completely replace a calendar ICS file on the server. Use this for weekly workout updates — generate full valid ICS content and push it. calendar_name='workouts' for the fitness calendar.",
        "input_schema": {"type": "object", "properties": {
            "calendar_name": {"type": "string", "description": "Calendar name without .ics"},
            "ics_content": {"type": "string", "description": "Complete valid ICS file content as a string"}
        }, "required": ["calendar_name", "ics_content"]}
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
        "name": "frigate_snapshot",
        "description": "Fetch the latest snapshot from a Frigate NVR camera and send it to Jax via Signal. Cameras: front (doorbell), garage, office, kitchen, safe, backdoor.",
        "input_schema": {"type": "object", "properties": {
            "camera": {"type": "string", "description": "Camera name: front, garage, office, kitchen, safe, or backdoor"}
        }, "required": ["camera"]}
    },
    {
        "name": "send_signal_file",
        "description": "Send a file from the filesystem as a Signal attachment to Jax. Use this when asked to 'send', 'pull', 'share', or 'grab' a file. The file lands in Signal as a downloadable attachment.",
        "input_schema": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Absolute path to the file to send"},
            "caption": {"type": "string", "description": "Optional message to accompany the file"}
        }, "required": ["path"]}
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
        "create_calendar_event": lambda i: create_calendar_event(i["calendar_name"], i["summary"], i["start_dt"], i["end_dt"], i.get("description",""), i.get("recurrence","")),
        "replace_calendar":      lambda i: replace_calendar(i["calendar_name"], i["ics_content"]),
        "web_search":            lambda i: web_search(i["query"]),
        "fetch_webpage":         lambda i: fetch_webpage(i["url"]),
        "save_memory":           lambda i: save_memory(i["key"], i["value"]),
        "get_memory":            lambda i: get_memory(i["key"]),
        "list_memories":         lambda i: list_memories(),
        "delete_memory":         lambda i: delete_memory(i["key"]),
        "github":                lambda i: github(i["command"]),
        "send_signal_file":      lambda i: send_signal_file(i["path"], i.get("caption", "")),
        "frigate_snapshot":      lambda i: frigate_snapshot(i["camera"]),
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
