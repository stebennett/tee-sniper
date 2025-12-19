# Comprehensive Testing Plan for tee-sniper

## Current State

| Component | File | Tests | Coverage |
|-----------|------|-------|----------|
| teetimes | `pkg/teetimes/teetimes.go` | ✅ | 84.6% |
| config | `pkg/config/config.go` | ❌ | 0% |
| bookingclient | `pkg/clients/bookingclient.go` | ❌ | 0% |
| twilioclient | `pkg/clients/twilioclient.go` | ❌ | 0% |
| models | `pkg/models/models.go` | ❌ | 0% |
| main | `cmd/tee-sniper/main.go` | ❌ | 0% |

**Overall Coverage**: ~17% (only 1 of 6 source files tested)

---

## Testing Strategy

### Approach

1. **Define interfaces** for external dependencies to enable mocking
2. **Use table-driven tests** for comprehensive input/output coverage
3. **Use httptest** for HTTP client testing
4. **Use testify** for assertions (already a dependency)
5. **Use golang/mock** for mock generation (already in go.mod but unused)

### Test Types

- **Unit Tests**: Test individual functions in isolation
- **Integration Tests**: Test HTTP client interactions with mock servers
- **Edge Case Tests**: Invalid inputs, error conditions, boundary values

---

## Phase 1: Infrastructure & Interfaces

### 1.1 Define Interfaces for Mocking

Create `pkg/clients/interfaces.go`:

```go
package clients

import "github.com/stevebennett/tee-sniper/pkg/models"

// BookingService defines the interface for booking operations
type BookingService interface {
    Login(username, password string) (bool, error)
    GetCourseAvailability(dateStr string) ([]models.TimeSlot, error)
    BookTimeSlot(timeSlot models.TimeSlot, playingPartners []string, dryRun bool) (string, error)
    AddPlayingPartner(bookingID, partnerID string, slotNumber int, dryRun bool) error
}

// SMSService defines the interface for SMS operations
type SMSService interface {
    SendSms(from, to, body string, dryRun bool) error
}
```

### 1.2 Generate Mocks

Run mock generation:
```bash
go install github.com/golang/mock/mockgen@latest
mockgen -source=pkg/clients/interfaces.go -destination=pkg/clients/mocks/mock_clients.go -package=mocks
```

### Tasks
- [x] Create `pkg/clients/interfaces.go` with BookingService and SMSService interfaces
- [x] Update BookingClient and TwilioClient to implement interfaces
- [x] Generate mock implementations
- [x] Create `pkg/clients/mocks/` directory

---

## Phase 2: Config Package Tests

### File: `pkg/config/config_test.go`

### Test Cases

| Function | Test Name | Description |
|----------|-----------|-------------|
| `GetPlayingPartnersList` | `TestGetPlayingPartnersListEmpty` | Empty string returns empty slice |
| `GetPlayingPartnersList` | `TestGetPlayingPartnersListSingle` | Single partner returns slice with one element |
| `GetPlayingPartnersList` | `TestGetPlayingPartnersListMultiple` | Comma-separated list returns multiple elements |
| `GetPlayingPartnersList` | `TestGetPlayingPartnersListWithSpaces` | Handles whitespace around values |
| `isErrHelp` | `TestIsErrHelpTrue` | Returns true for help flag error |
| `isErrHelp` | `TestIsErrHelpFalse` | Returns false for other errors |

### Tasks
- [ ] Create `pkg/config/config_test.go`
- [ ] Test `GetPlayingPartnersList()` with various inputs
- [ ] Test `isErrHelp()` error detection
- [ ] Test `GetConfig()` with mock os.Args (optional, complex)

---

## Phase 3: Tee Times Package Tests (Expand Coverage)

### File: `pkg/teetimes/teetimes_test.go`

### Additional Test Cases

| Function | Test Name | Description |
|----------|-----------|-------------|
| `PickRandomTime` | `TestPickRandomTimeEmptySlice` | Returns empty TimeSlot for empty input |
| `PickRandomTime` | `TestPickRandomTimeSingleItem` | Returns the only item |
| `PickRandomTime` | `TestPickRandomTimeMultipleItems` | Returns a valid item from the slice |
| `FilterBetweenTimes` | `TestFilterBetweenTimesEmptySlice` | Handles empty input |
| `FilterBetweenTimes` | `TestFilterBetweenTimesNoMatches` | Returns empty when no slots in range |
| `SortTimesAscending` | `TestSortTimesAscendingEmpty` | Handles empty slice |
| `SortTimesAscending` | `TestSortTimesAscendingSingleItem` | Single item remains unchanged |
| `FilterByBookable` | `TestFilterByBookableNoneBookable` | Returns empty when no bookable slots |
| `FilterByBookable` | `TestFilterByBookableAllBookable` | Returns all when all are bookable |

