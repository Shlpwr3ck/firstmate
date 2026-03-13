"""Email tool — send via msmtp."""
import subprocess
import tempfile
import os


def send_email(to: str, subject: str, body: str) -> str:
    try:
        msg = f"To: {to}\nSubject: {subject}\nFrom: jax@nobletechnologiesllc.com\n\n{body}"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(msg)
            tmp = f.name
        result = subprocess.run(
            ['msmtp', '-a', 'default', to],
            stdin=open(tmp), capture_output=True, text=True
        )
        os.unlink(tmp)
        if result.returncode == 0:
            return f"Email sent to {to} — Subject: {subject}"
        return f"Send failed: {result.stderr}"
    except FileNotFoundError:
        return "msmtp not found in container — email not available"
    except Exception as e:
        return f"Error sending email: {e}"
