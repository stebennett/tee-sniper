# Tee-Sniper

An automated golf tee-time booking bot written in Go. Tee-Sniper logs into a golf course booking website, searches for available tee times within your specified date and time range, and automatically books a slot. Upon successful booking, it sends an SMS confirmation via Twilio.

## Features

- Automated login and session management with cookie persistence
- Configurable date range (days ahead) and time window filtering
- Random selection from available slots to avoid predictable booking patterns
- User-agent rotation to avoid detection
- Retry logic with jitter to handle high-demand booking periods
- SMS notifications via Twilio for booking confirmations
- Support for booking with playing partners
- Dry-run mode for testing without making actual bookings

## Prerequisites

- Go 1.25 or later
- A Twilio account for SMS notifications
- Access credentials for your golf course booking website

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/stebennett/tee-sniper.git
cd tee-sniper

# Build the application
go build -o tee-sniper cmd/tee-sniper/main.go
```

### From Releases

Download the latest binary from the [Releases](https://github.com/stebennett/tee-sniper/releases) page.

### Using Docker

Build and run using Docker:

```bash
# Build the image
docker build -t tee-sniper .

# Run with CLI arguments
docker run --rm \
    -e TWILIO_ACCOUNT_SID="your-sid" \
    -e TWILIO_AUTH_TOKEN="your-token" \
    tee-sniper \
    -u YOUR_USERNAME \
    -p YOUR_PIN \
    -b https://your-golf-course.com/ \
    -d 7 \
    -t 15:00 \
    -e 17:00 \
    -f +1234567890 \
    -n +0987654321

# Or run with environment variables only
docker run --rm \
    -e TWILIO_ACCOUNT_SID="your-sid" \
    -e TWILIO_AUTH_TOKEN="your-token" \
    -e TS_USERNAME="your-username" \
    -e TS_PIN="your-pin" \
    -e TS_BASEURL="https://your-golf-course.com/" \
    -e TS_DAYS_AHEAD="7" \
    -e TS_TIME_START="15:00" \
    -e TS_TIME_END="17:00" \
    -e TS_FROM_NUMBER="+1234567890" \
    -e TS_TO_NUMBER="+0987654321" \
    tee-sniper
```

Pre-built images are available from GitHub Container Registry:

```bash
docker pull ghcr.io/stebennett/tee-sniper:latest
```

### Kubernetes with Helm

Deploy to Kubernetes as a CronJob using the included Helm chart:

```bash
# Install with Helm
helm install tee-sniper ./helm/tee-sniper \
    --namespace tee-sniper \
    --create-namespace \
    --set config.baseUrl="https://your-golf-course.com/" \
    --set secrets.username="your-username" \
    --set secrets.pin="your-pin" \
    --set secrets.fromNumber="+1234567890" \
    --set secrets.toNumber="+0987654321" \
    --set secrets.twilioAccountSid="ACxxxx" \
    --set secrets.twilioAuthToken="your-token"
```

For ArgoCD deployment, see the example manifests in `argocd/`. Full Helm chart documentation is available in [`helm/tee-sniper/README.md`](helm/tee-sniper/README.md).

## Configuration

### Environment Variables

Tee-Sniper supports configuration via environment variables as an alternative to command-line flags. CLI flags take precedence over environment variables when both are provided.

#### Required (Twilio)

| Variable | Description |
|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Your Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Your Twilio authentication token |

#### Application Configuration

| Variable | CLI Flag | Description |
|----------|----------|-------------|
| `TS_DAYS_AHEAD` | `-d` | Number of days ahead to look for a tee slot |
| `TS_TIME_START` | `-t` | Earliest time to book (HH:MM format) |
| `TS_TIME_END` | `-e` | Latest time to book (HH:MM format) |
| `TS_RETRIES` | `-r` | Number of retry attempts (default: 5) |
| `TS_DRY_RUN` | `-x` | Test mode - set to "true" to run without booking |
| `TS_USERNAME` | `-u` | Booking website username |
| `TS_PIN` | `-p` | PIN for authentication |
| `TS_BASEURL` | `-b` | Booking website base URL |
| `TS_FROM_NUMBER` | `-f` | Twilio sender phone number |
| `TS_TO_NUMBER` | `-n` | SMS recipient phone number |
| `TS_PARTNERS` | `-s` | Comma-separated list of playing partner IDs |

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
# Edit .env with your credentials
```

### Command Line Options

| Flag | Short | Description | Required | Default |
|------|-------|-------------|----------|---------|
| `--days` | `-d` | Number of days ahead to look for a tee slot | Yes | - |
| `--timestart` | `-t` | Earliest time to book (HH:MM format) | Yes | - |
| `--timeend` | `-e` | Latest time to book (HH:MM format) | Yes | - |
| `--retries` | `-r` | Number of retry attempts | Yes | 5 |
| `--dryrun` | `-x` | Test mode - runs without booking | No | false |
| `--username` | `-u` | Booking website username | Yes | - |
| `--pin` | `-p` | PIN for authentication | Yes | - |
| `--baseurl` | `-b` | Booking website base URL | Yes | - |
| `--fromnumber` | `-f` | Twilio sender phone number | Yes | - |
| `--tonumber` | `-n` | SMS recipient phone number | Yes | - |
| `--partners` | `-s` | Comma-separated list of playing partner IDs | No | - |

