# TODOs - Testing Implementation

## Phase 6: Main Application Tests

### Setup
- [x] Create branch `test/phase6-main-tests` from `main`
- [x] Create `cmd/tee-sniper/main_test.go`

### Refactoring for Testability
- [x] Export `GetRandomRetryDelay` function (rename from lowercase)
- [x] Create `App` struct with dependency injection
- [x] Add `TimeNow` function field for deterministic date testing
- [x] Add `SleepFunc` function field to avoid real delays in tests
- [x] Create `NewApp()` constructor with real dependencies
- [x] Extract main logic into `App.Run()` method
- [x] Update `main()` to use new App struct

### GetRandomRetryDelay Tests
- [x] `TestGetRandomRetryDelayWithinRange`
- [x] `TestGetRandomRetryDelayMinEqualsMax`
- [x] `TestGetRandomRetryDelayReturnsPositive`
- [x] `TestGetRandomRetryDelayHasVariation`

### NewApp Tests
- [x] `TestNewApp`

### App.Run() Tests
- [x] `TestRunLoginError`
- [x] `TestRunGetAvailabilityError`
- [x] `TestRunSuccessfulBookingFirstAttempt`
- [x] `TestRunSuccessfulBookingWithPartners`
- [x] `TestRunPartnerAddFailureContinues`
- [x] `TestRunRetryOnNoAvailability`
- [x] `TestRunRetryOnBookingFailure`
- [x] `TestRunRetryOnEmptyBookingID`
- [x] `TestRunAllRetriesExhausted`
- [x] `TestRunSendsFailureSMS`
- [x] `TestRunSMSErrorDoesNotFailBooking`
- [x] `TestRunDryRunMode`
- [x] `TestRunFiltersNonBookableSlots`
- [x] `TestRunFiltersOutsideTimeRange`
- [x] `TestRunUsesCorrectDateFormat`
- [x] `TestRunSleepCalledOnRetry`

### Final Verification
- [x] All tests pass (`go test ./...`)
- [x] Coverage target met (83.1% > 70%+)
- [x] Update TESTING_PLAN.md to mark tasks complete
- [ ] Create PR
