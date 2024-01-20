package main

import (
	"fmt"
	"log"
	"time"

	"github.com/stebennett/tee-sniper/pkg/clients"
	"github.com/stebennett/tee-sniper/pkg/config"
	"github.com/stebennett/tee-sniper/pkg/teetimes"
)

func main() {
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
			time.Sleep(10 * time.Second)
			continue
		}

		timeToBook := teetimes.PickRandomTime(availableTimes)

		ok, err = wc.BookTimeSlot(timeToBook, conf.DryRun)
		if err != nil {
			log.Fatal(err)
		}

		if ok {
			message := fmt.Sprintf("Successfully booked tee time: %s on %s", timeToBook.Time, dateStr)
			_, err := twilioClient.SendSms(conf.FromNumber, conf.ToNumber, message)
			if err != nil {
				log.Printf("Failed to send SMS: %s", err.Error())
			}
			log.Println(message)
			booked = true
			break
		} else {
			log.Printf("Failed to complete booking: %s on %s. Retrying.", timeToBook.Time, dateStr)
		}
	}

	if !booked {
		message := fmt.Sprintf("Failed to book tee time on %s", dateStr)
		_, err := twilioClient.SendSms(conf.FromNumber, conf.ToNumber, message)
		if err != nil {
			log.Printf("Failed to send SMS: %s", err.Error())
		}
		log.Fatal(message)
	}
}
