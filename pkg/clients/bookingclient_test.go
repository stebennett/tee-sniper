package clients

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stebennett/tee-sniper/pkg/models"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// loadFixture loads an HTML fixture file from the testdata directory
func loadFixture(t *testing.T, filename string) []byte {
	t.Helper()
	path := filepath.Join("..", "..", "testdata", filename)
	data, err := os.ReadFile(path)
	require.NoError(t, err, "Failed to load fixture: %s", filename)
	return data
}

// ============================================================================
// NewBookingClient Tests
// ============================================================================

func TestNewBookingClientValidURL(t *testing.T) {
	client, err := NewBookingClient("https://example.com/")

	require.NoError(t, err)
	assert.NotNil(t, client)
	assert.Equal(t, "https://example.com/", client.baseUrl)
	assert.NotNil(t, client.httpClient)
	assert.NotNil(t, client.httpClient.Jar)
}

func TestNewBookingClientEmptyURL(t *testing.T) {
	// Empty URL should still succeed - no URL validation in constructor
	client, err := NewBookingClient("")

	require.NoError(t, err)
	assert.NotNil(t, client)
	assert.Equal(t, "", client.baseUrl)
}

func TestNewBookingClientSetsUserAgent(t *testing.T) {
	client, err := NewBookingClient("https://example.com/")

	require.NoError(t, err)
	assert.NotEmpty(t, client.userAgent)
	// Verify it's one of the predefined user agents
	assert.Contains(t, client.userAgent, "Mozilla")
}

func TestNewBookingClientHasCookieJar(t *testing.T) {
	client, err := NewBookingClient("https://example.com/")

	require.NoError(t, err)
	assert.NotNil(t, client.httpClient.Jar, "HTTP client should have a cookie jar")
}

// ============================================================================
// Login Tests
// ============================================================================

func TestLoginSuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/login.php" && r.Method == "POST" {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "login_success.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	success, err := client.Login("testuser", "testpin")

	assert.NoError(t, err)
	assert.True(t, success)
}

func TestLoginFailure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/login.php" && r.Method == "POST" {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "login_failure.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	success, err := client.Login("testuser", "wrongpin")

	assert.NoError(t, err)
	assert.False(t, success)
}

func TestLoginNon200Status(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	success, err := client.Login("testuser", "testpin")

	assert.NoError(t, err)
	assert.False(t, success)
}

func TestLoginNetworkError(t *testing.T) {
	// Use an invalid URL that will cause a network error
	client, err := NewBookingClient("http://localhost:99999/")
	require.NoError(t, err)

	success, err := client.Login("testuser", "testpin")

	assert.Error(t, err)
	assert.False(t, success)
}

func TestLoginFormParameters(t *testing.T) {
	var capturedForm map[string][]string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/login.php" && r.Method == "POST" {
			err := r.ParseForm()
			require.NoError(t, err)
			capturedForm = r.PostForm
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "login_success.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	_, err = client.Login("myuser123", "mypin456")
	require.NoError(t, err)

	// Verify form parameters
	assert.Equal(t, []string{"login"}, capturedForm["task"])
	assert.Equal(t, []string{"1"}, capturedForm["topmenu"])
	assert.Equal(t, []string{"myuser123"}, capturedForm["memberid"])
	assert.Equal(t, []string{"mypin456"}, capturedForm["pin"])
	assert.Equal(t, []string{"1"}, capturedForm["cachemid"])
	assert.Equal(t, []string{"Login"}, capturedForm["Submit"])
}

func TestLoginSetsCorrectHeaders(t *testing.T) {
	var capturedHeaders http.Header

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/login.php" {
			capturedHeaders = r.Header.Clone()
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "login_success.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	_, err = client.Login("user", "pass")
	require.NoError(t, err)

	assert.Contains(t, capturedHeaders.Get("User-Agent"), "Mozilla")
	assert.Equal(t, "application/x-www-form-urlencoded", capturedHeaders.Get("Content-Type"))
	assert.NotEmpty(t, capturedHeaders.Get("Accept"))
	assert.NotEmpty(t, capturedHeaders.Get("Accept-Language"))
}

// ============================================================================
// GetCourseAvailability Tests
// ============================================================================

func TestGetCourseAvailabilitySuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/memberbooking/" && r.Method == "GET" {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "availability_with_slots.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	slots, err := client.GetCourseAvailability("2024-01-15")

	require.NoError(t, err)
	assert.Len(t, slots, 3)

	// Verify first slot
	assert.Equal(t, "09:00", slots[0].Time)
	assert.True(t, slots[0].CanBook)
	assert.Equal(t, "2024-01-15", slots[0].BookingForm["date"])
	assert.Equal(t, "0900", slots[0].BookingForm["time"])
	assert.Equal(t, "1", slots[0].BookingForm["course"])

	// Verify second slot
	assert.Equal(t, "09:30", slots[1].Time)
	assert.Equal(t, "0930", slots[1].BookingForm["time"])

	// Verify third slot
	assert.Equal(t, "10:00", slots[2].Time)
	assert.Equal(t, "1000", slots[2].BookingForm["time"])
}

func TestGetCourseAvailabilityNoSlots(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/memberbooking/" {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "availability_empty.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	slots, err := client.GetCourseAvailability("2024-01-15")

	require.NoError(t, err)
	assert.Empty(t, slots)
}

func TestGetCourseAvailabilityBlockedSlots(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/memberbooking/" {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "availability_blocked.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	slots, err := client.GetCourseAvailability("2024-01-15")

	require.NoError(t, err)
	// All slots should be filtered out: first two have players/competitions,
	// third has a player but also a booking button - but has player-name so filtered
	assert.Empty(t, slots)
}

func TestGetCourseAvailabilityNon200Status(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	slots, err := client.GetCourseAvailability("2024-01-15")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid status code returned 404")
	assert.Empty(t, slots)
}

func TestGetCourseAvailabilityNetworkError(t *testing.T) {
	client, err := NewBookingClient("http://localhost:99999/")
	require.NoError(t, err)

	slots, err := client.GetCourseAvailability("2024-01-15")

	assert.Error(t, err)
	assert.Empty(t, slots)
}

func TestGetCourseAvailabilityDateParameter(t *testing.T) {
	var capturedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/memberbooking/" {
			capturedQuery = r.URL.RawQuery
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "availability_empty.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	_, err = client.GetCourseAvailability("2024-12-25")
	require.NoError(t, err)

	assert.Contains(t, capturedQuery, "date=2024-12-25")
}

func TestGetCourseAvailabilitySetsCorrectHeaders(t *testing.T) {
	var capturedHeaders http.Header

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/memberbooking/" {
			capturedHeaders = r.Header.Clone()
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "availability_empty.html"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	_, err = client.GetCourseAvailability("2024-01-15")
	require.NoError(t, err)

	assert.Contains(t, capturedHeaders.Get("User-Agent"), "Mozilla")
	assert.NotEmpty(t, capturedHeaders.Get("Accept"))
	assert.NotEmpty(t, capturedHeaders.Get("Accept-Language"))
}

// ============================================================================
// extractBookingID Tests
// ============================================================================

func TestExtractBookingIDValid(t *testing.T) {
	client, _ := NewBookingClient("https://example.com/")

	bookingID, err := client.extractBookingID("https://example.com/memberbooking/?edit=12345&other=param")

	require.NoError(t, err)
	assert.Equal(t, "12345", bookingID)
}

func TestExtractBookingIDMidURL(t *testing.T) {
	client, _ := NewBookingClient("https://example.com/")

	bookingID, err := client.extractBookingID("https://example.com/memberbooking/?other=param&edit=67890&another=value")

	require.NoError(t, err)
	assert.Equal(t, "67890", bookingID)
}

func TestExtractBookingIDMissing(t *testing.T) {
	client, _ := NewBookingClient("https://example.com/")

	bookingID, err := client.extractBookingID("https://example.com/memberbooking/?other=param")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "booking ID not found in URL")
	assert.Empty(t, bookingID)
}

func TestExtractBookingIDEmpty(t *testing.T) {
	client, _ := NewBookingClient("https://example.com/")

	bookingID, err := client.extractBookingID("")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "booking ID not found in URL")
	assert.Empty(t, bookingID)
}

func TestExtractBookingIDNoQueryString(t *testing.T) {
	client, _ := NewBookingClient("https://example.com/")

	bookingID, err := client.extractBookingID("https://example.com/memberbooking/")

	assert.Error(t, err)
	assert.Empty(t, bookingID)
}

func TestExtractBookingIDComplexValue(t *testing.T) {
	client, _ := NewBookingClient("https://example.com/")

	// Test with alphanumeric booking ID
	bookingID, err := client.extractBookingID("https://example.com/?edit=abc123xyz")

	require.NoError(t, err)
	assert.Equal(t, "abc123xyz", bookingID)
}

// ============================================================================
// BookTimeSlot Tests
// ============================================================================

