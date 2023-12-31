/*
 * This code was generated by
 * ___ _ _ _ _ _    _ ____    ____ ____ _    ____ ____ _  _ ____ ____ ____ ___ __   __
 *  |  | | | | |    | |  | __ |  | |__| | __ | __ |___ |\ | |___ |__/ |__|  | |  | |__/
 *  |  |_|_| | |___ | |__|    |__| |  | |    |__] |___ | \| |___ |  \ |  |  | |__| |  \
 *
 * Twilio - Media
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

// MediaV1MediaProcessor struct for MediaV1MediaProcessor
type MediaV1MediaProcessor struct {
	// The SID of the [Account](https://www.twilio.com/docs/iam/api/account) that created the MediaProcessor resource.
	AccountSid *string `json:"account_sid,omitempty"`
	// The unique string generated to identify the MediaProcessor resource.
	Sid *string `json:"sid,omitempty"`
	// The date and time in GMT when the resource was created specified in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	DateCreated *time.Time `json:"date_created,omitempty"`
	// The date and time in GMT when the resource was last updated specified in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	DateUpdated *time.Time `json:"date_updated,omitempty"`
	// The [Media Extension](/docs/live/media-extensions-overview) name or URL. Ex: `video-composer-v2`
	Extension *string `json:"extension,omitempty"`
	// The context of the Media Extension, represented as a JSON dictionary. See the documentation for the specific [Media Extension](/docs/live/media-extensions-overview) you are using for more information about the context to send.
	ExtensionContext *string `json:"extension_context,omitempty"`
	Status           *string `json:"status,omitempty"`
	// The absolute URL of the resource.
	Url *string `json:"url,omitempty"`
	// The reason why a MediaProcessor ended. When a MediaProcessor is in progress, will be `null`. When a MediaProcessor is completed, can be `ended-via-api`, `max-duration-exceeded`, `error-loading-extension`, `error-streaming-media` or `internal-service-error`. See [ended reasons](/docs/live/api/mediaprocessors#mediaprocessor-ended-reason-values) for more details.
	EndedReason *string `json:"ended_reason,omitempty"`
	// The URL to which Twilio will send asynchronous webhook requests for every MediaProcessor event. See [Status Callbacks](/docs/live/api/status-callbacks) for details.
	StatusCallback *string `json:"status_callback,omitempty"`
	// The HTTP method Twilio should use to call the `status_callback` URL. Can be `POST` or `GET` and the default is `POST`.
	StatusCallbackMethod *string `json:"status_callback_method,omitempty"`
	// The maximum time, in seconds, that the MediaProcessor can run before automatically ends. The default value is 300 seconds, and the maximum value is 90000 seconds. Once this maximum duration is reached, Twilio will end the MediaProcessor, regardless of whether media is still streaming.
	MaxDuration *int `json:"max_duration,omitempty"`
}
