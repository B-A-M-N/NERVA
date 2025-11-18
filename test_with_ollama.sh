#!/bin/bash
# Test NERVA with Ollama

echo "Testing Ollama connection..."

if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Ollama is not running"
    echo ""
    echo "Start it with: ollama serve"
    echo "Then run this script again"
    exit 1
fi

echo "✓ Ollama is running"
echo ""

echo "Checking for models..."
MODELS=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

if [ -z "$MODELS" ]; then
    echo "❌ No models found"
    echo ""
    echo "Pull a model first:"
    echo "  ollama pull llama3"
    echo ""
    exit 1
fi

echo "Available models:"
echo "$MODELS" | while read model; do
    echo "  - $model"
done
echo ""

# Get first model
FIRST_MODEL=$(echo "$MODELS" | head -1)
echo "Testing with model: $FIRST_MODEL"
echo ""

# Update config temporarily
cp nerva/config.py nerva/config.py.backup
sed -i "s/qwen_model: str = \".*\"/qwen_model: str = \"$FIRST_MODEL\"/" nerva/config.py

echo "Running chat..."
python chat.py "What is NERVA?" 2>&1 | head -20

# Restore config
mv nerva/config.py.backup nerva/config.py

echo ""
echo "✓ Test complete!"
echo ""
echo "To use NERVA with your model:"
echo "  python chat.py"
