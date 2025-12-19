package clients

import (
	"log"

	twilio "github.com/twilio/twilio-go"
	twilioApi "github.com/twilio/twilio-go/rest/api/v2010"
)

// MessageCreator abstracts the Twilio message creation API for testing
type MessageCreator interface {
	CreateMessage(params *twilioApi.CreateMessageParams) (*twilioApi.ApiV2010Message, error)
}

type TwilioClient struct {
	messageCreator MessageCreator
}

// NewTwilioClient creates a TwilioClient with the real Twilio API
func NewTwilioClient() *TwilioClient {
	client := twilio.NewRestClient()
	return &TwilioClient{
		messageCreator: client.Api,
	}
}

// NewTwilioClientWithCreator creates a TwilioClient with a custom MessageCreator (for testing)
func NewTwilioClientWithCreator(creator MessageCreator) *TwilioClient {
	return &TwilioClient{
		messageCreator: creator,
	}
}

func (t TwilioClient) SendSms(from string, to string, body string, dryRun bool) error {
	if dryRun {
		log.Printf("DRY RUN: Would have sent SMS from %s to %s with body: %s", from, to, body)
		return nil
	}

	params := &twilioApi.CreateMessageParams{}
	params.SetTo(to)
	params.SetFrom(from)
	params.SetBody(body)

	_, err := t.messageCreator.CreateMessage(params)
	return err
}
