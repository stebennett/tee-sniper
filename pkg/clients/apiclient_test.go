package clients

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stebennett/tee-sniper/pkg/crypto"
	"github.com/stebennett/tee-sniper/pkg/models"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

const testSharedSecret = "test-shared-secret"

func TestAPIClientLogin_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodPost, r.Method)
		assert.Equal(t, "/api/login", r.URL.Path)
		assert.Equal(t, "application/json", r.Header.Get("Content-Type"))

		var req loginRequest
		require.NoError(t, json.NewDecoder(r.Body).Decode(&req))

		// Verify we can decrypt the credentials
		username, pin, err := crypto.DecryptCredentials(req.Credentials, testSharedSecret)
		require.NoError(t, err)
		assert.Equal(t, "testuser", username)
		assert.Equal(t, "1234", pin)

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(loginResponse{
			AccessToken: "test-token-123",
			ExpiresAt:   "2026-03-30T12:00:00Z",
		})
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	ok, err := client.Login("testuser", "1234")

	require.NoError(t, err)
	assert.True(t, ok)
	assert.Equal(t, "test-token-123", client.accessToken)
}

func TestAPIClientLogin_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(errorResponse{Detail: "invalid credentials"})
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	ok, err := client.Login("baduser", "wrong")

	require.NoError(t, err)
	assert.False(t, ok)
}

func TestAPIClientLogin_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(errorResponse{Detail: "internal error"})
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	_, err := client.Login("user", "pin")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "500")
}

func TestAPIClientGetCourseAvailability(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodGet, r.Method)
		assert.Equal(t, "/api/2026-04-05/times", r.URL.Path)
		assert.Equal(t, "Bearer test-token", r.Header.Get("Authorization"))

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(availabilityResponse{
			Date: "2026-04-05",
			Times: []timeSlotResponse{
				{Time: "08:00", CanBook: true, BookingForm: map[string]string{"key": "val"}},
				{Time: "09:30", CanBook: false, BookingForm: map[string]string{}},
			},
			FilteredCount: 2,
			TotalCount:    10,
		})
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	client.accessToken = "test-token"

	slots, err := client.GetCourseAvailability("05-04-2026")
	require.NoError(t, err)
	require.Len(t, slots, 2)

	assert.Equal(t, "08:00", slots[0].Time)
	assert.True(t, slots[0].CanBook)
	assert.Equal(t, map[string]string{"key": "val"}, slots[0].BookingForm)

	assert.Equal(t, "09:30", slots[1].Time)
	assert.False(t, slots[1].CanBook)

	// Verify lastDate was stored
	assert.Equal(t, "2026-04-05", client.lastDate)
}

func TestAPIClientGetCourseAvailability_InvalidDate(t *testing.T) {
	client := NewAPIClient("http://localhost", testSharedSecret)
	_, err := client.GetCourseAvailability("invalid-date")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "convert date")
}

func TestAPIClientBookTimeSlot(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodPost, r.Method)
		assert.Equal(t, "/api/2026-04-05/time/10:00/book", r.URL.Path)
		assert.Equal(t, "Bearer test-token", r.Header.Get("Authorization"))

		var req bookRequest
		require.NoError(t, json.NewDecoder(r.Body).Decode(&req))
		assert.Equal(t, 3, req.NumSlots)
		assert.True(t, req.DryRun)

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(bookResponse{
			BookingID:   "booking-456",
			Date:        "2026-04-05",
			Time:        "10:00",
			SlotsBooked: 3,
			Message:     "Successfully booked tee time",
		})
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	client.accessToken = "test-token"
	client.lastDate = "2026-04-05"

	slot := models.TimeSlot{Time: "10:00", CanBook: true}
	partners := []string{"p1", "p2"}
	bookingID, err := client.BookTimeSlot(slot, partners, true)

	require.NoError(t, err)
	assert.Equal(t, "booking-456", bookingID)
	assert.Equal(t, "booking-456", client.lastBooking)
	assert.Nil(t, client.partners) // reset on new booking
}

