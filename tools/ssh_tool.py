"""SSH tool — reach any machine on SW's network."""
import subprocess

HOSTS = {
    'dead-reckoning': ('sh1pwr3ck', '10.34.43.5'),
    'macbook':        ('sh1pwr3ck', '10.34.43.7'),
    'mint':           ('sh1pwr3ck', '10.34.43.9'),
    'ubuntuserver':   ('root',       '10.34.43.11'),
    'noble-wordpress':('root',       '10.34.43.12'),
    'frigate':        ('sh1pwr3ck', '10.34.43.31'),
    'kali':           ('sh1pwr3ck', '10.34.43.41'),
    'hacktop':        ('sh1pwr3ck', '10.34.43.45'),
    'proxmox':        ('root',       '10.34.43.244'),
    'linode':         ('root',       '194.195.212.217'),
}

SSH_OPTS = [
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=10',
    '-o', 'BatchMode=yes',
    '-i', '/home/sh1pwr3ck/.ssh/id_rsa',
]


def ssh_command(host: str, command: str, timeout: int = 30) -> str:
    if host not in HOSTS:
        return f"Unknown host '{host}'. Available: {', '.join(HOSTS.keys())}"
    user, ip = HOSTS[host]
    try:
        result = subprocess.run(
            ['ssh'] + SSH_OPTS + [f'{user}@{ip}', command],
            capture_output=True, text=True, timeout=timeout
        )
        out = (result.stdout + result.stderr).strip()
        if len(out) > 3000:
            out = out[:3000] + '\n[...truncated]'
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"SSH timed out after {timeout}s"
    except Exception as e:
        return f"SSH error: {e}"
