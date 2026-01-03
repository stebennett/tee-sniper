{{/*
Expand the name of the chart.
*/}}
{{- define "tee-sniper.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "tee-sniper.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "tee-sniper.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "tee-sniper.labels" -}}
helm.sh/chart: {{ include "tee-sniper.chart" . }}
{{ include "tee-sniper.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "tee-sniper.selectorLabels" -}}
app.kubernetes.io/name: {{ include "tee-sniper.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "tee-sniper.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "tee-sniper.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the secret to use
*/}}
{{- define "tee-sniper.secretName" -}}
{{- if .Values.secrets.create }}
{{- include "tee-sniper.fullname" . }}
{{- else }}
{{- .Values.existingSecret }}
{{- end }}
{{- end }}

{{/*
Create the name of the configmap to use
*/}}
{{- define "tee-sniper.configMapName" -}}
{{- include "tee-sniper.fullname" . }}
{{- end }}
