package mocks

import (
	"time"

	"github.com/golang/mock/gomock"
)

type MockClock struct {
	ctrl     *gomock.Controller
	recorder *MockClockRecorder
	t        time.Time
}

type MockClockRecorder struct {
	mock *MockClock
}

func NewMockClock(ctrl *gomock.Controller, t time.Time) *MockClock {
	mock := &MockClock{ctrl: ctrl}
	mock.t = t
	mock.recorder = &MockClockRecorder{mock}
	return mock
}

func (c *MockClock) Now() time.Time {
	return c.t
}
