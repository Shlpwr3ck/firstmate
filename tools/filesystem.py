"""File system access — restricted to the configured home directory."""
import os
import glob as glob_module

ALLOWED_BASE = os.getenv("HOME", "/home/user")

BLOCKED = [
    os.path.join(ALLOWED_BASE, 'firstmate/.env'),
    os.path.join(ALLOWED_BASE, '.msmtprc'),
    os.path.join(ALLOWED_BASE, '.ssh/id_rsa'),
    os.path.join(ALLOWED_BASE, '.ssh/id_ed25519'),
]


def _allowed(path: str) -> bool:
    p = os.path.realpath(path)
    for b in BLOCKED:
        if p == os.path.realpath(b) or p.startswith(os.path.realpath(b)):
            return False
    return p.startswith(ALLOWED_BASE)


def read_file(path: str) -> str:
    if not _allowed(path):
        return f"Access denied: {path}"
    try:
        with open(path, 'r', errors='replace') as f:
            content = f.read()
        if len(content) > 8000:
            return content[:8000] + f"\n\n[...truncated — {len(content)} total chars]"
        return content
    except Exception as e:
        return f"Error reading {path}: {e}"


def write_file(path: str, content: str) -> str:
    if not _allowed(path):
        return f"Access denied: {path}"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return f"Written: {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


def list_directory(path: str) -> str:
    if not _allowed(path):
        return f"Access denied: {path}"
    try:
        entries = sorted(os.listdir(path))
        lines = []
        for e in entries:
            full = os.path.join(path, e)
            if os.path.isdir(full):
                lines.append(f"[DIR]  {e}/")
            else:
                lines.append(f"[FILE] {e}  ({os.path.getsize(full):,} bytes)")
        return '\n'.join(lines) if lines else "Empty directory"
    except Exception as e:
        return f"Error: {e}"


def search_files(directory: str, pattern: str) -> str:
    if not _allowed(directory):
        return f"Access denied: {directory}"
    try:
        matches = glob_module.glob(os.path.join(directory, '**', pattern), recursive=True)
        matches = [m for m in matches if _allowed(m)]
        if not matches:
            return f"No files found matching '{pattern}' in {directory}"
        return '\n'.join(sorted(matches)[:50])
    except Exception as e:
        return f"Error: {e}"
