#!/bin/bash
# Run this whenever your Mac switches networks (WiFi ↔ hotspot).
# It detects the current LAN IP and rewrites .env automatically.

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)

if [ -z "$IP" ]; then
  echo "❌ Could not detect LAN IP. Are you connected to a network?"
  exit 1
fi

cat > "$(dirname "$0")/.env" <<EOF
EXPO_PUBLIC_API_URL=http://${IP}:8080
EXPO_PUBLIC_DERMAI_URL=http://${IP}:8000
EOF

echo "✅ .env updated → IP: $IP"
echo "   API:    http://${IP}:8080"
echo "   DermAI: http://${IP}:8000"
echo ""
echo "Restart Metro now: npx expo start --clear"
