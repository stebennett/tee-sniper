package config

import (
	"errors"
	"strings"

	flags "github.com/jessevdk/go-flags"
)

var (
	ErrHelp = errors.New("help")
)

type Config struct {
	DaysAhead int    `short:"d" long:"days" env:"TS_DAYS_AHEAD" required:"true" description:"The number of days ahead to look for a tee-slot"`
	TimeStart string `short:"t" long:"timestart" env:"TS_TIME_START" required:"true" description:"The time after which a tee-time will be selected"`
	TimeEnd   string `short:"e" long:"timeend" env:"TS_TIME_END" required:"true" description:"The time before which a tee-time will be selected"`
	Retries   int    `short:"r" long:"retries" env:"TS_RETRIES" default:"5" description:"The number of times to retry booking"`
	DryRun    bool   `short:"x" long:"dryrun" env:"TS_DRY_RUN" description:"Run everything, but don't do the booking and assume it succeeds"`
	LogLevel  string `short:"l" long:"loglevel" env:"TS_LOG_LEVEL" default:"info" description:"Log level (debug, info, warn, error)"`

	Username string `short:"u" long:"username" env:"TS_USERNAME" required:"true" description:"The username to use for booking"`
	Pin      string `short:"p" long:"pin" env:"TS_PIN" required:"true" description:"The pin associated with the username for booking"`
	BaseUrl  string `short:"b" long:"baseurl" env:"TS_BASEURL" required:"true" description:"The host for the booking website"`

	FromNumber      string `short:"f" long:"fromnumber" env:"TS_FROM_NUMBER" required:"true" description:"The number to send the confirmation SMS from"`
	ToNumber        string `short:"n" long:"tonumber" env:"TS_TO_NUMBER" required:"true" description:"The number to send the confirmation SMS to"`
	PlayingPartners string `short:"s" long:"partners" env:"TS_PARTNERS" description:"Comma-separated list of playing partner IDs"`
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

func (c Config) GetPlayingPartnersList() []string {
	if c.PlayingPartners == "" {
		return []string{}
	}
	parts := strings.Split(c.PlayingPartners, ",")
	for i, part := range parts {
		parts[i] = strings.TrimSpace(part)
	}
	return parts
}

func isErrHelp(err error) bool {
	flagsErr, ok := err.(*flags.Error)
	if ok {
		return flagsErr.Type == flags.ErrHelp
	}
	return false
}