func TestBookTimeSlotDryRun(t *testing.T) {
	// Server should not receive any requests in dry run mode
	requestReceived := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestReceived = true
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	timeSlot := models.TimeSlot{
		Time: "09:00",
		BookingForm: map[string]string{
			"date":   "2024-01-15",
			"time":   "0900",
			"course": "1",
		},
		CanBook: true,
	}

	bookingID, err := client.BookTimeSlot(timeSlot, []string{}, true)

	require.NoError(t, err)
	assert.Equal(t, "dryrun-booking-id", bookingID)
	assert.False(t, requestReceived, "No HTTP request should be made in dry run mode")
}

func TestBookTimeSlotSuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/memberbooking/" {
			// Simulate the booking flow: server returns success page
			// The client expects to read resp.Request.URL after following redirects
			// In our test, we need to handle this differently
			w.Header().Set("Location", "/memberbooking/?edit=BOOK123")
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "booking_success.html"))
		}
	}))
	defer server.Close()

	// Create a custom server that simulates redirects properly
	redirectServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.Contains(r.URL.RawQuery, "edit=") {
			// This is the final URL after redirect
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "booking_success.html"))
		} else {
			// Initial booking request - redirect to edit page
			http.Redirect(w, r, "/memberbooking/?edit=BOOK123", http.StatusFound)
		}
	}))
	defer redirectServer.Close()

	client, err := NewBookingClient(redirectServer.URL + "/")
	require.NoError(t, err)

	timeSlot := models.TimeSlot{
		Time: "09:00",
		BookingForm: map[string]string{
			"date":   "2024-01-15",
			"time":   "0900",
			"course": "1",
		},
		CanBook: true,
	}

	bookingID, err := client.BookTimeSlot(timeSlot, []string{}, false)

	require.NoError(t, err)
	assert.Equal(t, "BOOK123", bookingID)
}

func TestBookTimeSlotFailureNoConfirmation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.Contains(r.URL.RawQuery, "edit=") {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "booking_failure.html"))
		} else {
			http.Redirect(w, r, "/memberbooking/?edit=BOOK123", http.StatusFound)
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	timeSlot := models.TimeSlot{
		Time: "09:00",
		BookingForm: map[string]string{
			"date":   "2024-01-15",
			"time":   "0900",
			"course": "1",
		},
		CanBook: true,
	}

	bookingID, err := client.BookTimeSlot(timeSlot, []string{}, false)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "booking failed")
	assert.Empty(t, bookingID)
}

func TestBookTimeSlotNon200Status(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	timeSlot := models.TimeSlot{
		Time:        "09:00",
		BookingForm: map[string]string{},
		CanBook:     true,
	}

	bookingID, err := client.BookTimeSlot(timeSlot, []string{}, false)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid status code returned 503")
	assert.Empty(t, bookingID)
}

func TestBookTimeSlotNetworkError(t *testing.T) {
	client, err := NewBookingClient("http://localhost:99999/")
	require.NoError(t, err)

	timeSlot := models.TimeSlot{
		Time:        "09:00",
		BookingForm: map[string]string{},
		CanBook:     true,
	}

	bookingID, err := client.BookTimeSlot(timeSlot, []string{}, false)

	assert.Error(t, err)
	assert.Empty(t, bookingID)
}

func TestBookTimeSlotNumSlotsCalculation(t *testing.T) {
	var capturedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.Contains(r.URL.RawQuery, "edit=") {
			capturedQuery = r.URL.RawQuery
		}
		if strings.Contains(r.URL.RawQuery, "edit=") {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "booking_success.html"))
		} else {
			http.Redirect(w, r, "/memberbooking/?edit=BOOK123", http.StatusFound)
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	timeSlot := models.TimeSlot{
		Time: "09:00",
		BookingForm: map[string]string{
			"date": "2024-01-15",
		},
		CanBook: true,
	}

	// Test with 2 playing partners (should be 3 total slots)
	_, err = client.BookTimeSlot(timeSlot, []string{"partner1", "partner2"}, false)
	require.NoError(t, err)

	assert.Contains(t, capturedQuery, "numslots=3")
}

func TestBookTimeSlotNumSlotsNoPartners(t *testing.T) {
	var capturedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.Contains(r.URL.RawQuery, "edit=") {
			capturedQuery = r.URL.RawQuery
		}
		if strings.Contains(r.URL.RawQuery, "edit=") {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "booking_success.html"))
		} else {
			http.Redirect(w, r, "/memberbooking/?edit=BOOK123", http.StatusFound)
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	timeSlot := models.TimeSlot{
		Time: "09:00",
		BookingForm: map[string]string{
			"date": "2024-01-15",
		},
		CanBook: true,
	}

	// Test with no playing partners (should be 1 slot)
	_, err = client.BookTimeSlot(timeSlot, []string{}, false)
	require.NoError(t, err)

	assert.Contains(t, capturedQuery, "numslots=1")
}

