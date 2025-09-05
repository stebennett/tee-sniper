# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
```bash
# Run with command line arguments
go run cmd/tee-sniper/main.go -h

# Run using the convenience script (sources .env file)
./run-teesniper.sh

# Example with all parameters
go run cmd/tee-sniper/main.go -u username -p pin -b https://example.com/ -d 7 -t 15:00 -e 17:00 -n toNumber -f fromNumber
```

### Testing
```bash
# Run tests
go test ./...

# Run tests for specific package
go test ./pkg/teetimes/
```

### Building
```bash
# Build the application
go build -o tee-sniper cmd/tee-sniper/main.go
```

## Code Architecture

### Project Structure
- `cmd/tee-sniper/main.go` - Main application entry point
- `pkg/config/` - Configuration handling using go-flags
- `pkg/models/` - Data models (TimeSlot, etc.)
- `pkg/clients/` - External service clients (Twilio, booking site)
- `pkg/teetimes/` - Core business logic for filtering and selecting tee times

### Core Components

**Main Application Flow** (cmd/tee-sniper/main.go):
1. Parses command line configuration
2. Creates booking and Twilio clients
3. Logs into booking site
4. Searches for available tee times within specified date/time range
5. Filters, sorts, and randomly selects from available slots
6. Books the selected time slot with retry logic
7. Sends SMS confirmation via Twilio

**Configuration** (pkg/config/config.go):
Uses jessevdk/go-flags for command line argument parsing. All required parameters must be provided via CLI flags or the application will exit with help text.

**Tee Time Logic** (pkg/teetimes/teetimes.go):
- `FilterByBookable()` - Filters to only bookable slots
- `SortTimesAscending()` - Sorts times chronologically
- `FilterBetweenTimes()` - Filters by time range
- `PickRandomTime()` - Randomly selects from available options

**External Dependencies**:
- Twilio Go SDK for SMS notifications
- PuerkitoBio/goquery for HTML parsing/scraping
- jessevdk/go-flags for CLI argument parsing

### Environment Variables
The application expects Twilio credentials as environment variables:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`

### GitHub Actions Integration
The repository includes a manual workflow (`.github/workflows/book-tee-time-manual.yml`) that allows triggering the booking process via GitHub Actions with configurable parameters.