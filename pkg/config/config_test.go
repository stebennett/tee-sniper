package config

import (
	"errors"
	"os"
	"testing"

	flags "github.com/jessevdk/go-flags"
	"github.com/stretchr/testify/assert"
)

func TestGetPlayingPartnersList(t *testing.T) {
	tests := []struct {
		name     string
		partners string
		expected []string
	}{
		{
			name:     "empty string returns empty slice",
			partners: "",
			expected: []string{},
		},
		{
			name:     "single partner returns slice with one element",
			partners: "partner1",
			expected: []string{"partner1"},
		},
		{
			name:     "multiple partners returns multiple elements",
			partners: "p1,p2,p3",
			expected: []string{"p1", "p2", "p3"},
		},
		{
			name:     "handles whitespace around values",
			partners: " p1 , p2 , p3 ",
			expected: []string{"p1", "p2", "p3"},
		},
		{
			name:     "handles mixed spacing",
			partners: "p1,  p2,p3  ",
			expected: []string{"p1", "p2", "p3"},
		},
		{
			name:     "handles tabs and spaces",
			partners: "	p1	,	p2	",
			expected: []string{"p1", "p2"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := Config{PlayingPartners: tt.partners}
			result := cfg.GetPlayingPartnersList()
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestIsErrHelpTrue(t *testing.T) {
	helpErr := &flags.Error{
		Type:    flags.ErrHelp,
		Message: "help requested",
	}

	result := isErrHelp(helpErr)
	assert.True(t, result, "isErrHelp should return true for help flag error")
}

func TestIsErrHelpFalse(t *testing.T) {
	tests := []struct {
		name string
		err  error
	}{
		{
			name: "standard error",
			err:  errors.New("some error"),
		},
		{
			name: "flags error with different type",
			err: &flags.Error{
				Type:    flags.ErrRequired,
				Message: "required flag missing",
			},
		},
		{
			name: "flags error unknown type",
			err: &flags.Error{
				Type:    flags.ErrUnknown,
				Message: "unknown error",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isErrHelp(tt.err)
			assert.False(t, result, "isErrHelp should return false for non-help errors")
		})
	}
}

func TestGetConfigHelpFlag(t *testing.T) {
	// Save original os.Args and restore after test
	originalArgs := os.Args
	defer func() { os.Args = originalArgs }()

	os.Args = []string{"cmd", "-h"}

	_, err := GetConfig()
	assert.ErrorIs(t, err, ErrHelp, "GetConfig should return ErrHelp when help flag is passed")
}

func TestGetConfigMissingRequired(t *testing.T) {
	// Save original os.Args and restore after test
	originalArgs := os.Args
	defer func() { os.Args = originalArgs }()

	os.Args = []string{"cmd"}

	_, err := GetConfig()
	assert.Error(t, err, "GetConfig should return error when required flags are missing")
	assert.NotErrorIs(t, err, ErrHelp, "Error should not be ErrHelp")
}

func TestGetConfigValidArgs(t *testing.T) {
	// Save original os.Args and restore after test
	originalArgs := os.Args
	defer func() { os.Args = originalArgs }()

	os.Args = []string{
		"cmd",
		"-d", "7",
		"-t", "08:00",
		"-e", "12:00",
		"-r", "3",
		"-u", "testuser",
		"-p", "1234",
		"-b", "https://example.com",
		"-f", "+1234567890",
		"-n", "+0987654321",
		"-s", "partner1,partner2",
	}

	cfg, err := GetConfig()
	assert.NoError(t, err, "GetConfig should not return error with valid args")
	assert.Equal(t, 7, cfg.DaysAhead)
	assert.Equal(t, "08:00", cfg.TimeStart)
	assert.Equal(t, "12:00", cfg.TimeEnd)
	assert.Equal(t, 3, cfg.Retries)
	assert.Equal(t, "testuser", cfg.Username)
	assert.Equal(t, "1234", cfg.Pin)
	assert.Equal(t, "https://example.com", cfg.BaseUrl)
	assert.Equal(t, "+1234567890", cfg.FromNumber)
	assert.Equal(t, "+0987654321", cfg.ToNumber)
	assert.Equal(t, "partner1,partner2", cfg.PlayingPartners)
}

func TestGetConfigDryRunFlag(t *testing.T) {
	// Save original os.Args and restore after test
	originalArgs := os.Args
	defer func() { os.Args = originalArgs }()

	os.Args = []string{
		"cmd",
		"-d", "7",
		"-t", "08:00",
		"-e", "12:00",
		"-r", "3",
		"-u", "testuser",
		"-p", "1234",
		"-b", "https://example.com",
		"-f", "+1234567890",
		"-n", "+0987654321",
		"-x", // dry run flag
	}

	cfg, err := GetConfig()
	assert.NoError(t, err, "GetConfig should not return error with valid args")
	assert.True(t, cfg.DryRun, "DryRun should be true when -x flag is passed")
}

func TestGetConfigDefaultRetries(t *testing.T) {
	// Save original os.Args and restore after test
	originalArgs := os.Args
	defer func() { os.Args = originalArgs }()

	// Note: go-flags requires the default tag, but also required:"true"
	// This means retries is required despite having a default
	// Testing that the value is correctly parsed
	os.Args = []string{
		"cmd",
		"-d", "7",
		"-t", "08:00",
		"-e", "12:00",
		"-r", "5", // using default value
		"-u", "testuser",
		"-p", "1234",
		"-b", "https://example.com",
		"-f", "+1234567890",
		"-n", "+0987654321",
	}

	cfg, err := GetConfig()
	assert.NoError(t, err)
	assert.Equal(t, 5, cfg.Retries, "Retries should be 5")
}

func TestGetConfigOptionalPartners(t *testing.T) {
	// Save original os.Args and restore after test
	originalArgs := os.Args
	defer func() { os.Args = originalArgs }()

	os.Args = []string{
		"cmd",
		"-d", "7",
		"-t", "08:00",
		"-e", "12:00",
		"-r", "3",
		"-u", "testuser",
		"-p", "1234",
		"-b", "https://example.com",
		"-f", "+1234567890",
		"-n", "+0987654321",
		// No -s flag - partners is optional
	}

	cfg, err := GetConfig()
	assert.NoError(t, err, "GetConfig should succeed without optional partners flag")
	assert.Equal(t, "", cfg.PlayingPartners, "PlayingPartners should be empty string when not provided")
	assert.Equal(t, []string{}, cfg.GetPlayingPartnersList(), "GetPlayingPartnersList should return empty slice")
}
