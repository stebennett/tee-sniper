/*
 * This code was generated by
 * ___ _ _ _ _ _    _ ____    ____ ____ _    ____ ____ _  _ ____ ____ ____ ___ __   __
 *  |  | | | | |    | |  | __ |  | |__| | __ | __ |___ |\ | |___ |__/ |__|  | |  | |__/
 *  |  |_|_| | |___ | |__|    |__| |  | |    |__] |___ | \| |___ |  \ |  |  | |__| |  \
 *
 * Twilio - Numbers
 * This is the public Twilio REST API.
 *
 * NOTE: This class is auto generated by OpenAPI Generator.
 * https://openapi-generator.tech
 * Do not edit the class manually.
 */

package openapi

// NumbersV2HostedNumberOrderCapabilities Set of booleans describing the capabilities hosted on Twilio's platform. SMS is currently only supported.
type NumbersV2HostedNumberOrderCapabilities struct {
	Mms   bool `json:"mms,omitempty"`
	Sms   bool `json:"sms,omitempty"`
	Voice bool `json:"voice,omitempty"`
	Fax   bool `json:"fax,omitempty"`
}
