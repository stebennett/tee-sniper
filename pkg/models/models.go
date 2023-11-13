package models

type TimeSlot struct {
	Time        string
	CanBook     bool
	BookingForm map[string]string
}