## Usage

### Display Help

```bash
go run cmd/tee-sniper/main.go -h
```

### Basic Booking

Book a tee time 7 days ahead between 15:00 and 17:00:

```bash
go run cmd/tee-sniper/main.go \
    -u YOUR_USERNAME \
    -p YOUR_PIN \
    -b https://your-golf-course.com/ \
    -d 7 \
    -t 15:00 \
    -e 17:00 \
    -f +1234567890 \
    -n +0987654321
```

### Booking with Playing Partners

Book for yourself and two partners:

```bash
go run cmd/tee-sniper/main.go \
    -u YOUR_USERNAME \
    -p YOUR_PIN \
    -b https://your-golf-course.com/ \
    -d 7 \
    -t 15:00 \
    -e 17:00 \
    -f +1234567890 \
    -n +0987654321 \
    -s "partner1_id,partner2_id"
```

### Dry Run Mode

Test the booking flow without making an actual booking:

```bash
go run cmd/tee-sniper/main.go \
    -u YOUR_USERNAME \
    -p YOUR_PIN \
    -b https://your-golf-course.com/ \
    -d 7 \
    -t 15:00 \
    -e 17:00 \
    -f +1234567890 \
    -n +0987654321 \
    -x
```

### Using the Convenience Script

A convenience script is provided that sources environment variables from `.env`:

```bash
# Configure your .env file first
./run-teesniper.sh
```

## Project Structure

```
tee-sniper/
├── cmd/
│   └── tee-sniper/
│       ├── main.go           # Application entry point
│       └── main_test.go      # Main application tests
├── pkg/
│   ├── clients/
│   │   ├── interfaces.go     # Service interfaces for dependency injection
│   │   ├── bookingclient.go  # Golf course website HTTP client
│   │   ├── bookingclient_test.go
│   │   ├── twilioclient.go   # Twilio SMS client
│   │   ├── twilioclient_test.go
│   │   └── mocks/            # Generated mock implementations
│   ├── config/
│   │   ├── config.go         # CLI argument parsing
│   │   └── config_test.go
│   ├── models/
│   │   └── models.go         # Data structures (TimeSlot)
│   └── teetimes/
│       ├── teetimes.go       # Tee time filtering and selection logic
│       └── teetimes_test.go
├── helm/
│   └── tee-sniper/           # Helm chart for Kubernetes deployment
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── argocd/                   # ArgoCD Application examples
│   ├── application.yaml
│   └── secrets-example.yaml
├── testdata/                 # HTML fixtures for testing
├── .github/workflows/
│   ├── build.yml             # CI build and test workflow
│   └── release.yml           # Release automation (binary + Docker)
├── .env.example              # Environment variables template
├── run-teesniper.sh          # Convenience execution script
└── go.mod                    # Go module definition
```

## How It Works

1. **Authentication**: Logs into the golf course booking website using provided credentials
2. **Search**: Fetches available tee times for the target date (current date + days ahead)
3. **Filter**: Filters slots to only those that are:
   - Available for booking
   - Within the specified time window (timestart to timeend)
4. **Select**: Randomly picks one slot from the filtered results
5. **Book**: Attempts to book the selected time slot
   - If partners are specified, adds them to additional slots
6. **Notify**: Sends SMS confirmation via Twilio
7. **Retry**: If booking fails or no slots are available, waits with random delay and retries

The retry logic includes jitter (random delay variation) to avoid rate limiting and detection.

## Development

### Running Tests

```bash
# Run all tests
go test ./...

# Run tests for a specific package
go test ./pkg/teetimes/

# Run tests with verbose output
go test -v ./...

# Run tests with coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

### Test Coverage

| Package | Coverage |
|---------|----------|
| `pkg/teetimes` | 100% |
| `pkg/config` | 100% |
| `pkg/clients` | 93% |
| `cmd/tee-sniper` | 83% |
| **Overall** | **~78%** |

### Building

```bash
# Build for current platform
go build -o tee-sniper cmd/tee-sniper/main.go

# Build for Linux
GOOS=linux GOARCH=amd64 go build -o tee-sniper-linux cmd/tee-sniper/main.go
```

### Dependencies

| Package | Purpose |
|---------|---------|
| [goquery](https://github.com/PuerkitoBio/goquery) | HTML parsing and DOM traversal |
| [go-flags](https://github.com/jessevdk/go-flags) | Command-line argument parsing |
| [twilio-go](https://github.com/twilio/twilio-go) | Twilio SMS API client |
| [testify](https://github.com/stretchr/testify) | Testing assertions |
| [gomock](https://github.com/golang/mock) | Mock generation for testing |

## CI/CD

The project includes GitHub Actions workflows:

- **Build** (`.github/workflows/build.yml`): Runs on push to main and pull requests. Executes build and test steps.
- **Release** (`.github/workflows/release.yml`): Triggers on version tags (v*.*.*). Builds Linux binary, creates GitHub release, and pushes Docker image to GitHub Container Registry.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
