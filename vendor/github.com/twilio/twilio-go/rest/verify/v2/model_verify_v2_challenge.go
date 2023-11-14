/*
 * This code was generated by
 * ___ _ _ _ _ _    _ ____    ____ ____ _    ____ ____ _  _ ____ ____ ____ ___ __   __
 *  |  | | | | |    | |  | __ |  | |__| | __ | __ |___ |\ | |___ |__/ |__|  | |  | |__/
 *  |  |_|_| | |___ | |__|    |__| |  | |    |__] |___ | \| |___ |  \ |  |  | |__| |  \
 *
 * Twilio - Verify
 * This is the public Twilio REST API.
 *
 * NOTE: This class is auto generated by OpenAPI Generator.
 * https://openapi-generator.tech
 * Do not edit the class manually.
 */

package openapi

import (
	"time"
)

// VerifyV2Challenge struct for VerifyV2Challenge
type VerifyV2Challenge struct {
	// A 34 character string that uniquely identifies this Challenge.
	Sid *string `json:"sid,omitempty"`
	// The unique SID identifier of the Account.
	AccountSid *string `json:"account_sid,omitempty"`
	// The unique SID identifier of the Service.
	ServiceSid *string `json:"service_sid,omitempty"`
	// The unique SID identifier of the Entity.
	EntitySid *string `json:"entity_sid,omitempty"`
	// Customer unique identity for the Entity owner of the Challenge. This identifier should be immutable, not PII, length between 8 and 64 characters, and generated by your external system, such as your user's UUID, GUID, or SID. It can only contain dash (-) separated alphanumeric characters.
	Identity *string `json:"identity,omitempty"`
	// The unique SID identifier of the Factor.
	FactorSid *string `json:"factor_sid,omitempty"`
	// The date that this Challenge was created, given in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	DateCreated *time.Time `json:"date_created,omitempty"`
	// The date that this Challenge was updated, given in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	DateUpdated *time.Time `json:"date_updated,omitempty"`
	// The date that this Challenge was responded, given in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	DateResponded *time.Time `json:"date_responded,omitempty"`
	// The date-time when this Challenge expires, given in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format. The default value is five (5) minutes after Challenge creation. The max value is sixty (60) minutes after creation.
	ExpirationDate  *time.Time `json:"expiration_date,omitempty"`
	Status          *string    `json:"status,omitempty"`
	RespondedReason *string    `json:"responded_reason,omitempty"`
	// Details provided to give context about the Challenge. Intended to be shown to the end user.
	Details *interface{} `json:"details,omitempty"`
	// Details provided to give context about the Challenge. Intended to be hidden from the end user. It must be a stringified JSON with only strings values eg. `{\"ip\": \"172.168.1.234\"}`
	HiddenDetails *interface{} `json:"hidden_details,omitempty"`
	// Custom metadata associated with the challenge. This is added by the Device/SDK directly to allow for the inclusion of device information. It must be a stringified JSON with only strings values eg. `{\"os\": \"Android\"}`. Can be up to 1024 characters in length.
	Metadata   *interface{} `json:"metadata,omitempty"`
	FactorType *string      `json:"factor_type,omitempty"`
	// The URL of this resource.
	Url *string `json:"url,omitempty"`
	// Contains a dictionary of URL links to nested resources of this Challenge.
	Links *map[string]interface{} `json:"links,omitempty"`
}