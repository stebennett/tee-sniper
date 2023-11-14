/*
 * This code was generated by
 * ___ _ _ _ _ _    _ ____    ____ ____ _    ____ ____ _  _ ____ ____ ____ ___ __   __
 *  |  | | | | |    | |  | __ |  | |__| | __ | __ |___ |\ | |___ |__/ |__|  | |  | |__/
 *  |  |_|_| | |___ | |__|    |__| |  | |    |__] |___ | \| |___ |  \ |  |  | |__| |  \
 *
 * Twilio - Taskrouter
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

// TaskrouterV1Task struct for TaskrouterV1Task
type TaskrouterV1Task struct {
	// The SID of the [Account](https://www.twilio.com/docs/iam/api/account) that created the Task resource.
	AccountSid *string `json:"account_sid,omitempty"`
	// The number of seconds since the Task was created.
	Age              *int    `json:"age,omitempty"`
	AssignmentStatus *string `json:"assignment_status,omitempty"`
	// The JSON string with custom attributes of the work. **Note** If this property has been assigned a value, it will only be displayed in FETCH action that returns a single resource. Otherwise, it will be null.
	Attributes *string `json:"attributes,omitempty"`
	// An object that contains the [addon](https://www.twilio.com/docs/taskrouter/marketplace) data for all installed addons.
	Addons *string `json:"addons,omitempty"`
	// The date and time in GMT when the resource was created specified in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	DateCreated *time.Time `json:"date_created,omitempty"`
	// The date and time in GMT when the resource was last updated specified in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	DateUpdated *time.Time `json:"date_updated,omitempty"`
	// The date and time in GMT when the Task entered the TaskQueue, specified in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	TaskQueueEnteredDate *time.Time `json:"task_queue_entered_date,omitempty"`
	// The current priority score of the Task as assigned to a Worker by the workflow. Tasks with higher priority values will be assigned before Tasks with lower values.
	Priority *int `json:"priority,omitempty"`
	// The reason the Task was canceled or completed, if applicable.
	Reason *string `json:"reason,omitempty"`
	// The unique string that we created to identify the Task resource.
	Sid *string `json:"sid,omitempty"`
	// The SID of the TaskQueue.
	TaskQueueSid *string `json:"task_queue_sid,omitempty"`
	// The friendly name of the TaskQueue.
	TaskQueueFriendlyName *string `json:"task_queue_friendly_name,omitempty"`
	// The SID of the TaskChannel.
	TaskChannelSid *string `json:"task_channel_sid,omitempty"`
	// The unique name of the TaskChannel.
	TaskChannelUniqueName *string `json:"task_channel_unique_name,omitempty"`
	// The amount of time in seconds that the Task can live before being assigned.
	Timeout *int `json:"timeout,omitempty"`
	// The SID of the Workflow that is controlling the Task.
	WorkflowSid *string `json:"workflow_sid,omitempty"`
	// The friendly name of the Workflow that is controlling the Task.
	WorkflowFriendlyName *string `json:"workflow_friendly_name,omitempty"`
	// The SID of the Workspace that contains the Task.
	WorkspaceSid *string `json:"workspace_sid,omitempty"`
	// The absolute URL of the Task resource.
	Url *string `json:"url,omitempty"`
	// The URLs of related resources.
	Links *map[string]interface{} `json:"links,omitempty"`
	// The date and time in GMT indicating the ordering for routing of the Task specified in [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format.
	VirtualStartTime *time.Time `json:"virtual_start_time,omitempty"`
}