func TestAPIClientBookTimeSlot_NoDate(t *testing.T) {
	client := NewAPIClient("http://localhost", testSharedSecret)
	_, err := client.BookTimeSlot(models.TimeSlot{Time: "10:00"}, nil, false)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "no date available")
}

func TestAPIClientAddPlayingPartner(t *testing.T) {
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodPatch, r.Method)
		assert.Equal(t, "/api/bookings/booking-789", r.URL.Path)

		var req addPartnersRequest
		require.NoError(t, json.NewDecoder(r.Body).Decode(&req))

		callCount++
		w.Header().Set("Content-Type", "application/json")

		switch callCount {
		case 1:
			// First call: single partner
			assert.Equal(t, []string{"partner1"}, req.Partners)
			assert.False(t, req.DryRun)
			json.NewEncoder(w).Encode(addPartnersResponse{
				BookingID:     "booking-789",
				PartnersAdded: []string{"partner1"},
			})
		case 2:
			// Second call: accumulated list
			assert.Equal(t, []string{"partner1", "partner2"}, req.Partners)
			w.WriteHeader(http.StatusMultiStatus)
			json.NewEncoder(w).Encode(addPartnersResponse{
				BookingID:      "booking-789",
				PartnersAdded:  []string{"partner2"},
				PartnersFailed: []string{"partner1"}, // already added, harmless failure
			})
		}
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	client.accessToken = "test-token"
	client.lastBooking = "booking-789"

	// First partner
	err := client.AddPlayingPartner("booking-789", "partner1", 2, false)
	require.NoError(t, err)

	// Second partner - accumulates
	err = client.AddPlayingPartner("booking-789", "partner2", 3, false)
	require.NoError(t, err)

	assert.Equal(t, 2, callCount)
}

func TestAPIClientAddPlayingPartner_NewPartnerFails(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusMultiStatus)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(addPartnersResponse{
			BookingID:      "booking-789",
			PartnersAdded:  []string{},
			PartnersFailed: []string{"badpartner"},
		})
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	client.accessToken = "test-token"
	client.lastBooking = "booking-789"

	err := client.AddPlayingPartner("booking-789", "badpartner", 2, false)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to add partner badpartner")
}

func TestAPIClientAddPlayingPartner_ResetsOnNewBooking(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req addPartnersRequest
		require.NoError(t, json.NewDecoder(r.Body).Decode(&req))

		// Should only have one partner since booking ID changed
		assert.Len(t, req.Partners, 1)

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(addPartnersResponse{
			BookingID:     "booking-new",
			PartnersAdded: req.Partners,
		})
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	client.accessToken = "test-token"
	client.lastBooking = "booking-old"
	client.partners = []string{"old-partner"}

	err := client.AddPlayingPartner("booking-new", "new-partner", 2, false)
	require.NoError(t, err)
	assert.Equal(t, []string{"new-partner"}, client.partners)
}

func TestAPIClientAddPlayingPartner_AllFail(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(errorResponse{Detail: "Failed to add any partners"})
	}))
	defer server.Close()

	client := NewAPIClient(server.URL, testSharedSecret)
	client.accessToken = "test-token"
	client.lastBooking = "booking-789"

	err := client.AddPlayingPartner("booking-789", "partner1", 2, false)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "502")
}

func TestConvertDateFormat(t *testing.T) {
	tests := []struct {
		input    string
		expected string
		hasError bool
	}{
		{"05-04-2026", "2026-04-05", false},
		{"31-12-2025", "2025-12-31", false},
		{"01-01-2026", "2026-01-01", false},
		{"invalid", "", true},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result, err := convertDateFormat(tt.input)
			if tt.hasError {
				assert.Error(t, err)
			} else {
				require.NoError(t, err)
				assert.Equal(t, tt.expected, result)
			}
		})
	}
}

func TestAPIClientTrailingSlash(t *testing.T) {
	client := NewAPIClient("http://localhost:8000/", testSharedSecret)
	assert.Equal(t, "http://localhost:8000", client.apiURL)
}
