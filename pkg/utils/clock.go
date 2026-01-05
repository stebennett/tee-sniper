package utils

import (
	"time"
	_ "time/tzdata"
)

type Clock interface {
	Now() time.Time
}

type RealClock struct {
	loc *time.Location
}

func NewRealClock(tz string) (*RealClock, error) {
	loc, err := time.LoadLocation(tz)
	if err != nil {
		return nil, err
	}
	return &RealClock{loc: loc}, nil
}

func (c *RealClock) Now() time.Time {
	return time.Now().In(c.loc)
}
