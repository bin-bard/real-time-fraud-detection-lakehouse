#!/bin/bash
set -e

# Kiểm tra biến môi trường MODE
if [ "$MODE" = "idle" ]; then
    echo "🛑 IDLE MODE: Container running but not processing data"
    echo "   To bulk load: docker exec data-producer python producer.py --bulk-load 50000"
    echo "   To stream: docker exec data-producer python producer.py"
    tail -f /dev/null
else
    echo "🔄 STREAMING MODE: Starting real-time data producer..."
    exec python producer.py "$@"
fi
