#!/bin/bash
# Start the Flask backend with optimized settings

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Use /tmp for database to avoid network drive locking issues
export DATABASE_URL="sqlite:////tmp/transport.db"
export FLASK_APP=app.py
export FLASK_ENV=development

echo "Starting Flask backend..."
echo "- Database: /tmp/transport.db"
echo "- API: http://localhost:5000"

# Run without debugger/reload to prevent hanging
flask run --host=0.0.0.0 --port=5000 --no-debugger --no-reload
