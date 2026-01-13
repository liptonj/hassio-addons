#!/bin/bash
# VS Code Python Setup Helper
# Run this if you're seeing import errors in VS Code

echo "🔧 Setting up Python environment for VS Code..."
echo ""

# Check if venv exists
if [ ! -d "backend/.venv" ]; then
    echo "❌ Virtual environment not found at backend/.venv"
    echo "   Creating it now..."
    cd backend
    uv venv
    uv sync --all-groups
    cd ..
fi

# Check Python version
echo "✅ Python interpreter:"
backend/.venv/bin/python --version

# Check installed packages
echo ""
echo "✅ Key packages installed:"
backend/.venv/bin/python -c "import fastapi; print(f'  FastAPI: {fastapi.__version__}')"
backend/.venv/bin/python -c "import pydantic; print(f'  Pydantic: {pydantic.__version__}')"
backend/.venv/bin/python -c "import cryptography; print(f'  Cryptography: {cryptography.__version__}')"

echo ""
echo "📝 VS Code Configuration:"
echo "  - Python interpreter: backend/.venv/bin/python"
echo "  - Pylint config: backend/.pylintrc"
echo "  - Pyright config: backend/pyrightconfig.json"

echo ""
echo "🎯 Next steps:"
echo "  1. In VS Code, press Cmd+Shift+P (Mac) or Ctrl+Shift+P (Windows/Linux)"
echo "  2. Type: 'Python: Select Interpreter'"
echo "  3. Choose: './backend/.venv/bin/python'"
echo "  4. Reload VS Code window: Cmd+Shift+P → 'Developer: Reload Window'"
echo ""
echo "✨ Import errors should disappear after reloading!"
