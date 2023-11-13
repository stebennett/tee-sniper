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

	log.Printf("finding tee-times for date: %s", dateStr)

	availableTimes, err := wc.GetCourseAvailability(dateStr)
	if err != nil {
		log.Fatal(err)
	}

	availableTimes = teetimes.SortTimesAscending(availableTimes)
	//availableTimes = teetimes.FilterBookable(availableTimes)
	//availableTimes = teetimes.FilterBetweenTimes(conf.StartTime, conf.EndTime)

	log.Printf("%v", availableTimes)
}
