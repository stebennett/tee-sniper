package clients

import (
	"bytes"
	"errors"
	"io"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockHTTPClient is a mock implementation of HTTPClient for testing
type mockHTTPClient struct {
	doFunc    func(req *http.Request) (*http.Response, error)
	lastReq   *http.Request
	callCount int
}

func (m *mockHTTPClient) Do(req *http.Request) (*http.Response, error) {
	m.lastReq = req
	m.callCount++
	if m.doFunc != nil {
		return m.doFunc(req)
	}
	return &http.Response{
		StatusCode: 200,
		Body:       io.NopCloser(bytes.NewBufferString("")),
	}, nil
}

func TestNewAppriseClient(t *testing.T) {
	urls := "http://localhost:8000/notify"
	tag := "sms"
	client := NewAppriseClient(urls, tag)

	require.NotNil(t, client)
	assert.Equal(t, urls, client.urls)
	assert.Equal(t, tag, client.tag)
	assert.NotNil(t, client.httpClient)
}

func TestNewAppriseClientWithEmptyTag(t *testing.T) {
	urls := "http://localhost:8000/notify"
	client := NewAppriseClient(urls, "")

	require.NotNil(t, client)
	assert.Equal(t, urls, client.urls)
	assert.Equal(t, "", client.tag)
}

func TestNewAppriseClientWithHTTPClient(t *testing.T) {
	urls := "http://localhost:8000/notify"
	tag := "email"
	mockClient := &mockHTTPClient{}

	client := NewAppriseClientWithHTTPClient(urls, tag, mockClient)

	require.NotNil(t, client)
	assert.Equal(t, urls, client.urls)
	assert.Equal(t, tag, client.tag)
	assert.Equal(t, mockClient, client.httpClient)
}

func TestSendNotificationDryRun(t *testing.T) {
	mockClient := &mockHTTPClient{
		doFunc: func(req *http.Request) (*http.Response, error) {
			t.Error("HTTP request should not be made in dry run mode")
			return nil, nil
		},
	}
	client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", mockClient)

	err := client.SendNotification("Test message", true)

	assert.NoError(t, err)
	assert.Equal(t, 0, mockClient.callCount, "No HTTP calls should be made in dry run mode")
}

func TestSendNotificationDryRunWithVariousMessages(t *testing.T) {
	testCases := []struct {
		name    string
		message string
	}{
		{
			name:    "simple message",
			message: "Hello, World!",
		},
		{
			name:    "empty message",
			message: "",
		},
		{
			name:    "long message",
			message: "This is a very long message that might span multiple lines in a real notification scenario but should still work fine in dry run mode.",
		},
		{
			name:    "message with special characters",
			message: "Tee time booked! 🏌️ See you at 3:00 PM",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			mockClient := &mockHTTPClient{}
			client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", mockClient)

			err := client.SendNotification(tc.message, true)

			assert.NoError(t, err)
			assert.Equal(t, 0, mockClient.callCount)
		})
	}
}

func TestSendNotificationSuccess(t *testing.T) {
	mockClient := &mockHTTPClient{
		doFunc: func(req *http.Request) (*http.Response, error) {
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBufferString(`{"status": "ok"}`)),
			}, nil
		},
	}
	client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", mockClient)

	err := client.SendNotification("Test message", false)

	assert.NoError(t, err)
	assert.Equal(t, 1, mockClient.callCount)
	require.NotNil(t, mockClient.lastReq)
	assert.Equal(t, "POST", mockClient.lastReq.Method)
	assert.Equal(t, "application/json", mockClient.lastReq.Header.Get("Content-Type"))
}

func TestSendNotificationHTTPError(t *testing.T) {
	expectedError := errors.New("network error")
	mockClient := &mockHTTPClient{
		doFunc: func(req *http.Request) (*http.Response, error) {
			return nil, expectedError
		},
	}
	client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", mockClient)

	err := client.SendNotification("Test message", false)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to send apprise notification")
}

func TestSendNotificationNon2xxStatus(t *testing.T) {
	testCases := []struct {
		name       string
		statusCode int
		body       string
	}{
		{
			name:       "400 Bad Request",
			statusCode: 400,
			body:       "invalid request",
		},
		{
			name:       "401 Unauthorized",
			statusCode: 401,
			body:       "unauthorized",
		},
		{
			name:       "500 Internal Server Error",
			statusCode: 500,
			body:       "server error",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			mockClient := &mockHTTPClient{
				doFunc: func(req *http.Request) (*http.Response, error) {
					return &http.Response{
						StatusCode: tc.statusCode,
						Body:       io.NopCloser(bytes.NewBufferString(tc.body)),
					}, nil
				},
			}
			client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", mockClient)

			err := client.SendNotification("Test message", false)

			assert.Error(t, err)
			assert.Contains(t, err.Error(), "apprise notification failed")
			assert.Contains(t, err.Error(), tc.body)
		})
	}
}

