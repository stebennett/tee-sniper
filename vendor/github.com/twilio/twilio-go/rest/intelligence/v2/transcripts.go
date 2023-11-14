/*
 * This code was generated by
 * ___ _ _ _ _ _    _ ____    ____ ____ _    ____ ____ _  _ ____ ____ ____ ___ __   __
 *  |  | | | | |    | |  | __ |  | |__| | __ | __ |___ |\ | |___ |__/ |__|  | |  | |__/
 *  |  |_|_| | |___ | |__|    |__| |  | |    |__] |___ | \| |___ |  \ |  |  | |__| |  \
 *
 * Twilio - Intelligence
 * This is the public Twilio REST API.
 *
 * NOTE: This class is auto generated by OpenAPI Generator.
 * https://openapi-generator.tech
 * Do not edit the class manually.
 */

package openapi

import (
	"encoding/json"
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/twilio/twilio-go/client"
)

// Optional parameters for the method 'CreateTranscript'
type CreateTranscriptParams struct {
	// The unique SID identifier of the Service.
	ServiceSid *string `json:"ServiceSid,omitempty"`
	// JSON object describing Media Channel including Source and Participants
	Channel *interface{} `json:"Channel,omitempty"`
	// Used to store client provided metadata. Maximum of 64 double-byte UTF8 characters.
	CustomerKey *string `json:"CustomerKey,omitempty"`
	// The date that this Transcript's media was started, given in ISO 8601 format.
	MediaStartTime *time.Time `json:"MediaStartTime,omitempty"`
}

func (params *CreateTranscriptParams) SetServiceSid(ServiceSid string) *CreateTranscriptParams {
	params.ServiceSid = &ServiceSid
	return params
}
func (params *CreateTranscriptParams) SetChannel(Channel interface{}) *CreateTranscriptParams {
	params.Channel = &Channel
	return params
}
func (params *CreateTranscriptParams) SetCustomerKey(CustomerKey string) *CreateTranscriptParams {
	params.CustomerKey = &CustomerKey
	return params
}
func (params *CreateTranscriptParams) SetMediaStartTime(MediaStartTime time.Time) *CreateTranscriptParams {
	params.MediaStartTime = &MediaStartTime
	return params
}

// Create a new Transcript for the service
func (c *ApiService) CreateTranscript(params *CreateTranscriptParams) (*IntelligenceV2Transcript, error) {
	path := "/v2/Transcripts"

	data := url.Values{}
	headers := make(map[string]interface{})

	if params != nil && params.ServiceSid != nil {
		data.Set("ServiceSid", *params.ServiceSid)
	}
	if params != nil && params.Channel != nil {
		v, err := json.Marshal(params.Channel)

		if err != nil {
			return nil, err
		}

		data.Set("Channel", string(v))
	}
	if params != nil && params.CustomerKey != nil {
		data.Set("CustomerKey", *params.CustomerKey)
	}
	if params != nil && params.MediaStartTime != nil {
		data.Set("MediaStartTime", fmt.Sprint((*params.MediaStartTime).Format(time.RFC3339)))
	}

	resp, err := c.requestHandler.Post(c.baseURL+path, data, headers)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	ps := &IntelligenceV2Transcript{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}

	return ps, err
}

// Delete a specific Transcript.
func (c *ApiService) DeleteTranscript(Sid string) error {
	path := "/v2/Transcripts/{Sid}"
	path = strings.Replace(path, "{"+"Sid"+"}", Sid, -1)

	data := url.Values{}
	headers := make(map[string]interface{})

	resp, err := c.requestHandler.Delete(c.baseURL+path, data, headers)
	if err != nil {
		return err
	}

	defer resp.Body.Close()

	return nil
}

// Fetch a specific Transcript.
func (c *ApiService) FetchTranscript(Sid string) (*IntelligenceV2Transcript, error) {
	path := "/v2/Transcripts/{Sid}"
	path = strings.Replace(path, "{"+"Sid"+"}", Sid, -1)

	data := url.Values{}
	headers := make(map[string]interface{})

	resp, err := c.requestHandler.Get(c.baseURL+path, data, headers)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	ps := &IntelligenceV2Transcript{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}

	return ps, err
}

// Optional parameters for the method 'ListTranscript'
type ListTranscriptParams struct {
	// The unique SID identifier of the Service.
	ServiceSid *string `json:"ServiceSid,omitempty"`
	// Filter by before StartTime.
	BeforeStartTime *string `json:"BeforeStartTime,omitempty"`
	// Filter by after StartTime.
	AfterStartTime *string `json:"AfterStartTime,omitempty"`
	// Filter by before DateCreated.
	BeforeDateCreated *string `json:"BeforeDateCreated,omitempty"`
	// Filter by after DateCreated.
	AfterDateCreated *string `json:"AfterDateCreated,omitempty"`
	// Filter by status.
	Status *string `json:"Status,omitempty"`
	// Filter by Language Code.
	LanguageCode *string `json:"LanguageCode,omitempty"`
	// Filter by SourceSid.
	SourceSid *string `json:"SourceSid,omitempty"`
	// How many resources to return in each list page. The default is 50, and the maximum is 1000.
	PageSize *int `json:"PageSize,omitempty"`
	// Max number of records to return.
	Limit *int `json:"limit,omitempty"`
}

