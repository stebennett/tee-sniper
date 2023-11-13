package config

import (
	"errors"

	flags "github.com/jessevdk/go-flags"
)

var (
	ErrHelp = errors.New("help")
)

type Config struct {
	DaysAhead int    `short:"d" long:"days" required:"true" description:"The number of days ahead to look for a tee-slot"`
	TimeStart string `short:"t" long:"timestart" required:"true" description:"The time after which a tee-time will be selected"`
	TimeEnd   string `short:"e" long:"timeend" required:"true" description:"The time before which a tee-time will be selected"`

	Username string `short:"u" long:"username" required:"true" description:"The username to use for booking"`
	Pin      string `short:"p" long:"pin" required:"true" description:"The pin associated with the username for booking"`
	BaseUrl  string `short:"b" long:"baseurl" required:"true" description:"The host for the booking website"`
}

func GetConfig() (Config, error) {
	var c Config
	parser := flags.NewParser(&c, flags.Default)

	_, err := parser.Parse()
	if err != nil {
		if isErrHelp(err) {
			return c, ErrHelp
		}
		return c, err
	}

	return c, nil
}

func isErrHelp(err error) bool {
	flagsErr, ok := err.(*flags.Error)
	if ok {
		return flagsErr.Type == flags.ErrHelp
	}
	return false
}
