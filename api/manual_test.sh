#!/usr/bin/env bash
# =============================================================================
# Tee Sniper API - Manual Test Script
#
# Prerequisites:
#   1. Docker running (for Redis)
#   2. A .env file configured with real TSA_SHARED_SECRET and TSA_BASE_URL
#   3. Valid booking site credentials (member ID + PIN)
#
# Usage:
#   1. Start the stack:    docker-compose up -d
#   2. Run this script:    ./api/manual_test.sh
#   3. Follow the prompts
# =============================================================================

set -euo pipefail

API_BASE="http://localhost:8000"
TOKEN=""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

header() { echo -e "\n${CYAN}=== $1 ===${NC}"; }
pass()   { echo -e "${GREEN}PASS${NC}: $1"; }
fail()   { echo -e "${RED}FAIL${NC}: $1"; }
info()   { echo -e "${YELLOW}$1${NC}"; }

# ---------------------------------------------------------------------------
# Step 0: Load config
# ---------------------------------------------------------------------------
header "Loading configuration"

if [ -f .env ]; then
    # shellcheck disable=SC1091
    source .env
fi

if [ -z "${TSA_SHARED_SECRET:-}" ] || [ -z "${TSA_BASE_URL:-}" ]; then
    fail "TSA_SHARED_SECRET and TSA_BASE_URL must be set (in .env or environment)"
    exit 1
fi
info "SHARED_SECRET: (set)"
info "BASE_URL:      $TSA_BASE_URL"

# ---------------------------------------------------------------------------
# Step 1: Health check
# ---------------------------------------------------------------------------
header "Step 1: Health check (GET /health)"

HEALTH=$(curl -s -w "\n%{http_code}" "$API_BASE/health")
HTTP_CODE=$(echo "$HEALTH" | tail -1)
BODY=$(echo "$HEALTH" | sed '$d')

echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"

if [ "$HTTP_CODE" = "200" ]; then
    pass "Health endpoint returned 200"
else
    fail "Health endpoint returned $HTTP_CODE"
    info "Is the API running? Try: docker-compose up -d"
    exit 1
fi

# Check Redis connectivity from health response
REDIS_OK=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('redis_connected', False))" 2>/dev/null)
if [ "$REDIS_OK" = "True" ]; then
    pass "Redis is connected"
else
    fail "Redis is NOT connected - sessions won't work"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 2: Encrypt credentials and login
# ---------------------------------------------------------------------------
header "Step 2: Login (POST /api/login)"

read -r -p "Enter your member ID: " MEMBER_ID
read -r -s -p "Enter your PIN: " PIN
echo ""

info "Encrypting credentials..."

# Use the API's virtualenv if available, otherwise fall back to system python
if [ -x "api/.venv/bin/python3" ]; then
    PYTHON="api/.venv/bin/python3"
else
    PYTHON="python3"
fi

ENCRYPTED=$(TSA_SECRET="$TSA_SHARED_SECRET" TSA_USER="$MEMBER_ID" TSA_PIN="$PIN" $PYTHON -c "
import os, sys
sys.path.insert(0, 'api')
from app.services.encryption import EncryptionService
svc = EncryptionService(os.environ['TSA_SECRET'])
print(svc.encrypt_credentials(os.environ['TSA_USER'], os.environ['TSA_PIN']))
")

info "Sending login request..."
LOGIN_RESP=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/api/login" \
    -H "Content-Type: application/json" \
    -d "{\"credentials\": \"$ENCRYPTED\"}")

HTTP_CODE=$(echo "$LOGIN_RESP" | tail -1)
BODY=$(echo "$LOGIN_RESP" | sed '$d')

echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"

if [ "$HTTP_CODE" = "200" ]; then
    TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
    EXPIRES=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['expires_at'])")
    pass "Login successful"
    info "Token:   $TOKEN"
    info "Expires: $EXPIRES"
else
    fail "Login failed with HTTP $HTTP_CODE"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 3: Get available tee times
# ---------------------------------------------------------------------------
header "Step 3: Get available tee times (GET /api/{date}/times)"

# Default to tomorrow
if command -v gdate &>/dev/null; then
    DEFAULT_DATE=$(gdate -d "+1 day" +%Y-%m-%d)
elif date -d "+1 day" +%Y-%m-%d &>/dev/null 2>&1; then
    DEFAULT_DATE=$(date -d "+1 day" +%Y-%m-%d)
else
    DEFAULT_DATE=$(date -v+1d +%Y-%m-%d)
fi

read -r -p "Enter date to search (YYYY-MM-DD) [$DEFAULT_DATE]: " SEARCH_DATE
SEARCH_DATE=${SEARCH_DATE:-$DEFAULT_DATE}

read -r -p "Start time filter (HH:MM, blank for none): " START_TIME
read -r -p "End time filter   (HH:MM, blank for none): " END_TIME

