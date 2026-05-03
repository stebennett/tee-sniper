package crypto

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestEncryptDecryptRoundTrip(t *testing.T) {
	tests := []struct {
		name     string
		username string
		pin      string
		secret   string
	}{
		{
			name:     "basic credentials",
			username: "testuser",
			pin:      "1234",
			secret:   "my-shared-secret",
		},
		{
			name:     "username with special characters",
			username: "user@example.com",
			pin:      "p@ss!w0rd",
			secret:   "another-secret",
		},
		{
			name:     "empty pin",
			username: "user",
			pin:      "",
			secret:   "secret",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			encrypted, err := EncryptCredentials(tt.username, tt.pin, tt.secret)
			require.NoError(t, err)
			assert.NotEmpty(t, encrypted)

			username, pin, err := DecryptCredentials(encrypted, tt.secret)
			require.NoError(t, err)
			assert.Equal(t, tt.username, username)
			assert.Equal(t, tt.pin, pin)
		})
	}
}

func TestEncryptProducesDifferentCiphertexts(t *testing.T) {
	enc1, err := EncryptCredentials("user", "pin", "secret")
	require.NoError(t, err)

	enc2, err := EncryptCredentials("user", "pin", "secret")
	require.NoError(t, err)

	assert.NotEqual(t, enc1, enc2, "different nonces should produce different ciphertexts")
}

func TestDecryptWithWrongSecret(t *testing.T) {
	encrypted, err := EncryptCredentials("user", "pin", "correct-secret")
	require.NoError(t, err)

	_, _, err = DecryptCredentials(encrypted, "wrong-secret")
	assert.Error(t, err)
}

func TestDecryptInvalidBase64(t *testing.T) {
	_, _, err := DecryptCredentials("not-valid-base64!!!", "secret")
	assert.Error(t, err)
}

func TestDecryptTruncatedData(t *testing.T) {
	_, _, err := DecryptCredentials("AQID", "secret") // 3 bytes, too short for nonce
	assert.Error(t, err)
}
