package main

import (
	"log"
	"time"

	"github.com/stebennett/tee-sniper/pkg/client"
	"github.com/stebennett/tee-sniper/pkg/config"
	"github.com/stebennett/tee-sniper/pkg/teetimes"
)

func main() {
	conf, err := config.GetConfig()
	if err != nil {
		log.Fatal(err)
	}

	wc, err := client.NewClient(conf.BaseUrl)
	if err != nil {
		log.Fatal(err)
	}

	ok, err := wc.Login(conf.Username, conf.Pin)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("login status: %t", ok)

	nextBookableDate := time.Now().AddDate(0, 0, conf.DaysAhead)
	dateStr := nextBookableDate.Format("02-01-2006")

	log.Printf("finding tee times between %s and %s on date %s. retries %d", conf.TimeStart, conf.TimeEnd, dateStr, conf.Retries)

	for i := 0; i < conf.Retries; i++ {
		availableTimes, err := wc.GetCourseAvailability(dateStr)
		if err != nil {
			log.Fatal(err)
		}

		availableTimes = teetimes.FilterByBookable(availableTimes)
		availableTimes = teetimes.SortTimesAscending(availableTimes)
		availableTimes = teetimes.FilterBetweenTimes(availableTimes, conf.TimeStart, conf.TimeEnd)

		if len(availableTimes) == 0 {
			log.Printf("No tee times available between %s and %s on %s", conf.TimeStart, conf.TimeEnd, dateStr)
			time.Sleep(10 * time.Second)
			continue
		}

		ok, err = wc.BookTimeSlot(availableTimes[0], conf.DryRun)
		if err != nil {
			log.Fatal(err)
		}

		if ok {
			log.Printf("Successfully booked: %s on %s", availableTimes[0].Time, dateStr)
			break
		} else {
			log.Printf("Failed to complete booking: %s on %s", availableTimes[0].Time, dateStr)
		}
	}
}