QUERY=""
if [ -n "$START_TIME" ]; then QUERY="?start=$START_TIME"; fi
if [ -n "$END_TIME" ]; then
    if [ -n "$QUERY" ]; then QUERY="$QUERY&end=$END_TIME"; else QUERY="?end=$END_TIME"; fi
fi

info "Fetching times for $SEARCH_DATE..."
TIMES_RESP=$(curl -s -w "\n%{http_code}" "$API_BASE/api/$SEARCH_DATE/times$QUERY" \
    -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$TIMES_RESP" | tail -1)
BODY=$(echo "$TIMES_RESP" | sed '$d')

echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"

if [ "$HTTP_CODE" = "200" ]; then
    TOTAL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_count'])")
    FILTERED=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['filtered_count'])")
    pass "Got tee times: $FILTERED bookable (of $TOTAL total)"

    # List bookable times
    echo ""
    info "Bookable times:"
    echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data['times']:
    if t['can_book']:
        print(f\"  {t['time']}  (form: {t.get('booking_form', {})})\")
"
else
    fail "Get times failed with HTTP $HTTP_CODE"
    if [ "$HTTP_CODE" = "401" ]; then info "Session may have expired - try logging in again"; fi
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 4: Book a tee time (optional)
# ---------------------------------------------------------------------------
header "Step 4: Book a tee time (POST /api/{date}/time/{time}/book)"

read -r -p "Enter a time to book (HH:MM), or press Enter to skip: " BOOK_TIME

if [ -n "$BOOK_TIME" ]; then
    read -r -p "Number of slots (1-4) [1]: " NUM_SLOTS
    NUM_SLOTS=${NUM_SLOTS:-1}

    read -r -p "Dry run? (y/n) [y]: " DRY_RUN
    DRY_RUN=${DRY_RUN:-y}
    if [ "$DRY_RUN" = "y" ] || [ "$DRY_RUN" = "Y" ]; then
        DRY_RUN_BOOL="true"
        info "DRY RUN mode - no real booking will be made"
    else
        DRY_RUN_BOOL="false"
        info "LIVE mode - this will make a real booking!"
        read -r -p "Are you sure? (yes/no): " CONFIRM
        if [ "$CONFIRM" != "yes" ]; then
            info "Aborted."
            exit 0
        fi
    fi

    BOOK_RESP=$(curl -s -w "\n%{http_code}" -X POST \
        "$API_BASE/api/$SEARCH_DATE/time/$BOOK_TIME/book" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"num_slots\": $NUM_SLOTS, \"dry_run\": $DRY_RUN_BOOL}")

    HTTP_CODE=$(echo "$BOOK_RESP" | tail -1)
    BODY=$(echo "$BOOK_RESP" | sed '$d')

    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"

    if [ "$HTTP_CODE" = "200" ]; then
        BOOKING_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['booking_id'])")
        pass "Booking successful! ID: $BOOKING_ID"
    else
        fail "Booking failed with HTTP $HTTP_CODE"
    fi

    # -----------------------------------------------------------------------
    # Step 5: Add playing partners (optional, only if booking succeeded)
    # -----------------------------------------------------------------------
    if [ "$HTTP_CODE" = "200" ] && [ "$DRY_RUN_BOOL" = "false" ]; then
        header "Step 5: Add partners (PATCH /api/bookings/{booking_id})"

        read -r -p "Enter partner IDs (comma-separated), or press Enter to skip: " PARTNERS_INPUT

        if [ -n "$PARTNERS_INPUT" ]; then
            # Convert "P001,P002" to JSON array ["P001","P002"]
            PARTNERS_JSON=$(python3 -c "
import json
ids = [p.strip() for p in '$PARTNERS_INPUT'.split(',')]
print(json.dumps(ids))
")

            PARTNER_RESP=$(curl -s -w "\n%{http_code}" -X PATCH \
                "$API_BASE/api/bookings/$BOOKING_ID" \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d "{\"partners\": $PARTNERS_JSON, \"dry_run\": false}")

            HTTP_CODE=$(echo "$PARTNER_RESP" | tail -1)
            BODY=$(echo "$PARTNER_RESP" | sed '$d')

            echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"

            if [ "$HTTP_CODE" = "200" ]; then
                pass "All partners added"
            elif [ "$HTTP_CODE" = "207" ]; then
                info "Partial success - some partners failed (see response above)"
            else
                fail "Add partners failed with HTTP $HTTP_CODE"
            fi
        else
            info "Skipping partner addition."
        fi
    fi
else
    info "Skipping booking step."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
header "Manual test complete"
info "Your session token is still valid until it expires."
info "You can continue making requests with:"
info "  curl -H 'Authorization: Bearer $TOKEN' $API_BASE/api/..."
