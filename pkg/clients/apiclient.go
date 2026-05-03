package clients

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/stebennett/tee-sniper/pkg/crypto"
	"github.com/stebennett/tee-sniper/pkg/models"
)

// API request/response types

type loginRequest struct {
	Credentials string `json:"credentials"`
}

type loginResponse struct {
	AccessToken string `json:"access_token"`
	ExpiresAt   string `json:"expires_at"`
}

type timeSlotResponse struct {
	Time        string            `json:"time"`
	CanBook     bool              `json:"can_book"`
	BookingForm map[string]string `json:"booking_form"`
}

type availabilityResponse struct {
	Date          string             `json:"date"`
	Times         []timeSlotResponse `json:"times"`
	FilteredCount int                `json:"filtered_count"`
	TotalCount    int                `json:"total_count"`
}

type bookRequest struct {
	NumSlots int  `json:"num_slots"`
	DryRun   bool `json:"dry_run"`
}

type bookResponse struct {
	BookingID   string `json:"booking_id"`
	Date        string `json:"date"`
	Time        string `json:"time"`
	SlotsBooked int    `json:"slots_booked"`
	Message     string `json:"message"`
}

type addPartnersRequest struct {
	Partners []string `json:"partners"`
	DryRun   bool     `json:"dry_run"`
}

type addPartnersResponse struct {
	BookingID      string   `json:"booking_id"`
	PartnersAdded  []string `json:"partners_added"`
	PartnersFailed []string `json:"partners_failed"`
	Message        string   `json:"message"`
}

type errorResponse struct {
	Detail string `json:"detail"`
}

// APIClient implements BookingService by communicating with the tee-sniper API.
type APIClient struct {
	apiURL       string
	sharedSecret string
	httpClient   *http.Client
	accessToken  string
	lastDate     string   // YYYY-MM-DD format, set by GetCourseAvailability
	partners     []string // accumulated partners for current booking
	lastBooking  string   // current booking ID for partner accumulation reset
}

// NewAPIClient creates a new API client.
func NewAPIClient(apiURL, sharedSecret string) *APIClient {
	return &APIClient{
		apiURL:       strings.TrimRight(apiURL, "/"),
		sharedSecret: sharedSecret,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// Login authenticates with the API using encrypted credentials.
func (c *APIClient) Login(username, password string) (bool, error) {
	encrypted, err := crypto.EncryptCredentials(username, password, c.sharedSecret)
	if err != nil {
		return false, fmt.Errorf("failed to encrypt credentials: %w", err)
	}

	body, err := json.Marshal(loginRequest{Credentials: encrypted})
	if err != nil {
		return false, fmt.Errorf("failed to marshal login request: %w", err)
	}

	resp, err := c.doRequest(http.MethodPost, "/api/login", body, false)
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		return false, nil
	}

	if resp.StatusCode != http.StatusOK {
		return false, c.readError(resp)
	}

	var loginResp loginResponse
	if err := json.NewDecoder(resp.Body).Decode(&loginResp); err != nil {
		return false, fmt.Errorf("failed to decode login response: %w", err)
	}

	c.accessToken = loginResp.AccessToken
	return true, nil
}

// GetCourseAvailability retrieves available tee times for the given date.
// dateStr should be in DD-MM-YYYY format (as used by the Go CLI).
func (c *APIClient) GetCourseAvailability(dateStr string) ([]models.TimeSlot, error) {
	apiDate, err := convertDateFormat(dateStr)
	if err != nil {
		return nil, fmt.Errorf("failed to convert date format: %w", err)
	}
	c.lastDate = apiDate

	path := fmt.Sprintf("/api/%s/times", apiDate)
	resp, err := c.doRequest(http.MethodGet, path, nil, true)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, c.readError(resp)
	}

	var availResp availabilityResponse
	if err := json.NewDecoder(resp.Body).Decode(&availResp); err != nil {
		return nil, fmt.Errorf("failed to decode availability response: %w", err)
	}

	slots := make([]models.TimeSlot, len(availResp.Times))
	for i, t := range availResp.Times {
		slots[i] = models.TimeSlot{
			Time:        t.Time,
			CanBook:     t.CanBook,
			BookingForm: t.BookingForm,
		}
	}

	return slots, nil
}

