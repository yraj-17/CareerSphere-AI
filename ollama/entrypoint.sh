#!/bin/bash

set -e

echo "Starting Ollama..."

ollama serve &

OLLAMA_PID=$!

echo "Waiting for Ollama server..."

until ollama list > /dev/null 2>&1; do
    sleep 2
done

echo "Ollama server is ready."

echo "Checking qwen3.5:9b..."

if ! ollama list | grep -q "qwen3.5:9b"; then
    echo "Downloading qwen3.5:9b..."
    ollama pull qwen3.5:9b
else
    echo "qwen3.5:9b already exists."
fi

echo "Ollama is ready!"

wait $OLLAMA_PID