package logger

import (
	"log/slog"
	"os"
	"strings"
)

// Init initializes the global logger with JSON output for Loki compatibility.
// Should be called once at application startup.
func Init(level string) {
	slogLevel := parseLogLevel(level)

	opts := &slog.HandlerOptions{
		Level: slogLevel,
	}

	handler := slog.NewJSONHandler(os.Stdout, opts)

	// Add default application attributes
	logger := slog.New(handler).With(
		slog.String("app", "tee-sniper"),
	)

	slog.SetDefault(logger)
}

func parseLogLevel(levelStr string) slog.Level {
	switch strings.ToLower(levelStr) {
	case "debug":
		return slog.LevelDebug
	case "warn", "warning":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
