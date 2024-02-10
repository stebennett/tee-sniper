package clients

import (
	"log"

	twilio "github.com/twilio/twilio-go"
	twilioApi "github.com/twilio/twilio-go/rest/api/v2010"
)

type TwilioClient struct {
	client *twilio.RestClient
}

func NewTwilioClient() *TwilioClient {
	return &TwilioClient{
		client: twilio.NewRestClient(),
	}
}

func (t TwilioClient) SendSms(from string, to string, body string, dryRun bool) (*twilioApi.ApiV2010Message, error) {
	if dryRun {
		log.Printf("DRY RUN: Would have sent SMS from %s to %s with body: %s", from, to, body)
		return nil, nil
	}

	params := &twilioApi.CreateMessageParams{}
	params.SetTo(to)
	params.SetFrom(from)
	params.SetBody(body)

	return t.client.Api.CreateMessage(params)
}