### Tasks
- [ ] Add `PickRandomTime` tests
- [ ] Add edge case tests for all functions
- [ ] Achieve 100% coverage

---

## Phase 4: Booking Client Tests

### File: `pkg/clients/bookingclient_test.go`

### Strategy: Use `httptest.NewServer` for HTTP mocking

### Test Cases

| Function | Test Name | Description |
|----------|-----------|-------------|
| `NewBookingClient` | `TestNewBookingClientValidURL` | Creates client with valid URL |
| `NewBookingClient` | `TestNewBookingClientInvalidURL` | Returns error for invalid URL |
| `Login` | `TestLoginSuccess` | Returns true for successful login |
| `Login` | `TestLoginFailure` | Returns false for failed login |
| `Login` | `TestLoginNetworkError` | Handles network errors gracefully |
| `GetCourseAvailability` | `TestGetCourseAvailabilitySuccess` | Parses HTML and returns time slots |
| `GetCourseAvailability` | `TestGetCourseAvailabilityNoSlots` | Returns empty slice when no slots |
| `GetCourseAvailability` | `TestGetCourseAvailabilityMalformedHTML` | Handles malformed HTML |
| `BookTimeSlot` | `TestBookTimeSlotSuccess` | Returns booking ID on success |
| `BookTimeSlot` | `TestBookTimeSlotDryRun` | Returns fake ID in dry run mode |
| `BookTimeSlot` | `TestBookTimeSlotFailure` | Handles booking failures |
| `extractBookingID` | `TestExtractBookingIDValid` | Extracts ID from valid URL |
| `extractBookingID` | `TestExtractBookingIDInvalid` | Returns error for invalid URL |
| `AddPlayingPartner` | `TestAddPlayingPartnerSuccess` | Adds partner successfully |
| `AddPlayingPartner` | `TestAddPlayingPartnerDryRun` | Skips in dry run mode |

### Sample Test Structure

```go
func TestLoginSuccess(t *testing.T) {
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path == "/login" && r.Method == "POST" {
            w.WriteHeader(http.StatusOK)
            w.Write([]byte(`<html><head><title>Welcome</title></head></html>`))
        }
    }))
    defer server.Close()

    client, _ := NewBookingClient(server.URL)
    success, err := client.Login("user", "pass")

    assert.NoError(t, err)
    assert.True(t, success)
}
```

### Tasks
- [ ] Create `pkg/clients/bookingclient_test.go`
- [ ] Create test fixtures for HTML responses
- [ ] Test `NewBookingClient` constructor
- [ ] Test `Login` with mock server
- [ ] Test `GetCourseAvailability` with mock HTML
- [ ] Test `BookTimeSlot` with mock server
- [ ] Test `extractBookingID` regex parsing
- [ ] Test `AddPlayingPartner` with mock server

---

## Phase 5: Twilio Client Tests

### File: `pkg/clients/twilioclient_test.go`

### Strategy: Test dry run behavior and interface compliance

### Test Cases

| Function | Test Name | Description |
|----------|-----------|-------------|
| `NewTwilioClient` | `TestNewTwilioClient` | Creates client successfully |
| `SendSms` | `TestSendSmsDryRun` | Returns nil without sending in dry run |
| `SendSms` | `TestSendSmsIntegration` | (Skip in CI) Sends real SMS |

### Tasks
- [ ] Create `pkg/clients/twilioclient_test.go`
- [ ] Test dry run mode (no actual API calls)
- [ ] Test interface compliance

---

## Phase 6: Main Application Tests

### File: `cmd/tee-sniper/main_test.go`

### Refactoring Required

Extract testable functions from `main()`:

```go
// Move to pkg/app/app.go or keep in main but export
func GetRandomRetryDelay(minSeconds, maxSeconds int) time.Duration

// Create App struct for dependency injection
type App struct {
    config        config.Config
    bookingClient clients.BookingService
    twilioClient  clients.SMSService
}

func (a *App) Run() error { ... }
```

### Test Cases

