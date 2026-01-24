package clients

//go:generate mockgen -source=interfaces.go -destination=mocks/mock_clients.go -package=mocks

import "github.com/stebennett/tee-sniper/pkg/models"

// Compile-time verification that concrete types implement interfaces
var _ BookingService = (*BookingClient)(nil)
var _ NotificationService = (*AppriseClient)(nil)

// BookingService defines the interface for booking operations.
// This interface is implemented by BookingClient and can be mocked for testing.
type BookingService interface {
	// Login authenticates with the booking site.
	// Returns true if login was successful, false otherwise.
	Login(username, password string) (bool, error)

	// GetCourseAvailability retrieves available tee times for a given date.
	// The dateStr should be in the format expected by the booking site.
	GetCourseAvailability(dateStr string) ([]models.TimeSlot, error)

	// BookTimeSlot books the specified time slot.
	// Returns the booking ID on success.
	BookTimeSlot(timeSlot models.TimeSlot, playingPartners []string, dryRun bool) (string, error)

	// AddPlayingPartner adds a playing partner to an existing booking.
	AddPlayingPartner(bookingID, partnerID string, slotNumber int, dryRun bool) error
}

// NotificationService defines the interface for sending notifications.
// This interface is implemented by AppriseClient and can be mocked for testing.
type NotificationService interface {
	// SendNotification sends a notification message.
	// In dry run mode, the message is logged but not actually sent.
	SendNotification(message string, dryRun bool) error
}
