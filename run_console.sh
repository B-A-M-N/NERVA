#!/bin/bash
# NERVA Console Launcher
# Checks if Ollama is running and provides helpful messages

echo "╔════════════════════════════════════════════════════════╗"
echo "║         NERVA Console - Starting...                    ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

# Check if Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama is running at http://localhost:11434"
    echo "✓ Using real LLM for responses"
    echo
else
    echo "⚠ Ollama not detected at http://localhost:11434"
    echo
    echo "The console will use mock responses."
    echo
    echo "To use real LLM:"
    echo "  1. In another terminal: ollama serve"
    echo "  2. Pull model: ollama pull qwen3-vl:4-8b"
    echo "  3. Restart this console"
    echo
fi

echo "Launching NERVA Console..."
echo
echo "Controls:"
echo "  F1-F6: Switch tabs"
echo "  Ctrl+C: Quit"
echo
echo "════════════════════════════════════════════════════════"
echo

# Launch console
python -m nerva.console
