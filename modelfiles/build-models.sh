#!/bin/bash
# Build custom 1m Ollama model variants
# Run after all base models are pulled

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

build() {
    local name=$1
    local file=$2
    echo "Building 1m-${name}..."
    ollama create "1m-${name}" -f "${SCRIPT_DIR}/Modelfile.${name}"
    echo "1m-${name} ready"
}

echo "Waiting for base models..."
for model in qwen2.5-coder:7b deepseek-r1:7b dolphin3:8b moondream:latest; do
    while ! ollama list | grep -q "${model%%:*}"; do
        sleep 10
    done
    echo "  $model confirmed"
done

echo "All base models present — building custom variants..."
build coder
build reason
build sec
build vision
build nhn
build assist
build coach

echo ""
echo "Done. Active 1m models:"
ollama list | grep "1m-"

# Notify via Signal
curl -s -X POST http://localhost:8080/v2/send \
  -H "Content-Type: application/json" \
  -d '{
    "message": "1st Mate ready. All local models built:\n- 1m-coder (qwen2.5-coder:7b)\n- 1m-reason (deepseek-r1:7b)\n- 1m-sec (dolphin3:8b)\n- 1m-vision (moondream)\n- 1m-nhn (dolphin3:8b)\n- 1m-assist (deepseek-r1:7b)\n- 1m-coach (dolphin3:8b)\n\nAll agents online. You are offline-capable.",
    "number": "+13526918580",
    "recipients": ["+18138934620"]
  }' && echo "Signal notification sent"