| Function | Test Name | Description |
|----------|-----------|-------------|
| `getRandomRetryDelay` | `TestGetRandomRetryDelayRange` | Returns value within expected range |
| `getRandomRetryDelay` | `TestGetRandomRetryDelayJitter` | Applies ±20% jitter |
| `App.Run` | `TestRunSuccessfulBooking` | Complete flow with mocked dependencies |
| `App.Run` | `TestRunRetryOnFailure` | Retries on booking failure |
| `App.Run` | `TestRunSendsConfirmation` | Sends SMS on success |

### Tasks
- [ ] Export `getRandomRetryDelay` for testing
- [ ] Create `cmd/tee-sniper/main_test.go`
- [ ] Test delay calculation
- [ ] Optionally refactor main for full flow testing

---

## Phase 7: Test Fixtures

### Directory: `testdata/`

Create HTML fixtures for booking client tests:

```
testdata/
├── login_success.html       # Successful login response
├── login_failure.html       # Failed login response
├── availability_slots.html  # Page with available tee times
├── availability_empty.html  # Page with no tee times
├── booking_success.html     # Successful booking confirmation
└── booking_failure.html     # Failed booking response
```

### Tasks
- [ ] Create `testdata/` directory
- [ ] Create HTML fixture files
- [ ] Create helper function to load fixtures

---

## Implementation Order

Each phase will be completed in a **separate Pull Request** to ensure clean, reviewable changes.

| Phase | Branch Name | PR Title |
|-------|-------------|----------|
| 1 | `test/phase1-interfaces-mocks` | Add interfaces and mock infrastructure for testing |
| 2 | `test/phase2-config-tests` | Add unit tests for config package |
| 3 | `test/phase3-teetimes-tests` | Expand teetimes package test coverage to 100% |
| 4 | `test/phase4-bookingclient-tests` | Add unit tests for booking client |
| 5 | `test/phase5-twilioclient-tests` | Add unit tests for Twilio client |
| 6 | `test/phase6-main-tests` | Add tests for main application logic |
| 7 | `test/phase7-test-fixtures` | Add HTML test fixtures |

### Workflow Per Phase

1. Create feature branch from `main`
2. Implement tests for that phase
3. Run `go test ./...` to verify all tests pass
4. Commit changes with descriptive message
5. Push branch and create PR
6. Merge PR to `main` before starting next phase

### Phase Dependencies

```
Phase 1 (Interfaces/Mocks)
    ├── Phase 2 (Config) - independent
    ├── Phase 3 (Teetimes) - independent
    ├── Phase 4 (Booking Client) - requires Phase 1, 7
    ├── Phase 5 (Twilio Client) - requires Phase 1
    └── Phase 6 (Main) - requires Phase 1
Phase 7 (Fixtures) - can be done early, used by Phase 4
```

**Recommended order:**
1. **Phase 1**: Infrastructure (interfaces, mocks) - Foundation for all other tests
2. **Phase 2**: Config tests - Simple, no external deps
3. **Phase 3**: Teetimes tests - Expand existing coverage
4. **Phase 7**: Test fixtures - Needed for Phase 4
5. **Phase 4**: Booking client tests - Most complex, highest value
6. **Phase 5**: Twilio client tests - External API
7. **Phase 6**: Main tests - Integration/orchestration

---

## Coverage Goals

| Package | Current | Target |
|---------|---------|--------|
| pkg/teetimes | 84.6% | 100% |
| pkg/config | 0% | 90%+ |
| pkg/clients | 0% | 80%+ |
| pkg/models | 0% | N/A (data only) |
| cmd/tee-sniper | 0% | 70%+ |
| **Overall** | ~17% | **80%+** |

---

## CI Integration

Update `.github/workflows/build.yml` to include coverage:

```yaml
- name: Run tests with coverage
  run: go test -v -coverprofile=coverage.out ./...

- name: Check coverage threshold
  run: |
    coverage=$(go tool cover -func=coverage.out | grep total | awk '{print $3}' | sed 's/%//')
    if (( $(echo "$coverage < 80" | bc -l) )); then
      echo "Coverage $coverage% is below 80% threshold"
      exit 1
    fi
```

---

## Running Tests

```bash
# Run all tests
go test ./...

# Run with verbose output
go test -v ./...

# Run with coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out

# Run specific package
go test -v ./pkg/clients/

# Run specific test
go test -v -run TestLoginSuccess ./pkg/clients/
```