func (params *ListTranscriptParams) SetServiceSid(ServiceSid string) *ListTranscriptParams {
	params.ServiceSid = &ServiceSid
	return params
}
func (params *ListTranscriptParams) SetBeforeStartTime(BeforeStartTime string) *ListTranscriptParams {
	params.BeforeStartTime = &BeforeStartTime
	return params
}
func (params *ListTranscriptParams) SetAfterStartTime(AfterStartTime string) *ListTranscriptParams {
	params.AfterStartTime = &AfterStartTime
	return params
}
func (params *ListTranscriptParams) SetBeforeDateCreated(BeforeDateCreated string) *ListTranscriptParams {
	params.BeforeDateCreated = &BeforeDateCreated
	return params
}
func (params *ListTranscriptParams) SetAfterDateCreated(AfterDateCreated string) *ListTranscriptParams {
	params.AfterDateCreated = &AfterDateCreated
	return params
}
func (params *ListTranscriptParams) SetStatus(Status string) *ListTranscriptParams {
	params.Status = &Status
	return params
}
func (params *ListTranscriptParams) SetLanguageCode(LanguageCode string) *ListTranscriptParams {
	params.LanguageCode = &LanguageCode
	return params
}
func (params *ListTranscriptParams) SetSourceSid(SourceSid string) *ListTranscriptParams {
	params.SourceSid = &SourceSid
	return params
}
func (params *ListTranscriptParams) SetPageSize(PageSize int) *ListTranscriptParams {
	params.PageSize = &PageSize
	return params
}
func (params *ListTranscriptParams) SetLimit(Limit int) *ListTranscriptParams {
	params.Limit = &Limit
	return params
}

// Retrieve a single page of Transcript records from the API. Request is executed immediately.
func (c *ApiService) PageTranscript(params *ListTranscriptParams, pageToken, pageNumber string) (*ListTranscriptResponse, error) {
	path := "/v2/Transcripts"

	data := url.Values{}
	headers := make(map[string]interface{})

	if params != nil && params.ServiceSid != nil {
		data.Set("ServiceSid", *params.ServiceSid)
	}
	if params != nil && params.BeforeStartTime != nil {
		data.Set("BeforeStartTime", *params.BeforeStartTime)
	}
	if params != nil && params.AfterStartTime != nil {
		data.Set("AfterStartTime", *params.AfterStartTime)
	}
	if params != nil && params.BeforeDateCreated != nil {
		data.Set("BeforeDateCreated", *params.BeforeDateCreated)
	}
	if params != nil && params.AfterDateCreated != nil {
		data.Set("AfterDateCreated", *params.AfterDateCreated)
	}
	if params != nil && params.Status != nil {
		data.Set("Status", *params.Status)
	}
	if params != nil && params.LanguageCode != nil {
		data.Set("LanguageCode", *params.LanguageCode)
	}
	if params != nil && params.SourceSid != nil {
		data.Set("SourceSid", *params.SourceSid)
	}
	if params != nil && params.PageSize != nil {
		data.Set("PageSize", fmt.Sprint(*params.PageSize))
	}

	if pageToken != "" {
		data.Set("PageToken", pageToken)
	}
	if pageNumber != "" {
		data.Set("Page", pageNumber)
	}

	resp, err := c.requestHandler.Get(c.baseURL+path, data, headers)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	ps := &ListTranscriptResponse{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}

	return ps, err
}

// Lists Transcript records from the API as a list. Unlike stream, this operation is eager and loads 'limit' records into memory before returning.
func (c *ApiService) ListTranscript(params *ListTranscriptParams) ([]IntelligenceV2Transcript, error) {
	response, errors := c.StreamTranscript(params)

	records := make([]IntelligenceV2Transcript, 0)
	for record := range response {
		records = append(records, record)
	}

	if err := <-errors; err != nil {
		return nil, err
	}

	return records, nil
}

// Streams Transcript records from the API as a channel stream. This operation lazily loads records as efficiently as possible until the limit is reached.
func (c *ApiService) StreamTranscript(params *ListTranscriptParams) (chan IntelligenceV2Transcript, chan error) {
	if params == nil {
		params = &ListTranscriptParams{}
	}
	params.SetPageSize(client.ReadLimits(params.PageSize, params.Limit))

	recordChannel := make(chan IntelligenceV2Transcript, 1)
	errorChannel := make(chan error, 1)

	response, err := c.PageTranscript(params, "", "")
	if err != nil {
		errorChannel <- err
		close(recordChannel)
		close(errorChannel)
	} else {
		go c.streamTranscript(response, params, recordChannel, errorChannel)
	}

	return recordChannel, errorChannel
}

func (c *ApiService) streamTranscript(response *ListTranscriptResponse, params *ListTranscriptParams, recordChannel chan IntelligenceV2Transcript, errorChannel chan error) {
	curRecord := 1

	for response != nil {
		responseRecords := response.Transcripts
		for item := range responseRecords {
			recordChannel <- responseRecords[item]
			curRecord += 1
			if params.Limit != nil && *params.Limit < curRecord {
				close(recordChannel)
				close(errorChannel)
				return
			}
		}

		record, err := client.GetNext(c.baseURL, response, c.getNextListTranscriptResponse)
		if err != nil {
			errorChannel <- err
			break
		} else if record == nil {
			break
		}

		response = record.(*ListTranscriptResponse)
	}

	close(recordChannel)
	close(errorChannel)
}

func (c *ApiService) getNextListTranscriptResponse(nextPageUrl string) (interface{}, error) {
	if nextPageUrl == "" {
		return nil, nil
	}
	resp, err := c.requestHandler.Get(nextPageUrl, nil, nil)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	ps := &ListTranscriptResponse{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}
	return ps, nil
}