func TestSendNotificationRequestBody(t *testing.T) {
	urls := "http://localhost:8000/notify"
	message := "Your tee time has been booked!"

	var capturedBody []byte
	mockClient := &mockHTTPClient{
		doFunc: func(req *http.Request) (*http.Response, error) {
			capturedBody, _ = io.ReadAll(req.Body)
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBufferString("")),
			}, nil
		},
	}
	client := NewAppriseClientWithHTTPClient(urls, "", mockClient)

	err := client.SendNotification(message, false)

	assert.NoError(t, err)
	assert.Contains(t, string(capturedBody), `"urls":"http://localhost:8000/notify"`)
	assert.Contains(t, string(capturedBody), `"body":"Your tee time has been booked!"`)
	// Tag should be omitted when empty
	assert.NotContains(t, string(capturedBody), `"tag"`)
}

func TestSendNotificationRequestBodyWithTag(t *testing.T) {
	urls := "http://localhost:8000/notify"
	tag := "sms"
	message := "Your tee time has been booked!"

	var capturedBody []byte
	mockClient := &mockHTTPClient{
		doFunc: func(req *http.Request) (*http.Response, error) {
			capturedBody, _ = io.ReadAll(req.Body)
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBufferString("")),
			}, nil
		},
	}
	client := NewAppriseClientWithHTTPClient(urls, tag, mockClient)

	err := client.SendNotification(message, false)

	assert.NoError(t, err)
	assert.Contains(t, string(capturedBody), `"urls":"http://localhost:8000/notify"`)
	assert.Contains(t, string(capturedBody), `"body":"Your tee time has been booked!"`)
	assert.Contains(t, string(capturedBody), `"tag":"sms"`)
}

func TestAppriseClientImplementsNotificationService(t *testing.T) {
	// This is a compile-time check - if AppriseClient doesn't implement NotificationService,
	// this will fail to compile
	var _ NotificationService = (*AppriseClient)(nil)

	// Runtime verification
	client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", &mockHTTPClient{})
	var notificationService NotificationService = client
	assert.NotNil(t, notificationService)
}

func TestSendNotificationNotCalledInDryRun(t *testing.T) {
	callCount := 0
	mockClient := &mockHTTPClient{
		doFunc: func(req *http.Request) (*http.Response, error) {
			callCount++
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBufferString("")),
			}, nil
		},
	}
	client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", mockClient)

	// Call multiple times in dry run mode
	for i := 0; i < 5; i++ {
		err := client.SendNotification("Test", true)
		assert.NoError(t, err)
	}

	assert.Equal(t, 0, callCount, "HTTP request should never be made in dry run mode")
}

func TestSendNotificationCalledOncePerRequest(t *testing.T) {
	callCount := 0
	mockClient := &mockHTTPClient{
		doFunc: func(req *http.Request) (*http.Response, error) {
			callCount++
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBufferString("")),
			}, nil
		},
	}
	client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", mockClient)

	err := client.SendNotification("Test", false)

	assert.NoError(t, err)
	assert.Equal(t, 1, callCount, "HTTP request should be made exactly once")
}

func TestSendNotification2xxStatusCodes(t *testing.T) {
	testCases := []struct {
		name       string
		statusCode int
	}{
		{name: "200 OK", statusCode: 200},
		{name: "201 Created", statusCode: 201},
		{name: "202 Accepted", statusCode: 202},
		{name: "204 No Content", statusCode: 204},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			mockClient := &mockHTTPClient{
				doFunc: func(req *http.Request) (*http.Response, error) {
					return &http.Response{
						StatusCode: tc.statusCode,
						Body:       io.NopCloser(bytes.NewBufferString("")),
					}, nil
				},
			}
			client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", "", mockClient)

			err := client.SendNotification("Test message", false)

			assert.NoError(t, err)
		})
	}
}

func TestSendNotificationWithVariousTags(t *testing.T) {
	testCases := []struct {
		name        string
		tag         string
		expectInBody bool
	}{
		{
			name:        "empty tag",
			tag:         "",
			expectInBody: false,
		},
		{
			name:        "sms tag",
			tag:         "sms",
			expectInBody: true,
		},
		{
			name:        "email tag",
			tag:         "email",
			expectInBody: true,
		},
		{
			name:        "multiple tags",
			tag:         "sms,email",
			expectInBody: true,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			var capturedBody []byte
			mockClient := &mockHTTPClient{
				doFunc: func(req *http.Request) (*http.Response, error) {
					capturedBody, _ = io.ReadAll(req.Body)
					return &http.Response{
						StatusCode: 200,
						Body:       io.NopCloser(bytes.NewBufferString("")),
					}, nil
				},
			}
			client := NewAppriseClientWithHTTPClient("http://localhost:8000/notify", tc.tag, mockClient)

			err := client.SendNotification("Test message", false)

			assert.NoError(t, err)
			if tc.expectInBody {
				assert.Contains(t, string(capturedBody), `"tag":"`+tc.tag+`"`)
			} else {
				assert.NotContains(t, string(capturedBody), `"tag"`)
			}
		})
	}
}
