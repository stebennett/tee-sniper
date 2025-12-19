package main

import (
	"errors"
	"testing"
	"time"

	"github.com/golang/mock/gomock"
	"github.com/stebennett/tee-sniper/pkg/clients/mocks"
	"github.com/stebennett/tee-sniper/pkg/config"
	"github.com/stebennett/tee-sniper/pkg/models"
	"github.com/stretchr/testify/assert"
)

// =============================================================================
// GetRandomRetryDelay Tests
// =============================================================================

func TestGetRandomRetryDelayWithinRange(t *testing.T) {
	minSeconds := 5
	maxSeconds := 15

	for i := 0; i < 100; i++ {
		delay := GetRandomRetryDelay(minSeconds, maxSeconds)

		minExpected := time.Duration(float64(minSeconds)*0.8*1000) * time.Millisecond
		maxExpected := time.Duration(float64(maxSeconds)*1.2*1000) * time.Millisecond

		assert.GreaterOrEqual(t, delay, minExpected, "delay should be >= min with jitter")
		assert.LessOrEqual(t, delay, maxExpected, "delay should be <= max with jitter")
	}
}

func TestGetRandomRetryDelayMinEqualsMax(t *testing.T) {
	seconds := 10

	for i := 0; i < 50; i++ {
		delay := GetRandomRetryDelay(seconds, seconds)

		minExpected := time.Duration(float64(seconds)*0.8*1000) * time.Millisecond
		maxExpected := time.Duration(float64(seconds)*1.2*1000) * time.Millisecond

		assert.GreaterOrEqual(t, delay, minExpected)
		assert.LessOrEqual(t, delay, maxExpected)
	}
}

func TestGetRandomRetryDelayReturnsPositive(t *testing.T) {
	delay := GetRandomRetryDelay(1, 5)
	assert.Greater(t, delay, time.Duration(0))
}

func TestGetRandomRetryDelayHasVariation(t *testing.T) {
	delays := make(map[time.Duration]bool)

	for i := 0; i < 100; i++ {
		delay := GetRandomRetryDelay(5, 15)
		delays[delay] = true
	}

	assert.Greater(t, len(delays), 1, "delays should have variation due to randomness")
}

// =============================================================================
// NewApp Tests
// =============================================================================

func TestNewApp(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockBooking := mocks.NewMockBookingService(ctrl)
	mockSMS := mocks.NewMockSMSService(ctrl)
	conf := config.Config{
		Username: "testuser",
		Pin:      "1234",
	}

	app := NewApp(conf, mockBooking, mockSMS)

	assert.NotNil(t, app)
	assert.Equal(t, conf, app.Config)
	assert.NotNil(t, app.BookingClient)
	assert.NotNil(t, app.TwilioClient)
	assert.NotNil(t, app.TimeNow)
	assert.NotNil(t, app.SleepFunc)
}

// =============================================================================
// App.Run() Tests
// =============================================================================

func createTestApp(t *testing.T, conf config.Config) (*App, *mocks.MockBookingService, *mocks.MockSMSService, *gomock.Controller) {
	ctrl := gomock.NewController(t)
	mockBooking := mocks.NewMockBookingService(ctrl)
	mockSMS := mocks.NewMockSMSService(ctrl)

	app := &App{
		Config:        conf,
		BookingClient: mockBooking,
		TwilioClient:  mockSMS,
		TimeNow:       func() time.Time { return time.Date(2024, 1, 15, 10, 0, 0, 0, time.UTC) },
		SleepFunc:     func(d time.Duration) {},
	}

	return app, mockBooking, mockSMS, ctrl
}

func defaultTestConfig() config.Config {
	return config.Config{
		DaysAhead:  7,
		TimeStart:  "09:00",
		TimeEnd:    "17:00",
		Retries:    3,
		DryRun:     false,
		Username:   "testuser",
		Pin:        "1234",
		BaseUrl:    "https://example.com",
		FromNumber: "+1234567890",
		ToNumber:   "+0987654321",
	}
}

func TestRunLoginError(t *testing.T) {
	app, mockBooking, _, ctrl := createTestApp(t, defaultTestConfig())
	defer ctrl.Finish()

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(false, errors.New("invalid credentials"))

	err := app.Run()

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "login failed")
}