func TestBookTimeSlotPassesBookingFormParams(t *testing.T) {
	var capturedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.Contains(r.URL.RawQuery, "edit=") {
			capturedQuery = r.URL.RawQuery
		}
		if strings.Contains(r.URL.RawQuery, "edit=") {
			w.WriteHeader(http.StatusOK)
			w.Write(loadFixture(t, "booking_success.html"))
		} else {
			http.Redirect(w, r, "/memberbooking/?edit=BOOK123", http.StatusFound)
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	timeSlot := models.TimeSlot{
		Time: "09:00",
		BookingForm: map[string]string{
			"date":   "2024-01-15",
			"time":   "0900",
			"course": "1",
			"holes":  "18",
		},
		CanBook: true,
	}

	_, err = client.BookTimeSlot(timeSlot, []string{}, false)
	require.NoError(t, err)

	assert.Contains(t, capturedQuery, "date=2024-01-15")
	assert.Contains(t, capturedQuery, "time=0900")
	assert.Contains(t, capturedQuery, "course=1")
	assert.Contains(t, capturedQuery, "holes=18")
}

// ============================================================================
// AddPlayingPartner Tests
// ============================================================================

func TestAddPlayingPartnerSuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/memberbooking/" {
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("<html><body>Partner added</body></html>"))
		}
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	err = client.AddPlayingPartner("BOOK123", "partner456", 2, false)

	assert.NoError(t, err)
}

func TestAddPlayingPartnerDryRun(t *testing.T) {
	requestReceived := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestReceived = true
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	err = client.AddPlayingPartner("BOOK123", "partner456", 2, true)

	assert.NoError(t, err)
	assert.False(t, requestReceived, "No HTTP request should be made in dry run mode")
}

func TestAddPlayingPartnerNon200Status(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	err = client.AddPlayingPartner("BOOK123", "partner456", 2, false)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to add partner: status code 400")
}

func TestAddPlayingPartnerNetworkError(t *testing.T) {
	client, err := NewBookingClient("http://localhost:99999/")
	require.NoError(t, err)

	err = client.AddPlayingPartner("BOOK123", "partner456", 2, false)

	assert.Error(t, err)
}

func TestAddPlayingPartnerQueryParameters(t *testing.T) {
	var capturedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedQuery = r.URL.RawQuery
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	err = client.AddPlayingPartner("BOOK123", "partner456", 3, false)
	require.NoError(t, err)

	assert.Contains(t, capturedQuery, "edit=BOOK123")
	assert.Contains(t, capturedQuery, "addpartner=partner456")
	assert.Contains(t, capturedQuery, "partnerslot=3")
}

func TestAddPlayingPartnerSetsCorrectHeaders(t *testing.T) {
	var capturedHeaders http.Header

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedHeaders = r.Header.Clone()
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client, err := NewBookingClient(server.URL + "/")
	require.NoError(t, err)

	err = client.AddPlayingPartner("BOOK123", "partner456", 2, false)
	require.NoError(t, err)

	assert.Contains(t, capturedHeaders.Get("User-Agent"), "Mozilla")
	assert.NotEmpty(t, capturedHeaders.Get("Accept"))
}

// ============================================================================
// addBrowserHeaders Tests
// ============================================================================

func TestAddBrowserHeadersSetsAllHeaders(t *testing.T) {
	client, err := NewBookingClient("https://example.com/")
	require.NoError(t, err)

	req, _ := http.NewRequest("GET", "https://example.com/test", nil)
	client.addBrowserHeaders(req)

	assert.Contains(t, req.Header.Get("User-Agent"), "Mozilla")
	assert.Equal(t, "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", req.Header.Get("Accept"))
	assert.Equal(t, "en-US,en;q=0.5", req.Header.Get("Accept-Language"))
	assert.Equal(t, "gzip, deflate", req.Header.Get("Accept-Encoding"))
	assert.Equal(t, "keep-alive", req.Header.Get("Connection"))
	assert.Equal(t, "1", req.Header.Get("Upgrade-Insecure-Requests"))
}

// ============================================================================
// Interface Compliance Tests
// ============================================================================

func TestBookingClientImplementsBookingService(t *testing.T) {
	var _ BookingService = (*BookingClient)(nil)
}