// BookTimeSlot books the specified time slot via the API.
func (c *APIClient) BookTimeSlot(timeSlot models.TimeSlot, playingPartners []string, dryRun bool) (string, error) {
	if c.lastDate == "" {
		return "", fmt.Errorf("no date available: call GetCourseAvailability first")
	}

	path := fmt.Sprintf("/api/%s/time/%s/book", c.lastDate, timeSlot.Time)
	body, err := json.Marshal(bookRequest{
		NumSlots: len(playingPartners) + 1,
		DryRun:   dryRun,
	})
	if err != nil {
		return "", fmt.Errorf("failed to marshal book request: %w", err)
	}

	resp, err := c.doRequest(http.MethodPost, path, body, true)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", c.readError(resp)
	}

	var bookResp bookResponse
	if err := json.NewDecoder(resp.Body).Decode(&bookResp); err != nil {
		return "", fmt.Errorf("failed to decode book response: %w", err)
	}

	// Reset partner accumulation for new booking
	c.partners = nil
	c.lastBooking = bookResp.BookingID

	return bookResp.BookingID, nil
}

// AddPlayingPartner adds a playing partner to an existing booking.
// Partners are accumulated and sent as a growing list to ensure correct slot assignment.
func (c *APIClient) AddPlayingPartner(bookingID, partnerID string, slotNumber int, dryRun bool) error {
	// Reset accumulation if booking ID changed
	if bookingID != c.lastBooking {
		c.partners = nil
		c.lastBooking = bookingID
	}

	c.partners = append(c.partners, partnerID)

	body, err := json.Marshal(addPartnersRequest{
		Partners: c.partners,
		DryRun:   dryRun,
	})
	if err != nil {
		return fmt.Errorf("failed to marshal add partners request: %w", err)
	}

	path := fmt.Sprintf("/api/bookings/%s", bookingID)
	resp, err := c.doRequest(http.MethodPatch, path, body, true)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	// 200 = all success, 207 = partial success (some previously added partners may fail on re-add)
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusMultiStatus {
		return c.readError(resp)
	}

	var partnersResp addPartnersResponse
	if err := json.NewDecoder(resp.Body).Decode(&partnersResp); err != nil {
		return fmt.Errorf("failed to decode add partners response: %w", err)
	}

	// Only error if the newly added partner (the last one) failed
	for _, failed := range partnersResp.PartnersFailed {
		if failed == partnerID {
			return fmt.Errorf("failed to add partner %s to booking %s", partnerID, bookingID)
		}
	}

	return nil
}

// doRequest creates and executes an HTTP request to the API.
func (c *APIClient) doRequest(method, path string, body []byte, auth bool) (*http.Response, error) {
	url := c.apiURL + path

	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewReader(body)
	}

	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	if auth && c.accessToken != "" {
		req.Header.Set("Authorization", "Bearer "+c.accessToken)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("API request failed: %w", err)
	}

	return resp, nil
}

// readError reads an error response from the API.
func (c *APIClient) readError(resp *http.Response) error {
	var errResp errorResponse
	if err := json.NewDecoder(resp.Body).Decode(&errResp); err != nil {
		return fmt.Errorf("API error (status %d)", resp.StatusCode)
	}
	return fmt.Errorf("API error (status %d): %s", resp.StatusCode, errResp.Detail)
}

// convertDateFormat converts from DD-MM-YYYY to YYYY-MM-DD.
func convertDateFormat(dateStr string) (string, error) {
	t, err := time.Parse("02-01-2006", dateStr)
	if err != nil {
		return "", err
	}
	return t.Format("2006-01-02"), nil
}
