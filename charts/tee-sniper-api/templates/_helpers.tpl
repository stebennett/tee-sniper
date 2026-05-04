{{/*
Expand the name of the chart.
*/}}
{{- define "tee-sniper-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified app name (release-prefixed).
*/}}
{{- define "tee-sniper-api.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Common labels.
*/}}
{{- define "tee-sniper-api.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "tee-sniper-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels (stable; never include version).
*/}}
{{- define "tee-sniper-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "tee-sniper-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Service account name.
*/}}
{{- define "tee-sniper-api.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "tee-sniper-api.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
API image reference. Falls back to .Chart.AppVersion when tag is empty.
*/}}
{{- define "tee-sniper-api.apiImage" -}}
{{- $tag := default .Chart.AppVersion .Values.api.image.tag -}}
{{- printf "%s:%s" .Values.api.image.repository $tag -}}
{{- end -}}

{{/*
CLI image reference for a given cronjob entry. Allows per-entry override.
Usage: include "tee-sniper-api.cliImage" (dict "ctx" $ "entry" $entry)
*/}}
{{- define "tee-sniper-api.cliImage" -}}
{{- $ctx := .ctx -}}
{{- $entry := .entry -}}
{{- $repo := default $ctx.Values.cli.image.repository (dig "image" "repository" "" $entry) -}}
{{- $tag := default (default $ctx.Chart.AppVersion $ctx.Values.cli.image.tag) (dig "image" "tag" "" $entry) -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end -}}

{{/*
In-cluster API URL used by CronJob pods.
*/}}
{{- define "tee-sniper-api.internalUrl" -}}
{{- printf "http://%s.%s.svc.cluster.local" (include "tee-sniper-api.fullname" .) .Release.Namespace -}}
{{- end -}}
