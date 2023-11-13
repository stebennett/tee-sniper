package teetimes

import (
	"testing"

	"github.com/stebennett/tee-sniper/pkg/models"

	"github.com/stretchr/testify/assert"
)

func TestSortTimesAscending(t *testing.T) {

	timeslots := []models.TimeSlot{
		{
			Time: "15:00",
		},
		{
			Time: "08:30",
		},
		{
			Time: "15:05",
		},
		{
			Time: "12:05",
		},
	}

	sorted := SortTimesAscending(timeslots)

	assert.Equal(t, "08:30", sorted[0].Time)
	assert.Equal(t, "12:05", sorted[1].Time)
	assert.Equal(t, "15:00", sorted[2].Time)
	assert.Equal(t, "15:05", sorted[3].Time)
}

func TestFilterByBookable(t *testing.T) {

	timeslots := []models.TimeSlot{
		{
			Time:    "15:00",
			CanBook: false,
		},
		{
			Time:    "08:30",
			CanBook: true,
		},
		{
			Time:    "15:05",
			CanBook: false,
		},
		{
			Time:    "12:05",
			CanBook: true,
		},
	}

	sorted := FilterByBookable(timeslots)

	assert.Equal(t, "08:30", sorted[0].Time)
	assert.Equal(t, "12:05", sorted[1].Time)
}

func TestFilterTimesBetweenExcludeEnd(t *testing.T) {

	timeslots := []models.TimeSlot{
		{
			Time: "08:30",
		},
		{
			Time: "12:05",
		},
		{
			Time: "15:00",
		},
		{
			Time: "15:10",
		},
	}

	sorted := FilterBetweenTimes(timeslots, "09:00", "15:10")

	assert.Equal(t, "12:05", sorted[0].Time)
	assert.Equal(t, "15:00", sorted[1].Time)
}

func TestFilterTimesBetweenExcludeStart(t *testing.T) {

	timeslots := []models.TimeSlot{
		{
			Time: "08:30",
		},
		{
			Time: "12:05",
		},
		{
			Time: "15:00",
		},
		{
			Time: "15:10",
		},
	}

	sorted := FilterBetweenTimes(timeslots, "08:30", "15:15")

	assert.Equal(t, "12:05", sorted[0].Time)
	assert.Equal(t, "15:00", sorted[1].Time)
}
