FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    openssh-client \
    msmtp \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 firstmate

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY tools/ tools/

USER firstmate

CMD ["python", "main.py"]
