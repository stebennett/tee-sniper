package main

import (
	"errors"
	"fmt"
	"log/slog"
	"math/rand"
	"os"
	"time"

	"github.com/stebennett/tee-sniper/pkg/clients"
	"github.com/stebennett/tee-sniper/pkg/config"
	"github.com/stebennett/tee-sniper/pkg/logger"
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

	slog.Info("login completed", slog.Bool("success", ok))

	nextBookableDate := a.TimeNow().AddDate(0, 0, a.Config.DaysAhead)
	dateStr := nextBookableDate.Format("02-01-2006")

	slog.Info("searching for tee times",
		slog.String("time_start", a.Config.TimeStart),
		slog.String("time_end", a.Config.TimeEnd),
		slog.String("date", dateStr),
		slog.Int("max_retries", a.Config.Retries),
	)
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
			slog.Info("no tee times available, retrying",
				slog.String("time_start", a.Config.TimeStart),
				slog.String("time_end", a.Config.TimeEnd),
				slog.String("date", dateStr),
			)
			retryDelay := GetRandomRetryDelay(5, 15)
			slog.Debug("waiting before retry", slog.Duration("delay", retryDelay))
			a.SleepFunc(retryDelay)
			continue
		}

		slog.Info("found available tee times",
			slog.Int("count", len(availableTimes)),
			slog.String("time_start", a.Config.TimeStart),
			slog.String("time_end", a.Config.TimeEnd),
			slog.String("date", dateStr),
		)

		timeToBook, err := teetimes.PickRandomTime(availableTimes)
		if err != nil {
			slog.Warn("failed to pick random time", slog.String("error", err.Error()))
			continue
		}
		playingPartners := a.Config.GetPlayingPartnersList()

		slog.Info("attempting to book tee time",
			slog.String("time", timeToBook.Time),
			slog.String("date", dateStr),
			slog.Int("players", len(playingPartners)+1),
		)

		bookingID, err := a.BookingClient.BookTimeSlot(timeToBook, playingPartners, a.Config.DryRun)
		if err != nil {
			slog.Warn("failed to book time slot", slog.String("error", err.Error()))
			retryDelay := GetRandomRetryDelay(3, 8)
			slog.Debug("waiting before retry", slog.Duration("delay", retryDelay))
			a.SleepFunc(retryDelay)
			continue
		}

		if bookingID != "" {
			slog.Info("successfully booked tee time",
				slog.String("time", timeToBook.Time),
				slog.String("date", dateStr),
				slog.String("booking_id", bookingID),
			)

			for i, partnerID := range playingPartners {
				slotNumber := i + 2
				err := a.BookingClient.AddPlayingPartner(bookingID, partnerID, slotNumber, a.Config.DryRun)
				if err != nil {
					slog.Warn("failed to add playing partner",
						slog.String("partner_id", partnerID),
						slog.Int("slot", slotNumber),
						slog.String("error", err.Error()),
					)
				} else {
					slog.Info("added playing partner",
						slog.String("partner_id", partnerID),
						slog.Int("slot", slotNumber),
					)
				}
			}

			message := fmt.Sprintf("Successfully booked tee time: %s on %s for %d people", timeToBook.Time, dateStr, len(playingPartners)+1)
			err := a.TwilioClient.SendSms(a.Config.FromNumber, a.Config.ToNumber, message, a.Config.DryRun)
			if err != nil {
				slog.Warn("failed to send SMS", slog.String("error", err.Error()))
			}
			slog.Info("booking confirmation", slog.String("message", message))
			booked = true
			break
		} else {
			slog.Warn("booking incomplete, retrying",
				slog.String("time", timeToBook.Time),
				slog.String("date", dateStr),
			)
			retryDelay := GetRandomRetryDelay(4, 10)
			slog.Debug("waiting before retry", slog.Duration("delay", retryDelay))
			a.SleepFunc(retryDelay)
		}
	}

	if !booked {
		message := fmt.Sprintf("Failed to book tee time on %s", dateStr)
		err := a.TwilioClient.SendSms(a.Config.FromNumber, a.Config.ToNumber, message, a.Config.DryRun)
		if err != nil {
			slog.Warn("failed to send failure SMS", slog.String("error", err.Error()))
		}
		return fmt.Errorf("%w: %s", ErrNoBooking, message)
	}

	return nil
}

func main() {
	conf, err := config.GetConfig()
	if err != nil {
		if errors.Is(err, config.ErrHelp) {
			os.Exit(0)
		}
		// Initialize with default level for error output
		logger.Init("info")
		slog.Error("configuration error", slog.String("error", err.Error()))
		os.Exit(1)
	}

	logger.Init(conf.LogLevel)

	bookingClient, err := clients.NewBookingClient(conf.BaseUrl)
	if err != nil {
		slog.Error("failed to create booking client", slog.String("error", err.Error()))
		os.Exit(1)
	}

	twilioClient := clients.NewTwilioClient()

	app := NewApp(conf, bookingClient, twilioClient)
	if err := app.Run(); err != nil {
		slog.Error("application failed", slog.String("error", err.Error()))
		os.Exit(1)
	}
}
