package clients

import (
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

func (t TwilioClient) SendSms(from string, to string, body string) (*twilioApi.ApiV2010Message, error) {
	params := &twilioApi.CreateMessageParams{}
	params.SetTo(to)
	params.SetFrom(from)
	params.SetBody(body)

	return t.client.Api.CreateMessage(params)
}
