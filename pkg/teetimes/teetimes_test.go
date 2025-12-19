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

// PickRandomTime tests

func TestPickRandomTimeEmptySlice(t *testing.T) {
	result := PickRandomTime([]models.TimeSlot{})
	assert.Equal(t, models.TimeSlot{}, result)
}

func TestPickRandomTimeSingleItem(t *testing.T) {
	slot := models.TimeSlot{Time: "10:00", CanBook: true}
	result := PickRandomTime([]models.TimeSlot{slot})
	assert.Equal(t, slot, result)
}

func TestPickRandomTimeMultipleItems(t *testing.T) {
	slots := []models.TimeSlot{
		{Time: "09:00", CanBook: true},
		{Time: "10:00", CanBook: true},
		{Time: "11:00", CanBook: true},
	}

	result := PickRandomTime(slots)

	// Verify the result is one of the input slots
	found := false
	for _, s := range slots {
		if s.Time == result.Time {
			found = true
			break
		}
	}
	assert.True(t, found, "PickRandomTime should return an item from the input slice")
}

// SortTimesAscending edge case tests

func TestSortTimesAscendingEmpty(t *testing.T) {
	result := SortTimesAscending([]models.TimeSlot{})
	assert.Empty(t, result)
}

func TestSortTimesAscendingSingleItem(t *testing.T) {
	slot := models.TimeSlot{Time: "10:00"}
	result := SortTimesAscending([]models.TimeSlot{slot})
	assert.Len(t, result, 1)
	assert.Equal(t, "10:00", result[0].Time)
}

// FilterByBookable edge case tests

func TestFilterByBookableEmpty(t *testing.T) {
	result := FilterByBookable([]models.TimeSlot{})
	assert.Empty(t, result)
}

func TestFilterByBookableNoneBookable(t *testing.T) {
	slots := []models.TimeSlot{
		{Time: "09:00", CanBook: false},
		{Time: "10:00", CanBook: false},
	}
	result := FilterByBookable(slots)
	assert.Empty(t, result)
}

func TestFilterByBookableAllBookable(t *testing.T) {
	slots := []models.TimeSlot{
		{Time: "09:00", CanBook: true},
		{Time: "10:00", CanBook: true},
	}
	result := FilterByBookable(slots)
	assert.Len(t, result, 2)
	assert.Equal(t, "09:00", result[0].Time)
	assert.Equal(t, "10:00", result[1].Time)
}

// FilterBetweenTimes edge case tests

func TestFilterBetweenTimesEmpty(t *testing.T) {
	result := FilterBetweenTimes([]models.TimeSlot{}, "09:00", "17:00")
	assert.Empty(t, result)
}

func TestFilterBetweenTimesNoMatches(t *testing.T) {
	slots := []models.TimeSlot{
		{Time: "08:00"},
		{Time: "18:00"},
	}
	result := FilterBetweenTimes(slots, "09:00", "17:00")
	assert.Empty(t, result)
}
