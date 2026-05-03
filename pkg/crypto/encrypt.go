package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"strings"
)

// EncryptCredentials encrypts username and pin using AES-256-GCM.
// The output format matches the Python EncryptionService: base64(nonce + ciphertext).
func EncryptCredentials(username, pin, sharedSecret string) (string, error) {
	key := sha256.Sum256([]byte(sharedSecret))

	block, err := aes.NewCipher(key[:])
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %w", err)
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := rand.Read(nonce); err != nil {
		return "", fmt.Errorf("failed to generate nonce: %w", err)
	}

	plaintext := []byte(fmt.Sprintf("%s:%s", username, pin))
	ciphertext := gcm.Seal(nil, nonce, plaintext, nil)

	// Prepend nonce to ciphertext, then base64 encode
	combined := append(nonce, ciphertext...)
	return base64.StdEncoding.EncodeToString(combined), nil
}

// DecryptCredentials decrypts a base64-encoded AES-256-GCM encrypted string.
// Returns the username and pin.
func DecryptCredentials(encrypted, sharedSecret string) (string, string, error) {
	data, err := base64.StdEncoding.DecodeString(encrypted)
	if err != nil {
		return "", "", fmt.Errorf("failed to decode base64: %w", err)
	}

	key := sha256.Sum256([]byte(sharedSecret))

	block, err := aes.NewCipher(key[:])
	if err != nil {
		return "", "", fmt.Errorf("failed to create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", "", fmt.Errorf("failed to create GCM: %w", err)
	}

	nonceSize := gcm.NonceSize()
	if len(data) < nonceSize {
		return "", "", fmt.Errorf("encrypted data too short")
	}

	nonce, ciphertext := data[:nonceSize], data[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return "", "", fmt.Errorf("failed to decrypt: %w", err)
	}

	// Split on first ":" only to support usernames containing ":"
	parts := strings.SplitN(string(plaintext), ":", 2)
	if len(parts) != 2 {
		return "", "", fmt.Errorf("invalid credential format")
	}

	return parts[0], parts[1], nil
}
