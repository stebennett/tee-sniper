package teetimes

import (
	"sort"

	"github.com/stebennett/tee-sniper/pkg/models"
)

func SortTimesAscending(slots []models.TimeSlot) []models.TimeSlot {
	sort.Slice(slots, func(i, j int) bool {
		return slots[i].Time < slots[j].Time
	})

	return slots
}

func FilterByBookable(slots []models.TimeSlot) (results []models.TimeSlot) {
	for _, ts := range slots {
		if ts.CanBook {
			results = append(results, ts)
		}
	}
	return
}

func FilterBetweenTimes(slots []models.TimeSlot, startTime string, endTime string) (results []models.TimeSlot) {
	for _, ts := range slots {
		if ts.Time > startTime && ts.Time < endTime {
			results = append(results, ts)
		}
	}
	return
}
