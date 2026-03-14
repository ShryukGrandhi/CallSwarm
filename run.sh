#!/bin/bash
# CallSwarm - Start both backend and frontend

echo "=== CallSwarm ==="
echo ""

# Check for .env
if [ ! -f .env ]; then
    echo "WARNING: No .env file found. Copy .env.example to .env and fill in your API keys."
    echo ""
fi

# Start backend
echo "Starting backend on http://localhost:8000 ..."
python3 -m uvicorn callswarm.api.server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend
echo "Starting dashboard on http://localhost:5173 ..."
cd dashboard && npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend PID: $BACKEND_PID"
echo "Dashboard PID: $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop both services."

# Trap Ctrl+C to kill both
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
