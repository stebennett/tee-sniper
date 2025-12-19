package clients

import (
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	twilioApi "github.com/twilio/twilio-go/rest/api/v2010"
)

// mockMessageCreator is a mock implementation of MessageCreator for testing
type mockMessageCreator struct {
	createMessageFunc func(params *twilioApi.CreateMessageParams) (*twilioApi.ApiV2010Message, error)
	lastParams        *twilioApi.CreateMessageParams
}

func (m *mockMessageCreator) CreateMessage(params *twilioApi.CreateMessageParams) (*twilioApi.ApiV2010Message, error) {
	m.lastParams = params
	if m.createMessageFunc != nil {
		return m.createMessageFunc(params)
	}
	return &twilioApi.ApiV2010Message{}, nil
}

// TestNewTwilioClient tests that the constructor creates a valid client
func TestNewTwilioClient(t *testing.T) {
	client := NewTwilioClient()
	assert.NotNil(t, client)
}

// TestNewTwilioClientReturnsNonNil verifies the client is properly initialized
func TestNewTwilioClientReturnsNonNil(t *testing.T) {
	client := NewTwilioClient()
	require.NotNil(t, client)
	assert.NotNil(t, client.messageCreator)
}

// TestNewTwilioClientWithCreator tests the constructor with custom MessageCreator
func TestNewTwilioClientWithCreator(t *testing.T) {
	mock := &mockMessageCreator{}
	client := NewTwilioClientWithCreator(mock)

	require.NotNil(t, client)
	assert.Equal(t, mock, client.messageCreator)
}

// TestSendSmsDryRun tests that dry run mode logs but doesn't send
func TestSendSmsDryRun(t *testing.T) {
	mock := &mockMessageCreator{
		createMessageFunc: func(params *twilioApi.CreateMessageParams) (*twilioApi.ApiV2010Message, error) {
			t.Error("CreateMessage should not be called in dry run mode")
			return nil, nil
		},
	}
	client := NewTwilioClientWithCreator(mock)

	err := client.SendSms("+1234567890", "+0987654321", "Test message", true)

	assert.NoError(t, err)
	assert.Nil(t, mock.lastParams, "No parameters should be set in dry run mode")
}

// TestSendSmsDryRunWithVariousInputs tests dry run with different input combinations
func TestSendSmsDryRunWithVariousInputs(t *testing.T) {
	testCases := []struct {
		name string
		from string
		to   string
		body string
	}{
		{
			name: "standard phone numbers",
			from: "+1234567890",
			to:   "+0987654321",
			body: "Hello, World!",
		},
		{
			name: "empty body",
			from: "+1111111111",
			to:   "+2222222222",
			body: "",
		},
		{
			name: "long message body",
			from: "+1234567890",
			to:   "+0987654321",
			body: "This is a very long message that might span multiple SMS segments in a real scenario but should still work fine in dry run mode.",
		},
		{
			name: "special characters in body",
			from: "+1234567890",
			to:   "+0987654321",
			body: "Tee time booked! 🏌️ See you at 3:00 PM",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			mock := &mockMessageCreator{}
			client := NewTwilioClientWithCreator(mock)

			err := client.SendSms(tc.from, tc.to, tc.body, true)

			assert.NoError(t, err)
			assert.Nil(t, mock.lastParams)
		})
	}
}

// TestSendSmsSuccess tests successful message sending
func TestSendSmsSuccess(t *testing.T) {
	mock := &mockMessageCreator{
		createMessageFunc: func(params *twilioApi.CreateMessageParams) (*twilioApi.ApiV2010Message, error) {
			sid := "SM1234567890"
			return &twilioApi.ApiV2010Message{Sid: &sid}, nil
		},
	}
	client := NewTwilioClientWithCreator(mock)

	err := client.SendSms("+1234567890", "+0987654321", "Test message", false)

	assert.NoError(t, err)
	require.NotNil(t, mock.lastParams)
}

// TestSendSmsAPIError tests error handling from the Twilio API
func TestSendSmsAPIError(t *testing.T) {
	expectedError := errors.New("Twilio API error: invalid phone number")
	mock := &mockMessageCreator{
		createMessageFunc: func(params *twilioApi.CreateMessageParams) (*twilioApi.ApiV2010Message, error) {
			return nil, expectedError
		},
	}
	client := NewTwilioClientWithCreator(mock)

	err := client.SendSms("+1234567890", "+0987654321", "Test message", false)

	assert.Error(t, err)
	assert.Equal(t, expectedError, err)
}

// TestSendSmsPassesCorrectParameters verifies the correct parameters are passed to Twilio
func TestSendSmsPassesCorrectParameters(t *testing.T) {
	from := "+1234567890"
	to := "+0987654321"
	body := "Your tee time has been booked!"

	mock := &mockMessageCreator{}
	client := NewTwilioClientWithCreator(mock)

	err := client.SendSms(from, to, body, false)

	assert.NoError(t, err)
	require.NotNil(t, mock.lastParams)
	assert.Equal(t, to, *mock.lastParams.To)
	assert.Equal(t, from, *mock.lastParams.From)
	assert.Equal(t, body, *mock.lastParams.Body)
}

// TestTwilioClientImplementsSMSService verifies interface compliance at compile time
func TestTwilioClientImplementsSMSService(t *testing.T) {
	// This is a compile-time check - if TwilioClient doesn't implement SMSService,
	// this will fail to compile
	var _ SMSService = (*TwilioClient)(nil)

	// Runtime verification
	client := NewTwilioClientWithCreator(&mockMessageCreator{})
	var smsService SMSService = client
	assert.NotNil(t, smsService)
}

// TestSendSmsNotCalledInDryRun double-checks that API is never called in dry run
func TestSendSmsNotCalledInDryRun(t *testing.T) {
	callCount := 0
	mock := &mockMessageCreator{
		createMessageFunc: func(params *twilioApi.CreateMessageParams) (*twilioApi.ApiV2010Message, error) {
			callCount++
			return &twilioApi.ApiV2010Message{}, nil
		},
	}
	client := NewTwilioClientWithCreator(mock)

	// Call multiple times in dry run mode
	for i := 0; i < 5; i++ {
		err := client.SendSms("+1234567890", "+0987654321", "Test", true)
		assert.NoError(t, err)
	}

	assert.Equal(t, 0, callCount, "CreateMessage should never be called in dry run mode")
}

// TestSendSmsCalledOncePerRequest verifies API is called exactly once per non-dry-run request
func TestSendSmsCalledOncePerRequest(t *testing.T) {
	callCount := 0
	mock := &mockMessageCreator{
		createMessageFunc: func(params *twilioApi.CreateMessageParams) (*twilioApi.ApiV2010Message, error) {
			callCount++
			return &twilioApi.ApiV2010Message{}, nil
		},
	}
	client := NewTwilioClientWithCreator(mock)

	err := client.SendSms("+1234567890", "+0987654321", "Test", false)

	assert.NoError(t, err)
	assert.Equal(t, 1, callCount, "CreateMessage should be called exactly once")
}
