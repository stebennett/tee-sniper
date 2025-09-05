package main

import (
	"fmt"
	"log"
	"math/rand"
	"time"

	"github.com/stebennett/tee-sniper/pkg/clients"
	"github.com/stebennett/tee-sniper/pkg/config"
	"github.com/stebennett/tee-sniper/pkg/teetimes"
)

// getRandomRetryDelay returns a random delay between min and max seconds with jitter
func getRandomRetryDelay(minSeconds, maxSeconds int) time.Duration {
	// Base delay between min and max
	baseDelay := minSeconds + rand.Intn(maxSeconds-minSeconds+1)
	
	// Add jitter of +/- 20% (in milliseconds)
	jitterRange := float64(baseDelay) * 0.2
	jitterMs := (rand.Float64() - 0.5) * jitterRange * 1000
	
	totalMs := float64(baseDelay)*1000 + jitterMs
	return time.Duration(totalMs) * time.Millisecond
}

func main() {
	// Initialize random seed
	rand.Seed(time.Now().UnixNano())
	conf, err := config.GetConfig()
	if err != nil {
		log.Fatal(err)
	}

	wc, err := clients.NewBookingClient(conf.BaseUrl)
	if err != nil {
		log.Fatal(err)
	}

	twilioClient := clients.NewTwilioClient()

	ok, err := wc.Login(conf.Username, conf.Pin)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("login status: %t", ok)

	nextBookableDate := time.Now().AddDate(0, 0, conf.DaysAhead)
	dateStr := nextBookableDate.Format("02-01-2006")

	log.Printf("Finding tee times between %s and %s on date %s. retries %d", conf.TimeStart, conf.TimeEnd, dateStr, conf.Retries)
	booked := false

	for i := 0; i < conf.Retries; i++ {
		availableTimes, err := wc.GetCourseAvailability(dateStr)
		if err != nil {
			log.Fatal(err)
		}

		availableTimes = teetimes.FilterByBookable(availableTimes)
		availableTimes = teetimes.SortTimesAscending(availableTimes)
		availableTimes = teetimes.FilterBetweenTimes(availableTimes, conf.TimeStart, conf.TimeEnd)

		if len(availableTimes) == 0 {
			log.Printf("No tee times available between %s and %s on %s. Retrying.", conf.TimeStart, conf.TimeEnd, dateStr)
			// Random delay between 5-15 seconds with jitter
			retryDelay := getRandomRetryDelay(5, 15)
			log.Printf("Waiting %v before retry", retryDelay)
			time.Sleep(retryDelay)
			continue
		}

		log.Printf("Found %d available tee times between %s and %s on %s", len(availableTimes), conf.TimeStart, conf.TimeEnd, dateStr)

		timeToBook := teetimes.PickRandomTime(availableTimes)
		playingPartners := conf.GetPlayingPartnersList()

		log.Printf("Attempting to book tee time: %s on %s for %d people", timeToBook.Time, dateStr, len(playingPartners)+1)

		bookingID, err := wc.BookTimeSlot(timeToBook, playingPartners, conf.DryRun)
		if err != nil {
			log.Printf("Failed to book time slot: %s", err.Error())
			// Random delay between 3-8 seconds after failed booking
			retryDelay := getRandomRetryDelay(3, 8)
			log.Printf("Waiting %v before retry", retryDelay)
			time.Sleep(retryDelay)
			continue
		}

		if bookingID != "" {
			log.Printf("Successfully booked tee time: %s on %s (booking ID: %s)", timeToBook.Time, dateStr, bookingID)

			// Add playing partners to slots 2, 3, etc. (slot 1 is for the main player)
			for i, partnerID := range playingPartners {
				slotNumber := i + 2 // slots start at 2 for partners (1 is main player)
				err := wc.AddPlayingPartner(bookingID, partnerID, slotNumber, conf.DryRun)
				if err != nil {
					log.Printf("Failed to add playing partner %s to slot %d: %s", partnerID, slotNumber, err.Error())
				} else {
					log.Printf("Added playing partner %s to slot %d", partnerID, slotNumber)
				}
			}

			message := fmt.Sprintf("Successfully booked tee time: %s on %s for %d people", timeToBook.Time, dateStr, len(playingPartners)+1)
			_, err := twilioClient.SendSms(conf.FromNumber, conf.ToNumber, message, conf.DryRun)
			if err != nil {
				log.Printf("Failed to send SMS: %s", err.Error())
			}
			log.Println(message)
			booked = true
			break
		} else {
			log.Printf("Failed to complete booking: %s on %s. Retrying.", timeToBook.Time, dateStr)
			// Random delay between 4-10 seconds after incomplete booking
			retryDelay := getRandomRetryDelay(4, 10)
			log.Printf("Waiting %v before retry", retryDelay)
			time.Sleep(retryDelay)
		}
	}

	if !booked {
		message := fmt.Sprintf("Failed to book tee time on %s", dateStr)
		_, err := twilioClient.SendSms(conf.FromNumber, conf.ToNumber, message, conf.DryRun)
		if err != nil {
			log.Printf("Failed to send SMS: %s", err.Error())
		}
		log.Fatal(message)
	}
}