func TestRunGetAvailabilityError(t *testing.T) {
	app, mockBooking, _, ctrl := createTestApp(t, defaultTestConfig())
	defer ctrl.Finish()

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(nil, errors.New("network error"))

	err := app.Run()

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get availability")
}

func TestRunSuccessfulBookingFirstAttempt(t *testing.T) {
	app, mockBooking, mockSMS, ctrl := createTestApp(t, defaultTestConfig())
	defer ctrl.Finish()

	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(availableSlots, nil)
	mockBooking.EXPECT().
		BookTimeSlot(gomock.Any(), gomock.Any(), false).
		Return("booking-123", nil)
	mockSMS.EXPECT().
		SendSms("+1234567890", "+0987654321", gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunSuccessfulBookingWithPartners(t *testing.T) {
	conf := defaultTestConfig()
	conf.PlayingPartners = "partner1,partner2"

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(availableSlots, nil)
	mockBooking.EXPECT().
		BookTimeSlot(gomock.Any(), []string{"partner1", "partner2"}, false).
		Return("booking-123", nil)
	mockBooking.EXPECT().
		AddPlayingPartner("booking-123", "partner1", 2, false).
		Return(nil)
	mockBooking.EXPECT().
		AddPlayingPartner("booking-123", "partner2", 3, false).
		Return(nil)
	mockSMS.EXPECT().
		SendSms("+1234567890", "+0987654321", gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunPartnerAddFailureContinues(t *testing.T) {
	conf := defaultTestConfig()
	conf.PlayingPartners = "partner1,partner2"

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(availableSlots, nil)
	mockBooking.EXPECT().
		BookTimeSlot(gomock.Any(), []string{"partner1", "partner2"}, false).
		Return("booking-123", nil)
	mockBooking.EXPECT().
		AddPlayingPartner("booking-123", "partner1", 2, false).
		Return(errors.New("partner not found"))
	mockBooking.EXPECT().
		AddPlayingPartner("booking-123", "partner2", 3, false).
		Return(nil)
	mockSMS.EXPECT().
		SendSms("+1234567890", "+0987654321", gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunRetryOnNoAvailability(t *testing.T) {
	conf := defaultTestConfig()
	conf.Retries = 2

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	emptySlots := []models.TimeSlot{}
	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)

	gomock.InOrder(
		mockBooking.EXPECT().
			GetCourseAvailability("22-01-2024").
			Return(emptySlots, nil),
		mockBooking.EXPECT().
			GetCourseAvailability("22-01-2024").
			Return(availableSlots, nil),
	)

	mockBooking.EXPECT().
		BookTimeSlot(gomock.Any(), gomock.Any(), false).
		Return("booking-123", nil)
	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunRetryOnBookingFailure(t *testing.T) {
	conf := defaultTestConfig()
	conf.Retries = 2

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(availableSlots, nil).
		Times(2)

	gomock.InOrder(
		mockBooking.EXPECT().
			BookTimeSlot(gomock.Any(), gomock.Any(), false).
			Return("", errors.New("slot taken")),
		mockBooking.EXPECT().
			BookTimeSlot(gomock.Any(), gomock.Any(), false).
			Return("booking-123", nil),
	)

	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunRetryOnEmptyBookingID(t *testing.T) {
	conf := defaultTestConfig()
	conf.Retries = 2

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(availableSlots, nil).
		Times(2)

	gomock.InOrder(
		mockBooking.EXPECT().
			BookTimeSlot(gomock.Any(), gomock.Any(), false).
			Return("", nil),
		mockBooking.EXPECT().
			BookTimeSlot(gomock.Any(), gomock.Any(), false).
			Return("booking-123", nil),
	)

	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunAllRetriesExhausted(t *testing.T) {
	conf := defaultTestConfig()
	conf.Retries = 2

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	emptySlots := []models.TimeSlot{}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(emptySlots, nil).
		Times(2)

	mockSMS.EXPECT().
		SendSms("+1234567890", "+0987654321", gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.Error(t, err)
	assert.True(t, errors.Is(err, ErrNoBooking))
}

func TestRunSendsFailureSMS(t *testing.T) {
	conf := defaultTestConfig()
	conf.Retries = 1

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	emptySlots := []models.TimeSlot{}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(emptySlots, nil)

	mockSMS.EXPECT().
		SendSms("+1234567890", "+0987654321", "Failed to book tee time on 22-01-2024", false).
		Return(nil)

	err := app.Run()

	assert.Error(t, err)
}

func TestRunSMSErrorDoesNotFailBooking(t *testing.T) {
	app, mockBooking, mockSMS, ctrl := createTestApp(t, defaultTestConfig())
	defer ctrl.Finish()

	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(availableSlots, nil)
	mockBooking.EXPECT().
		BookTimeSlot(gomock.Any(), gomock.Any(), false).
		Return("booking-123", nil)
	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), false).
		Return(errors.New("SMS failed"))

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunDryRunMode(t *testing.T) {
	conf := defaultTestConfig()
	conf.DryRun = true

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(availableSlots, nil)
	mockBooking.EXPECT().
		BookTimeSlot(gomock.Any(), gomock.Any(), true).
		Return("dry-run-123", nil)
	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), true).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunFiltersNonBookableSlots(t *testing.T) {
	conf := defaultTestConfig()
	conf.Retries = 1

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	slotsWithNonBookable := []models.TimeSlot{
		{Time: "10:00", CanBook: false, BookingForm: map[string]string{"id": "1"}},
		{Time: "11:00", CanBook: false, BookingForm: map[string]string{"id": "2"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(slotsWithNonBookable, nil)

	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.Error(t, err)
	assert.True(t, errors.Is(err, ErrNoBooking))
}

func TestRunFiltersOutsideTimeRange(t *testing.T) {
	conf := defaultTestConfig()
	conf.TimeStart = "14:00"
	conf.TimeEnd = "16:00"
	conf.Retries = 1

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	slotsOutsideRange := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
		{Time: "11:00", CanBook: true, BookingForm: map[string]string{"id": "2"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("22-01-2024").
		Return(slotsOutsideRange, nil)

	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.Error(t, err)
	assert.True(t, errors.Is(err, ErrNoBooking))
}

func TestRunUsesCorrectDateFormat(t *testing.T) {
	conf := defaultTestConfig()
	conf.DaysAhead = 10

	app, mockBooking, mockSMS, ctrl := createTestApp(t, conf)
	defer ctrl.Finish()

	app.TimeNow = func() time.Time {
		return time.Date(2024, 3, 5, 10, 0, 0, 0, time.UTC)
	}

	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)
	mockBooking.EXPECT().
		GetCourseAvailability("15-03-2024").
		Return(availableSlots, nil)
	mockBooking.EXPECT().
		BookTimeSlot(gomock.Any(), gomock.Any(), false).
		Return("booking-123", nil)
	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
}

func TestRunSleepCalledOnRetry(t *testing.T) {
	conf := defaultTestConfig()
	conf.Retries = 2

	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockBooking := mocks.NewMockBookingService(ctrl)
	mockSMS := mocks.NewMockSMSService(ctrl)

	sleepCalled := false
	app := &App{
		Config:        conf,
		BookingClient: mockBooking,
		TwilioClient:  mockSMS,
		TimeNow:       func() time.Time { return time.Date(2024, 1, 15, 10, 0, 0, 0, time.UTC) },
		SleepFunc: func(d time.Duration) {
			sleepCalled = true
			assert.Greater(t, d, time.Duration(0))
		},
	}

	emptySlots := []models.TimeSlot{}
	availableSlots := []models.TimeSlot{
		{Time: "10:00", CanBook: true, BookingForm: map[string]string{"id": "1"}},
	}

	mockBooking.EXPECT().
		Login("testuser", "1234").
		Return(true, nil)

	gomock.InOrder(
		mockBooking.EXPECT().
			GetCourseAvailability("22-01-2024").
			Return(emptySlots, nil),
		mockBooking.EXPECT().
			GetCourseAvailability("22-01-2024").
			Return(availableSlots, nil),
	)

	mockBooking.EXPECT().
		BookTimeSlot(gomock.Any(), gomock.Any(), false).
		Return("booking-123", nil)
	mockSMS.EXPECT().
		SendSms(gomock.Any(), gomock.Any(), gomock.Any(), false).
		Return(nil)

	err := app.Run()

	assert.NoError(t, err)
	assert.True(t, sleepCalled, "SleepFunc should be called on retry")
}
