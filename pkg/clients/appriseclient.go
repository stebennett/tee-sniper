package clients

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"
)

// HTTPClient interface for making HTTP requests (allows mocking in tests)
type HTTPClient interface {
	Do(req *http.Request) (*http.Response, error)
}

// AppriseClient sends notifications via the Apprise API
type AppriseClient struct {
	httpClient HTTPClient
	urls       string
}

// appriseRequest represents the JSON payload for Apprise API
type appriseRequest struct {
	URLs string `json:"urls"`
	Body string `json:"body"`
}

// NewAppriseClient creates an AppriseClient with the default HTTP client
func NewAppriseClient(urls string) *AppriseClient {
	return &AppriseClient{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		urls: urls,
	}
}

// NewAppriseClientWithHTTPClient creates an AppriseClient with a custom HTTP client (for testing)
func NewAppriseClientWithHTTPClient(urls string, httpClient HTTPClient) *AppriseClient {
	return &AppriseClient{
		httpClient: httpClient,
		urls:       urls,
	}
}

// SendNotification sends a notification via Apprise
func (a *AppriseClient) SendNotification(message string, dryRun bool) error {
	if dryRun {
		slog.Info("dry run: notification simulated",
			slog.String("message", message),
			slog.Bool("dry_run", true),
		)
		return nil
	}

	payload := appriseRequest{
		URLs: a.urls,
		Body: message,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal apprise request: %w", err)
	}

	req, err := http.NewRequest("POST", a.urls, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create apprise request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := a.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send apprise notification: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("apprise notification failed with status %d: %s", resp.StatusCode, string(body))
	}

	slog.Debug("apprise notification sent successfully",
		slog.Int("status_code", resp.StatusCode),
	)

	return nil
}
