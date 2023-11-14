/*
 * This code was generated by
 * ___ _ _ _ _ _    _ ____    ____ ____ _    ____ ____ _  _ ____ ____ ____ ___ __   __
 *  |  | | | | |    | |  | __ |  | |__| | __ | __ |___ |\ | |___ |__/ |__|  | |  | |__/
 *  |  |_|_| | |___ | |__|    |__| |  | |    |__] |___ | \| |___ |  \ |  |  | |__| |  \
 *
 * Twilio - Ip_messaging
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

	"github.com/twilio/twilio-go/client"
)

// Optional parameters for the method 'CreateCredential'
type CreateCredentialParams struct {
	//
	Type *string `json:"Type,omitempty"`
	//
	FriendlyName *string `json:"FriendlyName,omitempty"`
	//
	Certificate *string `json:"Certificate,omitempty"`
	//
	PrivateKey *string `json:"PrivateKey,omitempty"`
	//
	Sandbox *bool `json:"Sandbox,omitempty"`
	//
	ApiKey *string `json:"ApiKey,omitempty"`
	//
	Secret *string `json:"Secret,omitempty"`
}

func (params *CreateCredentialParams) SetType(Type string) *CreateCredentialParams {
	params.Type = &Type
	return params
}
func (params *CreateCredentialParams) SetFriendlyName(FriendlyName string) *CreateCredentialParams {
	params.FriendlyName = &FriendlyName
	return params
}
func (params *CreateCredentialParams) SetCertificate(Certificate string) *CreateCredentialParams {
	params.Certificate = &Certificate
	return params
}
func (params *CreateCredentialParams) SetPrivateKey(PrivateKey string) *CreateCredentialParams {
	params.PrivateKey = &PrivateKey
	return params
}
func (params *CreateCredentialParams) SetSandbox(Sandbox bool) *CreateCredentialParams {
	params.Sandbox = &Sandbox
	return params
}
func (params *CreateCredentialParams) SetApiKey(ApiKey string) *CreateCredentialParams {
	params.ApiKey = &ApiKey
	return params
}
func (params *CreateCredentialParams) SetSecret(Secret string) *CreateCredentialParams {
	params.Secret = &Secret
	return params
}

//
func (c *ApiService) CreateCredential(params *CreateCredentialParams) (*IpMessagingV2Credential, error) {
	path := "/v2/Credentials"

	data := url.Values{}
	headers := make(map[string]interface{})

	if params != nil && params.Type != nil {
		data.Set("Type", *params.Type)
	}
	if params != nil && params.FriendlyName != nil {
		data.Set("FriendlyName", *params.FriendlyName)
	}
	if params != nil && params.Certificate != nil {
		data.Set("Certificate", *params.Certificate)
	}
	if params != nil && params.PrivateKey != nil {
		data.Set("PrivateKey", *params.PrivateKey)
	}
	if params != nil && params.Sandbox != nil {
		data.Set("Sandbox", fmt.Sprint(*params.Sandbox))
	}
	if params != nil && params.ApiKey != nil {
		data.Set("ApiKey", *params.ApiKey)
	}
	if params != nil && params.Secret != nil {
		data.Set("Secret", *params.Secret)
	}

	resp, err := c.requestHandler.Post(c.baseURL+path, data, headers)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	ps := &IpMessagingV2Credential{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}

	return ps, err
}

//
func (c *ApiService) DeleteCredential(Sid string) error {
	path := "/v2/Credentials/{Sid}"
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

//
func (c *ApiService) FetchCredential(Sid string) (*IpMessagingV2Credential, error) {
	path := "/v2/Credentials/{Sid}"
	path = strings.Replace(path, "{"+"Sid"+"}", Sid, -1)

	data := url.Values{}
	headers := make(map[string]interface{})

	resp, err := c.requestHandler.Get(c.baseURL+path, data, headers)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	ps := &IpMessagingV2Credential{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}

	return ps, err
}

// Optional parameters for the method 'ListCredential'
type ListCredentialParams struct {
	// How many resources to return in each list page. The default is 50, and the maximum is 1000.
	PageSize *int `json:"PageSize,omitempty"`
	// Max number of records to return.
	Limit *int `json:"limit,omitempty"`
}

func (params *ListCredentialParams) SetPageSize(PageSize int) *ListCredentialParams {
	params.PageSize = &PageSize
	return params
}
func (params *ListCredentialParams) SetLimit(Limit int) *ListCredentialParams {
	params.Limit = &Limit
	return params
}

// Retrieve a single page of Credential records from the API. Request is executed immediately.
func (c *ApiService) PageCredential(params *ListCredentialParams, pageToken, pageNumber string) (*ListCredentialResponse, error) {
	path := "/v2/Credentials"

	data := url.Values{}
	headers := make(map[string]interface{})

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

	ps := &ListCredentialResponse{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}

	return ps, err
}

// Lists Credential records from the API as a list. Unlike stream, this operation is eager and loads 'limit' records into memory before returning.
func (c *ApiService) ListCredential(params *ListCredentialParams) ([]IpMessagingV2Credential, error) {
	response, errors := c.StreamCredential(params)

	records := make([]IpMessagingV2Credential, 0)
	for record := range response {
		records = append(records, record)
	}

	if err := <-errors; err != nil {
		return nil, err
	}

	return records, nil
}

// Streams Credential records from the API as a channel stream. This operation lazily loads records as efficiently as possible until the limit is reached.
func (c *ApiService) StreamCredential(params *ListCredentialParams) (chan IpMessagingV2Credential, chan error) {
	if params == nil {
		params = &ListCredentialParams{}
	}
	params.SetPageSize(client.ReadLimits(params.PageSize, params.Limit))

	recordChannel := make(chan IpMessagingV2Credential, 1)
	errorChannel := make(chan error, 1)

	response, err := c.PageCredential(params, "", "")
	if err != nil {
		errorChannel <- err
		close(recordChannel)
		close(errorChannel)
	} else {
		go c.streamCredential(response, params, recordChannel, errorChannel)
	}

	return recordChannel, errorChannel
}

func (c *ApiService) streamCredential(response *ListCredentialResponse, params *ListCredentialParams, recordChannel chan IpMessagingV2Credential, errorChannel chan error) {
	curRecord := 1

	for response != nil {
		responseRecords := response.Credentials
		for item := range responseRecords {
			recordChannel <- responseRecords[item]
			curRecord += 1
			if params.Limit != nil && *params.Limit < curRecord {
				close(recordChannel)
				close(errorChannel)
				return
			}
		}

		record, err := client.GetNext(c.baseURL, response, c.getNextListCredentialResponse)
		if err != nil {
			errorChannel <- err
			break
		} else if record == nil {
			break
		}

		response = record.(*ListCredentialResponse)
	}

	close(recordChannel)
	close(errorChannel)
}

func (c *ApiService) getNextListCredentialResponse(nextPageUrl string) (interface{}, error) {
	if nextPageUrl == "" {
		return nil, nil
	}
	resp, err := c.requestHandler.Get(nextPageUrl, nil, nil)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	ps := &ListCredentialResponse{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}
	return ps, nil
}

// Optional parameters for the method 'UpdateCredential'
type UpdateCredentialParams struct {
	//
	FriendlyName *string `json:"FriendlyName,omitempty"`
	//
	Certificate *string `json:"Certificate,omitempty"`
	//
	PrivateKey *string `json:"PrivateKey,omitempty"`
	//
	Sandbox *bool `json:"Sandbox,omitempty"`
	//
	ApiKey *string `json:"ApiKey,omitempty"`
	//
	Secret *string `json:"Secret,omitempty"`
}

func (params *UpdateCredentialParams) SetFriendlyName(FriendlyName string) *UpdateCredentialParams {
	params.FriendlyName = &FriendlyName
	return params
}
func (params *UpdateCredentialParams) SetCertificate(Certificate string) *UpdateCredentialParams {
	params.Certificate = &Certificate
	return params
}
func (params *UpdateCredentialParams) SetPrivateKey(PrivateKey string) *UpdateCredentialParams {
	params.PrivateKey = &PrivateKey
	return params
}
func (params *UpdateCredentialParams) SetSandbox(Sandbox bool) *UpdateCredentialParams {
	params.Sandbox = &Sandbox
	return params
}
func (params *UpdateCredentialParams) SetApiKey(ApiKey string) *UpdateCredentialParams {
	params.ApiKey = &ApiKey
	return params
}
func (params *UpdateCredentialParams) SetSecret(Secret string) *UpdateCredentialParams {
	params.Secret = &Secret
	return params
}

//
func (c *ApiService) UpdateCredential(Sid string, params *UpdateCredentialParams) (*IpMessagingV2Credential, error) {
	path := "/v2/Credentials/{Sid}"
	path = strings.Replace(path, "{"+"Sid"+"}", Sid, -1)

	data := url.Values{}
	headers := make(map[string]interface{})

	if params != nil && params.FriendlyName != nil {
		data.Set("FriendlyName", *params.FriendlyName)
	}
	if params != nil && params.Certificate != nil {
		data.Set("Certificate", *params.Certificate)
	}
	if params != nil && params.PrivateKey != nil {
		data.Set("PrivateKey", *params.PrivateKey)
	}
	if params != nil && params.Sandbox != nil {
		data.Set("Sandbox", fmt.Sprint(*params.Sandbox))
	}
	if params != nil && params.ApiKey != nil {
		data.Set("ApiKey", *params.ApiKey)
	}
	if params != nil && params.Secret != nil {
		data.Set("Secret", *params.Secret)
	}

	resp, err := c.requestHandler.Post(c.baseURL+path, data, headers)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	ps := &IpMessagingV2Credential{}
	if err := json.NewDecoder(resp.Body).Decode(ps); err != nil {
		return nil, err
	}

	return ps, err
}
