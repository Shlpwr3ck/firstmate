"""System status tools — dead-reckoning health."""
import subprocess


def get_system_status() -> str:
    try:
        uptime = subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip()
        disk = subprocess.run(['df', '-h', '/'], capture_output=True, text=True).stdout.strip()
        mem = subprocess.run(['free', '-h'], capture_output=True, text=True).stdout.strip()
        return f"Uptime: {uptime}\n\nDisk:\n{disk}\n\nMemory:\n{mem}"
    except Exception as e:
        return f"Error: {e}"


def check_service(service: str) -> str:
    try:
        result = subprocess.run(['systemctl', 'is-active', service],
                                capture_output=True, text=True)
        return f"{service}: {result.stdout.strip()}"
    except Exception as e:
        return f"Error: {e}"


def list_docker_containers() -> str:
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Image}}'],
            capture_output=True, text=True
        )
        return result.stdout.strip() or "No containers running"
    except Exception as e:
        return f"Error: {e}"
