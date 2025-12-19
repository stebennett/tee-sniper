package main

import (
	"errors"
	"fmt"
	"log"
	"math/rand"
	"time"

	"github.com/stebennett/tee-sniper/pkg/clients"
	"github.com/stebennett/tee-sniper/pkg/config"
	"github.com/stebennett/tee-sniper/pkg/teetimes"
)

var (
	ErrNoBooking = errors.New("failed to book tee time")
)

// GetRandomRetryDelay returns a random delay between min and max seconds with jitter
func GetRandomRetryDelay(minSeconds, maxSeconds int) time.Duration {
	// Base delay between min and max
	baseDelay := minSeconds + rand.Intn(maxSeconds-minSeconds+1)

	// Add jitter of +/- 20% (in milliseconds)
	jitterRange := float64(baseDelay) * 0.2
	jitterMs := (rand.Float64() - 0.5) * jitterRange * 1000

	totalMs := float64(baseDelay)*1000 + jitterMs
	return time.Duration(totalMs) * time.Millisecond
}

// App encapsulates the application dependencies for testability
type App struct {
	Config        config.Config
	BookingClient clients.BookingService
	TwilioClient  clients.SMSService
	TimeNow       func() time.Time
	SleepFunc     func(time.Duration)
}

// NewApp creates a new App with real dependencies
func NewApp(conf config.Config, bookingClient clients.BookingService, twilioClient clients.SMSService) *App {
	return &App{
		Config:        conf,
		BookingClient: bookingClient,
		TwilioClient:  twilioClient,
		TimeNow:       time.Now,
		SleepFunc:     time.Sleep,
	}
}

// Run executes the main application logic
func (a *App) Run() error {
	ok, err := a.BookingClient.Login(a.Config.Username, a.Config.Pin)
	if err != nil {
		return fmt.Errorf("login failed: %w", err)
	}

	log.Printf("login status: %t", ok)

	nextBookableDate := a.TimeNow().AddDate(0, 0, a.Config.DaysAhead)
	dateStr := nextBookableDate.Format("02-01-2006")

	log.Printf("Finding tee times between %s and %s on date %s. retries %d", a.Config.TimeStart, a.Config.TimeEnd, dateStr, a.Config.Retries)
	booked := false

	for i := 0; i < a.Config.Retries; i++ {
		availableTimes, err := a.BookingClient.GetCourseAvailability(dateStr)
		if err != nil {
			return fmt.Errorf("failed to get availability: %w", err)
		}

		availableTimes = teetimes.FilterByBookable(availableTimes)
		availableTimes = teetimes.SortTimesAscending(availableTimes)
		availableTimes = teetimes.FilterBetweenTimes(availableTimes, a.Config.TimeStart, a.Config.TimeEnd)

		if len(availableTimes) == 0 {
			log.Printf("No tee times available between %s and %s on %s. Retrying.", a.Config.TimeStart, a.Config.TimeEnd, dateStr)
			retryDelay := GetRandomRetryDelay(5, 15)
			log.Printf("Waiting %v before retry", retryDelay)
			a.SleepFunc(retryDelay)
			continue
		}

		log.Printf("Found %d available tee times between %s and %s on %s", len(availableTimes), a.Config.TimeStart, a.Config.TimeEnd, dateStr)

		timeToBook, err := teetimes.PickRandomTime(availableTimes)
		if err != nil {
			log.Printf("Failed to pick random time: %s", err.Error())
			continue
		}
		playingPartners := a.Config.GetPlayingPartnersList()

		log.Printf("Attempting to book tee time: %s on %s for %d people", timeToBook.Time, dateStr, len(playingPartners)+1)

		bookingID, err := a.BookingClient.BookTimeSlot(timeToBook, playingPartners, a.Config.DryRun)
		if err != nil {
			log.Printf("Failed to book time slot: %s", err.Error())
			retryDelay := GetRandomRetryDelay(3, 8)
			log.Printf("Waiting %v before retry", retryDelay)
			a.SleepFunc(retryDelay)
			continue
		}

		if bookingID != "" {
			log.Printf("Successfully booked tee time: %s on %s (booking ID: %s)", timeToBook.Time, dateStr, bookingID)

			for i, partnerID := range playingPartners {
				slotNumber := i + 2
				err := a.BookingClient.AddPlayingPartner(bookingID, partnerID, slotNumber, a.Config.DryRun)
				if err != nil {
					log.Printf("Failed to add playing partner %s to slot %d: %s", partnerID, slotNumber, err.Error())
				} else {
					log.Printf("Added playing partner %s to slot %d", partnerID, slotNumber)
				}
			}

			message := fmt.Sprintf("Successfully booked tee time: %s on %s for %d people", timeToBook.Time, dateStr, len(playingPartners)+1)
			err := a.TwilioClient.SendSms(a.Config.FromNumber, a.Config.ToNumber, message, a.Config.DryRun)
			if err != nil {
				log.Printf("Failed to send SMS: %s", err.Error())
			}
			log.Println(message)
			booked = true
			break
		} else {
			log.Printf("Failed to complete booking: %s on %s. Retrying.", timeToBook.Time, dateStr)
			retryDelay := GetRandomRetryDelay(4, 10)
			log.Printf("Waiting %v before retry", retryDelay)
			a.SleepFunc(retryDelay)
		}
	}

	if !booked {
		message := fmt.Sprintf("Failed to book tee time on %s", dateStr)
		err := a.TwilioClient.SendSms(a.Config.FromNumber, a.Config.ToNumber, message, a.Config.DryRun)
		if err != nil {
			log.Printf("Failed to send SMS: %s", err.Error())
		}
		return fmt.Errorf("%w: %s", ErrNoBooking, message)
	}

	return nil
}

func main() {
	conf, err := config.GetConfig()
	if err != nil {
		log.Fatal(err)
	}

	bookingClient, err := clients.NewBookingClient(conf.BaseUrl)
	if err != nil {
		log.Fatal(err)
	}

	twilioClient := clients.NewTwilioClient()

	app := NewApp(conf, bookingClient, twilioClient)
	if err := app.Run(); err != nil {
		log.Fatal(err)
	}
}
