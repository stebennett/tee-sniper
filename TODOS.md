# TODOs - Testing Implementation

## Phase 4: Booking Client Tests

### Test Fixtures
- [x] Create `testdata/login_success.html`
- [x] Create `testdata/login_failure.html`
- [x] Create `testdata/availability_with_slots.html`
- [x] Create `testdata/availability_empty.html`
- [x] Create `testdata/availability_blocked.html`
- [x] Create `testdata/booking_success.html`
- [x] Create `testdata/booking_failure.html`

### Test File Setup
- [x] Create `pkg/clients/bookingclient_test.go`
- [x] Create `loadFixture` helper function
- [x] Create mock server helpers

### NewBookingClient Tests
- [x] `TestNewBookingClientValidURL`
- [x] `TestNewBookingClientEmptyURL`
- [x] `TestNewBookingClientSetsUserAgent`
- [x] `TestNewBookingClientHasCookieJar` (bonus)

### Login Tests
- [x] `TestLoginSuccess`
- [x] `TestLoginFailure`
- [x] `TestLoginNon200Status`
- [x] `TestLoginNetworkError`
- [x] `TestLoginFormParameters`
- [x] `TestLoginSetsCorrectHeaders` (bonus)

### GetCourseAvailability Tests
- [x] `TestGetCourseAvailabilitySuccess`
- [x] `TestGetCourseAvailabilityNoSlots`
- [x] `TestGetCourseAvailabilityBlockedSlots`
- [x] `TestGetCourseAvailabilityNon200Status`
- [x] `TestGetCourseAvailabilityNetworkError`
- [x] `TestGetCourseAvailabilityDateParameter`
- [x] `TestGetCourseAvailabilitySetsCorrectHeaders` (bonus)

### extractBookingID Tests
- [x] `TestExtractBookingIDValid`
- [x] `TestExtractBookingIDMidURL`
- [x] `TestExtractBookingIDMissing`
- [x] `TestExtractBookingIDEmpty`
- [x] `TestExtractBookingIDNoQueryString` (bonus)
- [x] `TestExtractBookingIDComplexValue` (bonus)

### BookTimeSlot Tests
- [x] `TestBookTimeSlotSuccess`
- [x] `TestBookTimeSlotDryRun`
- [x] `TestBookTimeSlotFailureNoConfirmation`
- [x] `TestBookTimeSlotNon200Status`
- [x] `TestBookTimeSlotNetworkError`
- [x] `TestBookTimeSlotNumSlotsCalculation`
- [x] `TestBookTimeSlotNumSlotsNoPartners` (bonus)
- [x] `TestBookTimeSlotPassesBookingFormParams` (bonus)

### AddPlayingPartner Tests
- [x] `TestAddPlayingPartnerSuccess`
- [x] `TestAddPlayingPartnerDryRun`
- [x] `TestAddPlayingPartnerNon200Status`
- [x] `TestAddPlayingPartnerNetworkError`
- [x] `TestAddPlayingPartnerQueryParameters`
- [x] `TestAddPlayingPartnerSetsCorrectHeaders` (bonus)

### Additional Tests
- [x] `TestAddBrowserHeadersSetsAllHeaders`
- [x] `TestBookingClientImplementsBookingService`

### Final Verification
- [x] All tests pass (`go test ./...`)
- [x] Coverage target met (85.9% > 80%+)
- [x] Update TESTING_PLAN.md to mark tasks complete
- [ ] Create PR
