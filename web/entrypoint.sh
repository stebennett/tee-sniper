#!/bin/sh
set -e
: "${API_BASE_URL:=}"
cat > /usr/share/nginx/html/config.js <<EOF
window.__TSA_CONFIG__ = { apiBaseUrl: "${API_BASE_URL}" };
EOF
exec nginx -g 'daemon off;'
