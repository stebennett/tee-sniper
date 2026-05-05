# Helm Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a single Helm chart (`charts/tee-sniper-api/`) that deploys the FastAPI service plus Bitnami Redis to a self-hosted k3s cluster and runs `tee-sniper-cli` as a list of CronJobs configured via values.

**Architecture:** One umbrella chart with Bitnami Redis pulled in as a pinned subchart dependency. Secrets are referenced by name only (created out-of-band by the user's 1Password operator). API is `ClusterIP` only — no Ingress. NetworkPolicy is opt-in with a configurable client label selector. CronJobs are rendered from a `cronjobs:` list in values, so adding a schedule is a one-line change.

**Tech Stack:** Helm 3.x, Bitnami Redis chart (subchart), JSON Schema for values validation, `kubeconform` for manifest validation, GitHub Actions for CI.

**Spec reference:** `docs/superpowers/specs/2026-05-03-helm-deployment-design.md`

---

## Prerequisites

The implementing engineer needs locally:
- `helm` v3.14 or later (`helm version`)
- `kubeconform` v0.6+ (`brew install kubeconform` on macOS)
- `yq` v4 (`brew install yq`) — for asserting rendered template fields
- A working internet connection so `helm dep update` can pull the Bitnami chart

Add the Bitnami chart repo once:
```sh
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

> **Note on Bitnami Redis chart version:** This plan pins to `20.6.2`. Before using it, run `helm search repo bitnami/redis --versions | head -5` and either confirm `20.6.2` is still available or substitute the latest `20.x` release. Update the version in `Chart.yaml` accordingly. Do not use `latest` or a floating version.

---

## File structure

What this plan creates:

```
charts/
  tee-sniper-api/
    Chart.yaml                   # Task 1
    .helmignore                  # Task 1
    values.yaml                  # Task 1 (skeleton), expanded across later tasks
    values-dev.yaml              # Task 6
    values-prod.yaml             # Task 6
    values.schema.json           # Task 3
    templates/
      _helpers.tpl               # Task 1
      NOTES.txt                  # Task 1
      serviceaccount.yaml        # Task 2
      configmap.yaml             # Task 2
      deployment.yaml            # Task 2
      service.yaml               # Task 2
      cronjob.yaml               # Task 4
      networkpolicy.yaml         # Task 5
    README.md                    # Task 7
```

Modified:
- `.gitignore` — Task 1, ignore pulled subcharts
- `.github/workflows/helm-chart.yml` — Task 8 (new file, but listed under modifications since CI is an existing concern)

Each template file owns one Kubernetes resource kind. `_helpers.tpl` owns shared label/name templates. Splitting by resource keeps each file small enough to reason about and easy to diff.

---

## Task 1: Chart skeleton with Bitnami Redis dependency

**Goal:** A bare chart that lints clean, pulls the Redis subchart, and renders an empty release.

**Files:**
- Create: `charts/tee-sniper-api/Chart.yaml`
- Create: `charts/tee-sniper-api/.helmignore`
- Create: `charts/tee-sniper-api/values.yaml`
- Create: `charts/tee-sniper-api/templates/_helpers.tpl`
- Create: `charts/tee-sniper-api/templates/NOTES.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Create `charts/tee-sniper-api/Chart.yaml`**

```yaml
apiVersion: v2
name: tee-sniper-api
description: Tee-sniper API service, Redis, and scheduled booking CronJobs.
type: application
version: 0.1.0
appVersion: "0.1.0"
kubeVersion: ">=1.27.0"
home: https://github.com/stebennett/tee-sniper
sources:
  - https://github.com/stebennett/tee-sniper
maintainers:
  - name: Steve Bennett
dependencies:
  - name: redis
    version: 20.6.2
    repository: https://charts.bitnami.com/bitnami
    condition: redis.enabled
```

- [ ] **Step 2: Create `charts/tee-sniper-api/.helmignore`**

```
.DS_Store
.git/
.gitignore
.idea/
.vscode/
*.swp
*.tmp
*.bak
*.orig
README.md.gotmpl
```

> **Note:** Do NOT include `*.tgz` in `.helmignore`. Helm 4 treats `.helmignore` patterns as a filter when resolving subchart dependencies, so ignoring `*.tgz` makes subchart packages invisible and breaks `helm template`. The packaging-output `.tgz` files (e.g., `tee-sniper-api-0.1.0.tgz`) are kept out of git via `.gitignore`, not `.helmignore`.

- [ ] **Step 3: Create `charts/tee-sniper-api/values.yaml` skeleton**

```yaml
api:
  image:
    repository: ghcr.io/stebennett/tee-sniper-api
    tag: ""
    pullPolicy: IfNotPresent
  replicas: 2
  resources:
    requests:
      memory: 128Mi
      cpu: 100m
    limits:
      memory: 256Mi
      cpu: 500m
  config:
    logLevel: INFO
  existingSecret: tee-sniper-api
  service:
    port: 80
    targetPort: 8000

cli:
  image:
    repository: ghcr.io/stebennett/tee-sniper-cli
    tag: ""
    pullPolicy: IfNotPresent
  existingSecret: tee-sniper-cli

cronjobs: []

redis:
  enabled: true
  architecture: standalone
  auth:
    enabled: true
    existingSecret: redis-auth
    existingSecretPasswordKey: password
  master:
    persistence:
      enabled: true
      storageClass: local-path
      size: 1Gi

networkPolicy:
  enabled: false
  apiAllowedClients:
    matchLabels:
      tee-sniper.io/api-client: "true"

serviceAccount:
  create: true
  name: ""
```

- [ ] **Step 4: Create `charts/tee-sniper-api/templates/_helpers.tpl`**

```
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
```

- [ ] **Step 5: Create `charts/tee-sniper-api/templates/NOTES.txt`**

```
Tee-Sniper API installed.

Release:    {{ .Release.Name }}
Namespace:  {{ .Release.Namespace }}
Chart:      {{ .Chart.Name }}-{{ .Chart.Version }} (appVersion {{ .Chart.AppVersion }})

The API is reachable in-cluster at:
  {{ include "tee-sniper-api.internalUrl" . }}

Required Secrets (must already exist in namespace {{ .Release.Namespace }}):
  - {{ .Values.api.existingSecret }} (keys: shared-secret)
  - {{ .Values.cli.existingSecret }} (keys: username, pin, twilio-account-sid, twilio-auth-token, to-number, from-number, shared-secret)
{{- if .Values.redis.enabled }}
  - {{ .Values.redis.auth.existingSecret }} (keys: {{ .Values.redis.auth.existingSecretPasswordKey }})
{{- end }}

Verify pods are healthy:
  kubectl -n {{ .Release.Namespace }} get pods -l app.kubernetes.io/instance={{ .Release.Name }}
```

- [ ] **Step 6: Add subcharts directory to `.gitignore`**

Append to `.gitignore`:

```
# Helm: don't commit pulled subcharts (Chart.lock pins them)
charts/*/charts/
charts/*/*.tgz
```

- [ ] **Step 7: Pull the Redis subchart**

Run from repo root:
```sh
helm dep update charts/tee-sniper-api
```

Expected: creates `charts/tee-sniper-api/Chart.lock` and `charts/tee-sniper-api/charts/redis-20.6.2.tgz`. If the Bitnami repo no longer publishes 20.6.2, this command fails — replace `20.6.2` in `Chart.yaml` with a current `20.x` version from `helm search repo bitnami/redis --versions` and rerun.

- [ ] **Step 8: Lint the chart**

Run:
```sh
helm lint charts/tee-sniper-api
```

Expected output ends with `1 chart(s) linted, 0 chart(s) failed`.

- [ ] **Step 9: Verify it renders**

Run:
```sh
helm template testrel charts/tee-sniper-api --namespace tee-sniper > /tmp/render.yaml
wc -l /tmp/render.yaml
```

Expected: non-zero line count (Bitnami Redis renders even with no app templates yet). No errors.

- [ ] **Step 10: Commit**

```sh
git add charts/tee-sniper-api/Chart.yaml charts/tee-sniper-api/Chart.lock \
  charts/tee-sniper-api/.helmignore charts/tee-sniper-api/values.yaml \
  charts/tee-sniper-api/templates/_helpers.tpl charts/tee-sniper-api/templates/NOTES.txt \
  .gitignore
git commit -m "feat(helm): scaffold tee-sniper-api chart with Bitnami Redis dependency"
```

---

## Task 2: API Deployment, Service, ServiceAccount, ConfigMap

**Goal:** Render a working API Deployment that mounts secrets/config and exposes a ClusterIP service.

**Files:**
- Create: `charts/tee-sniper-api/templates/serviceaccount.yaml`
- Create: `charts/tee-sniper-api/templates/configmap.yaml`
- Create: `charts/tee-sniper-api/templates/deployment.yaml`
- Create: `charts/tee-sniper-api/templates/service.yaml`

- [ ] **Step 1: Create `templates/serviceaccount.yaml`**

```yaml
{{- if .Values.serviceAccount.create -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "tee-sniper-api.serviceAccountName" . }}
  labels:
    {{- include "tee-sniper-api.labels" . | nindent 4 }}
{{- end }}
```

- [ ] **Step 2: Create `templates/configmap.yaml`**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "tee-sniper-api.fullname" . }}-config
  labels:
    {{- include "tee-sniper-api.labels" . | nindent 4 }}
data:
  TSA_LOG_LEVEL: {{ .Values.api.config.logLevel | quote }}
```

- [ ] **Step 3: Create `templates/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "tee-sniper-api.fullname" . }}
  labels:
    {{- include "tee-sniper-api.labels" . | nindent 4 }}
    app.kubernetes.io/component: api
spec:
  replicas: {{ .Values.api.replicas }}
  selector:
    matchLabels:
      {{- include "tee-sniper-api.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: api
  template:
    metadata:
      labels:
        {{- include "tee-sniper-api.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: api
    spec:
      serviceAccountName: {{ include "tee-sniper-api.serviceAccountName" . }}
      containers:
        - name: api
          image: {{ include "tee-sniper-api.apiImage" . | quote }}
          imagePullPolicy: {{ .Values.api.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.api.service.targetPort }}
              protocol: TCP
          envFrom:
            - configMapRef:
                name: {{ include "tee-sniper-api.fullname" . }}-config
          env:
            - name: TSA_SHARED_SECRET
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.api.existingSecret }}
                  key: shared-secret
            {{- if .Values.redis.enabled }}
            - name: TSA_REDIS_HOST
              value: {{ printf "%s-redis-master" .Release.Name | quote }}
            - name: TSA_REDIS_PORT
              value: "6379"
            - name: TSA_REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.redis.auth.existingSecret }}
                  key: {{ .Values.redis.auth.existingSecretPasswordKey }}
            - name: TSA_REDIS_URL
              value: "redis://:$(TSA_REDIS_PASSWORD)@$(TSA_REDIS_HOST):$(TSA_REDIS_PORT)/0"
            {{- end }}
          resources:
            {{- toYaml .Values.api.resources | nindent 12 }}
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 15
            periodSeconds: 20
```

- [ ] **Step 4: Create `templates/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "tee-sniper-api.fullname" . }}
  labels:
    {{- include "tee-sniper-api.labels" . | nindent 4 }}
    app.kubernetes.io/component: api
spec:
  type: ClusterIP
  ports:
    - name: http
      port: {{ .Values.api.service.port }}
      targetPort: http
      protocol: TCP
  selector:
    {{- include "tee-sniper-api.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: api
```

- [ ] **Step 5: Lint and render**

```sh
helm lint charts/tee-sniper-api
helm template testrel charts/tee-sniper-api --namespace tee-sniper > /tmp/render.yaml
```

Expected: lint clean. Render succeeds.

- [ ] **Step 6: Assert rendered fields**

```sh
yq 'select(.kind == "Deployment" and .metadata.name == "testrel-tee-sniper-api") | .spec.replicas' /tmp/render.yaml
yq 'select(.kind == "Deployment" and .metadata.name == "testrel-tee-sniper-api") | .spec.template.spec.containers[0].image' /tmp/render.yaml
yq 'select(.kind == "Service" and .metadata.name == "testrel-tee-sniper-api") | .spec.type' /tmp/render.yaml
yq 'select(.kind == "Service" and .metadata.name == "testrel-tee-sniper-api") | .spec.ports[0].port' /tmp/render.yaml
```

Expected output (in order):
```
2
ghcr.io/stebennett/tee-sniper-api:0.1.0
ClusterIP
80
```

- [ ] **Step 7: Validate against Kubernetes API schemas**

```sh
helm template testrel charts/tee-sniper-api --namespace tee-sniper | \
  kubeconform -strict -summary -kubernetes-version 1.27.0 -ignore-missing-schemas
```

Expected output ends with `Summary: <N> resource(s) found, ... 0 errors`. The `-ignore-missing-schemas` flag is needed because Bitnami Redis pulls in some CRDs whose schemas aren't in the default set.

- [ ] **Step 8: Commit**

```sh
git add charts/tee-sniper-api/templates/serviceaccount.yaml \
  charts/tee-sniper-api/templates/configmap.yaml \
  charts/tee-sniper-api/templates/deployment.yaml \
  charts/tee-sniper-api/templates/service.yaml
git commit -m "feat(helm): add API Deployment, Service, ServiceAccount, ConfigMap"
```

---

## Task 3: values.schema.json with required-field and tag validation

**Goal:** Reject bad values at install time. Specifically, reject `tag: "latest"` and missing required fields.

**Files:**
- Create: `charts/tee-sniper-api/values.schema.json`

- [ ] **Step 1: Create `charts/tee-sniper-api/values.schema.json`**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "tee-sniper-api values",
  "type": "object",
  "required": ["api", "cli", "cronjobs", "redis", "networkPolicy"],
  "properties": {
    "api": {
      "type": "object",
      "required": ["image", "replicas", "resources", "config", "existingSecret", "service"],
      "properties": {
        "image": {
          "type": "object",
          "required": ["repository", "tag", "pullPolicy"],
          "properties": {
            "repository": { "type": "string", "minLength": 1 },
            "tag": { "type": "string", "not": { "enum": ["latest"] } },
            "pullPolicy": { "type": "string", "enum": ["Always", "IfNotPresent", "Never"] }
          }
        },
        "replicas": { "type": "integer", "minimum": 1 },
        "resources": { "type": "object" },
        "config": {
          "type": "object",
          "required": ["logLevel"],
          "properties": {
            "logLevel": { "type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"] }
          }
        },
        "existingSecret": { "type": "string", "minLength": 1 },
        "service": {
          "type": "object",
          "required": ["port", "targetPort"],
          "properties": {
            "port": { "type": "integer", "minimum": 1, "maximum": 65535 },
            "targetPort": { "type": "integer", "minimum": 1, "maximum": 65535 }
          }
        }
      }
    },
    "cli": {
      "type": "object",
      "required": ["image", "existingSecret"],
      "properties": {
        "image": {
          "type": "object",
          "required": ["repository", "tag", "pullPolicy"],
          "properties": {
            "repository": { "type": "string", "minLength": 1 },
            "tag": { "type": "string", "not": { "enum": ["latest"] } },
            "pullPolicy": { "type": "string", "enum": ["Always", "IfNotPresent", "Never"] }
          }
        },
        "existingSecret": { "type": "string", "minLength": 1 }
      }
    },
    "cronjobs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "schedule", "args"],
        "properties": {
          "name": { "type": "string", "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$" },
          "schedule": { "type": "string", "minLength": 1 },
          "suspend": { "type": "boolean" },
          "args": { "type": "array", "items": { "type": "string" } },
          "env": { "type": "array" },
          "image": {
            "type": "object",
            "properties": {
              "repository": { "type": "string", "minLength": 1 },
              "tag": { "type": "string", "not": { "enum": ["latest"] } }
            },
            "required": ["repository", "tag"]
          }
        }
      }
    },
    "redis": {
      "type": "object",
      "required": ["enabled"],
      "properties": {
        "enabled": { "type": "boolean" }
      }
    },
    "networkPolicy": {
      "type": "object",
      "required": ["enabled"],
      "properties": {
        "enabled": { "type": "boolean" },
        "apiAllowedClients": { "type": "object" }
      }
    },
    "serviceAccount": {
      "type": "object",
      "properties": {
        "create": { "type": "boolean" },
        "name": { "type": "string" }
      }
    }
  }
}
```

- [ ] **Step 2: Verify defaults still validate**

```sh
helm lint charts/tee-sniper-api
helm template testrel charts/tee-sniper-api > /dev/null
```

Expected: no schema errors.

- [ ] **Step 3: Verify schema rejects `tag: latest`**

```sh
helm template testrel charts/tee-sniper-api --set api.image.tag=latest 2>&1 | head -5
```

Expected: error mentioning `api.image.tag` and the failed `not` constraint. Exit code non-zero.

- [ ] **Step 4: Verify schema rejects bad logLevel**

```sh
helm template testrel charts/tee-sniper-api --set api.config.logLevel=VERBOSE 2>&1 | head -5
```

Expected: error mentioning `logLevel` enum.

- [ ] **Step 5: Verify schema rejects bad cronjob (missing required image.tag when image override is set)**

```sh
cat > /tmp/bad-cron.yaml <<'YAML'
cronjobs:
  - name: bad
    schedule: "0 * * * *"
    args: []
    image:
      repository: ghcr.io/stebennett/tee-sniper-cli
YAML
helm template testrel charts/tee-sniper-api -f /tmp/bad-cron.yaml 2>&1 | head -5
```

Expected: error mentioning the missing `tag` field.

- [ ] **Step 6: Commit**

```sh
git add charts/tee-sniper-api/values.schema.json
git commit -m "feat(helm): add values.schema.json with tag and field validation"
```

---

## Task 4: CronJob template

**Goal:** Each `cronjobs:` entry renders one `CronJob` that calls the in-cluster API.

**Files:**
- Create: `charts/tee-sniper-api/templates/cronjob.yaml`

> **Integration check before starting:** This template wires the `tee-sniper-cli` secret keys (`username`, `pin`, `twilio-account-sid`, `twilio-auth-token`, `to-number`, `from-number`) into env vars named `TEESNIPER_USERNAME`, `TEESNIPER_PIN`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TEESNIPER_TO_NUMBER`, `TEESNIPER_FROM_NUMBER`. The CLI must either (a) read these env vars directly in API-client mode, or (b) the operator must pass them as args with `$(VAR)` substitution. Before writing this template, run `grep -r "os.Getenv\|getenv" cmd/ pkg/` and check `pkg/config/config.go` to confirm what env var names (if any) the CLI accepts. If the CLI is args-only, document in the README that operators must add `-u=$(TEESNIPER_USERNAME) -p=$(TEESNIPER_PIN)` etc. to each cronjob entry's `args` list.

- [ ] **Step 1: Create `templates/cronjob.yaml`**

```yaml
{{- range $entry := .Values.cronjobs }}
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: {{ include "tee-sniper-api.fullname" $ }}-{{ $entry.name }}
  labels:
    {{- include "tee-sniper-api.labels" $ | nindent 4 }}
    app.kubernetes.io/component: cli
    tee-sniper.io/cronjob: {{ $entry.name | quote }}
spec:
  schedule: {{ $entry.schedule | quote }}
  suspend: {{ $entry.suspend | default false }}
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        metadata:
          labels:
            {{- include "tee-sniper-api.selectorLabels" $ | nindent 12 }}
            app.kubernetes.io/component: cli
            tee-sniper.io/cronjob: {{ $entry.name | quote }}
        spec:
          restartPolicy: OnFailure
          serviceAccountName: {{ include "tee-sniper-api.serviceAccountName" $ }}
          containers:
            - name: cli
              image: {{ include "tee-sniper-api.cliImage" (dict "ctx" $ "entry" $entry) | quote }}
              imagePullPolicy: {{ $.Values.cli.image.pullPolicy }}
              args:
                - "--api-url={{ include "tee-sniper-api.internalUrl" $ }}"
                {{- range $arg := $entry.args }}
                - {{ $arg | quote }}
                {{- end }}
              env:
                - name: TSA_SHARED_SECRET
                  valueFrom:
                    secretKeyRef:
                      name: {{ $.Values.cli.existingSecret }}
                      key: shared-secret
                - name: TEESNIPER_USERNAME
                  valueFrom:
                    secretKeyRef:
                      name: {{ $.Values.cli.existingSecret }}
                      key: username
                - name: TEESNIPER_PIN
                  valueFrom:
                    secretKeyRef:
                      name: {{ $.Values.cli.existingSecret }}
                      key: pin
                - name: TWILIO_ACCOUNT_SID
                  valueFrom:
                    secretKeyRef:
                      name: {{ $.Values.cli.existingSecret }}
                      key: twilio-account-sid
                - name: TWILIO_AUTH_TOKEN
                  valueFrom:
                    secretKeyRef:
                      name: {{ $.Values.cli.existingSecret }}
                      key: twilio-auth-token
                - name: TEESNIPER_TO_NUMBER
                  valueFrom:
                    secretKeyRef:
                      name: {{ $.Values.cli.existingSecret }}
                      key: to-number
                - name: TEESNIPER_FROM_NUMBER
                  valueFrom:
                    secretKeyRef:
                      name: {{ $.Values.cli.existingSecret }}
                      key: from-number
                {{- with $entry.env }}
                {{- toYaml . | nindent 16 }}
                {{- end }}
{{- end }}
```

- [ ] **Step 2: Create a test values file with two cronjobs**

```sh
cat > /tmp/cronjob-test.yaml <<'YAML'
cronjobs:
  - name: saturday-morning
    schedule: "0 7 * * 5"
    args:
      - "-b=https://example.com/"
      - "-d=8"
      - "-t=09:00"
      - "-e=11:00"
  - name: sunday-afternoon
    schedule: "0 7 * * 6"
    args:
      - "-b=https://example.com/"
      - "-d=8"
      - "-t=14:00"
      - "-e=16:00"
    image:
      repository: ghcr.io/stebennett/tee-sniper-cli
      tag: "0.2.0"
YAML
```

- [ ] **Step 3: Render and assert**

```sh
helm template testrel charts/tee-sniper-api -f /tmp/cronjob-test.yaml > /tmp/render.yaml
yq 'select(.kind == "CronJob") | .metadata.name' /tmp/render.yaml
yq 'select(.kind == "CronJob" and .metadata.name == "testrel-tee-sniper-api-saturday-morning") | .spec.schedule' /tmp/render.yaml
yq 'select(.kind == "CronJob" and .metadata.name == "testrel-tee-sniper-api-sunday-afternoon") | .spec.jobTemplate.spec.template.spec.containers[0].image' /tmp/render.yaml
yq 'select(.kind == "CronJob" and .metadata.name == "testrel-tee-sniper-api-saturday-morning") | .spec.jobTemplate.spec.template.spec.containers[0].args[0]' /tmp/render.yaml
```

Expected:
```
testrel-tee-sniper-api-saturday-morning
testrel-tee-sniper-api-sunday-afternoon
0 7 * * 5
ghcr.io/stebennett/tee-sniper-cli:0.2.0
--api-url=http://testrel-tee-sniper-api.default.svc.cluster.local
```

- [ ] **Step 4: Validate against schemas**

```sh
helm template testrel charts/tee-sniper-api -f /tmp/cronjob-test.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.27.0 -ignore-missing-schemas
```

Expected: 0 errors.

- [ ] **Step 5: Verify empty `cronjobs: []` renders no CronJob resources**

```sh
helm template testrel charts/tee-sniper-api | yq 'select(.kind == "CronJob") | .metadata.name'
```

Expected: empty output.

- [ ] **Step 6: Commit**

```sh
git add charts/tee-sniper-api/templates/cronjob.yaml
git commit -m "feat(helm): add CronJob template driven by cronjobs values list"
```

---

## Task 5: NetworkPolicy (opt-in)

**Goal:** When enabled, restrict Redis ingress to API pods and API ingress to CronJob pods + a configurable client selector.

**Files:**
- Create: `charts/tee-sniper-api/templates/networkpolicy.yaml`

- [ ] **Step 1: Create `templates/networkpolicy.yaml`**

```yaml
{{- if .Values.networkPolicy.enabled }}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "tee-sniper-api.fullname" . }}-api-ingress
  labels:
    {{- include "tee-sniper-api.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      {{- include "tee-sniper-api.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: api
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              {{- include "tee-sniper-api.selectorLabels" . | nindent 14 }}
              app.kubernetes.io/component: cli
        - podSelector:
            {{- toYaml .Values.networkPolicy.apiAllowedClients | nindent 12 }}
      ports:
        - protocol: TCP
          port: {{ .Values.api.service.targetPort }}
{{- if .Values.redis.enabled }}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "tee-sniper-api.fullname" . }}-redis-ingress
  labels:
    {{- include "tee-sniper-api.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: redis
      app.kubernetes.io/instance: {{ .Release.Name }}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              {{- include "tee-sniper-api.selectorLabels" . | nindent 14 }}
              app.kubernetes.io/component: api
      ports:
        - protocol: TCP
          port: 6379
{{- end }}
{{- end }}
```

- [ ] **Step 2: Verify off by default**

```sh
helm template testrel charts/tee-sniper-api | yq 'select(.kind == "NetworkPolicy") | .metadata.name'
```

Expected: empty output.

- [ ] **Step 3: Verify on with default values**

```sh
helm template testrel charts/tee-sniper-api --set networkPolicy.enabled=true > /tmp/render.yaml
yq 'select(.kind == "NetworkPolicy") | .metadata.name' /tmp/render.yaml
yq 'select(.kind == "NetworkPolicy" and (.metadata.name | test("api-ingress$"))) | .spec.ingress[0].from[1].podSelector.matchLabels' /tmp/render.yaml
```

Expected:
```
testrel-tee-sniper-api-api-ingress
testrel-tee-sniper-api-redis-ingress
tee-sniper.io/api-client: "true"
```

- [ ] **Step 4: Verify custom apiAllowedClients selector takes effect**

```sh
helm template testrel charts/tee-sniper-api \
  --set networkPolicy.enabled=true \
  --set networkPolicy.apiAllowedClients.matchLabels.team=platform \
  | yq 'select(.kind == "NetworkPolicy" and (.metadata.name | test("api-ingress$"))) | .spec.ingress[0].from[1].podSelector.matchLabels'
```

Expected:
```
team: platform
```

- [ ] **Step 5: kubeconform pass**

```sh
helm template testrel charts/tee-sniper-api --set networkPolicy.enabled=true | \
  kubeconform -strict -summary -kubernetes-version 1.27.0 -ignore-missing-schemas
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```sh
git add charts/tee-sniper-api/templates/networkpolicy.yaml
git commit -m "feat(helm): add opt-in NetworkPolicy with configurable client selector"
```

---

## Task 6: Environment value files

**Goal:** Two ready-to-use overlay files for dev and prod.

**Files:**
- Create: `charts/tee-sniper-api/values-dev.yaml`
- Create: `charts/tee-sniper-api/values-prod.yaml`

- [ ] **Step 1: Create `charts/tee-sniper-api/values-dev.yaml`**

```yaml
api:
  replicas: 1
  resources:
    requests:
      memory: 64Mi
      cpu: 50m
    limits:
      memory: 128Mi
      cpu: 250m
  config:
    logLevel: DEBUG

cronjobs: []

redis:
  master:
    persistence:
      size: 256Mi

networkPolicy:
  enabled: false
```

- [ ] **Step 2: Create `charts/tee-sniper-api/values-prod.yaml`**

```yaml
api:
  replicas: 2
  config:
    logLevel: INFO

cronjobs:
  - name: example-saturday
    schedule: "0 7 * * 5"
    args:
      - "-b=https://CHANGE-ME.example.com/"
      - "-d=8"
      - "-t=09:00"
      - "-e=11:00"
    suspend: true

networkPolicy:
  enabled: true
  apiAllowedClients:
    matchLabels:
      tee-sniper.io/api-client: "true"
```

> The example cronjob ships with `suspend: true` so an unconfigured prod install does not start firing booking attempts. Operators replace the URL and remove `suspend: true` per their needs.

- [ ] **Step 3: Render both and validate**

```sh
helm template testrel charts/tee-sniper-api -f charts/tee-sniper-api/values-dev.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.27.0 -ignore-missing-schemas
helm template testrel charts/tee-sniper-api -f charts/tee-sniper-api/values-prod.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.27.0 -ignore-missing-schemas
```

Expected: both report 0 errors.

- [ ] **Step 4: Assert prod has 2 replicas and 1 cronjob, dev has 1 replica and 0 cronjobs**

```sh
helm template testrel charts/tee-sniper-api -f charts/tee-sniper-api/values-prod.yaml | \
  yq 'select(.kind == "Deployment") | .spec.replicas'
helm template testrel charts/tee-sniper-api -f charts/tee-sniper-api/values-prod.yaml | \
  yq '[. | select(.kind == "CronJob")] | length' | head -1
helm template testrel charts/tee-sniper-api -f charts/tee-sniper-api/values-dev.yaml | \
  yq 'select(.kind == "Deployment") | .spec.replicas'
helm template testrel charts/tee-sniper-api -f charts/tee-sniper-api/values-dev.yaml | \
  yq '[. | select(.kind == "CronJob")] | length' | head -1
```

Expected:
```
2
1
1
0
```

- [ ] **Step 5: Commit**

```sh
git add charts/tee-sniper-api/values-dev.yaml charts/tee-sniper-api/values-prod.yaml
git commit -m "feat(helm): add dev and prod value overlays"
```

---

## Task 7: Chart README

**Goal:** A single doc that walks an operator from zero to a deployed chart.

**Files:**
- Create: `charts/tee-sniper-api/README.md`

- [ ] **Step 1: Create `charts/tee-sniper-api/README.md`**

```markdown
# tee-sniper-api Helm chart

Deploys the tee-sniper FastAPI service plus Redis to a Kubernetes cluster, and runs `tee-sniper-cli` as a configurable list of CronJobs.

## Prerequisites

- Kubernetes 1.27+ (tested on k3s)
- Helm 3.14+
- A storage class for Redis persistence (k3s default: `local-path`)
- The Bitnami chart repository: `helm repo add bitnami https://charts.bitnami.com/bitnami`
- Required Secrets created in the target namespace (see below)

## Secret contract

The chart never creates Secrets. Three Secrets must exist before installing:

| Secret (default name) | Required keys                                                                                                          |
|-----------------------|------------------------------------------------------------------------------------------------------------------------|
| `tee-sniper-api`      | `shared-secret`                                                                                                        |
| `tee-sniper-cli`      | `username`, `pin`, `twilio-account-sid`, `twilio-auth-token`, `to-number`, `from-number`, `shared-secret`              |
| `redis-auth`          | `password`                                                                                                             |

Names are configurable via `api.existingSecret`, `cli.existingSecret`, `redis.auth.existingSecret`.

Manual creation example (typically the 1Password operator handles this):
```sh
kubectl -n tee-sniper create secret generic tee-sniper-api --from-literal=shared-secret=...
kubectl -n tee-sniper create secret generic tee-sniper-cli \
  --from-literal=username=... \
  --from-literal=pin=... \
  --from-literal=twilio-account-sid=... \
  --from-literal=twilio-auth-token=... \
  --from-literal=to-number=... \
  --from-literal=from-number=... \
  --from-literal=shared-secret=...
kubectl -n tee-sniper create secret generic redis-auth --from-literal=password=...
```

## Install

```sh
helm dep update charts/tee-sniper-api
kubectl create namespace tee-sniper
# Create secrets per the table above
helm upgrade --install tee-sniper charts/tee-sniper-api \
  -n tee-sniper \
  -f charts/tee-sniper-api/values-prod.yaml
```

## Upgrade

Application image versions are driven by `appVersion` in `Chart.yaml`. To bump:

1. Edit `Chart.yaml` and set `appVersion: "X.Y.Z"`.
2. Bump chart `version:` (semver — patch for value-only changes, minor for template changes).
3. `helm dep update charts/tee-sniper-api` (only if dependencies changed).
4. `helm upgrade tee-sniper charts/tee-sniper-api -n tee-sniper -f charts/tee-sniper-api/values-prod.yaml`.

To pin a different image tag without changing `appVersion`, set `api.image.tag` and/or `cli.image.tag` in your values file. `latest` is rejected by schema validation.

## Adding a new scheduled booking

Append an entry to `cronjobs:` in your values file:

```yaml
cronjobs:
  - name: friday-evening
    schedule: "0 7 * * 4"
    args:
      - "-b=https://golf.example.com/"
      - "-d=8"
      - "-t=17:00"
      - "-e=19:00"
      - "-s=partner1,partner2"
```

`name` must be DNS-label-compliant (lowercase, digits, hyphens). Re-run `helm upgrade` to apply.

## Granting another in-cluster workload access to the API

The API is `ClusterIP` only. With `networkPolicy.enabled: true`, only the chart's own CronJobs can reach it by default. Other workloads opt in by labelling their pods to match `networkPolicy.apiAllowedClients`:

```yaml
# In another workload's pod spec
metadata:
  labels:
    tee-sniper.io/api-client: "true"
```

Or change the selector in your values file:

```yaml
networkPolicy:
  apiAllowedClients:
    matchLabels:
      team: platform
```

## Troubleshooting

| Symptom                                         | Diagnosis                                                                                  |
|-------------------------------------------------|--------------------------------------------------------------------------------------------|
| API pod stuck in `CreateContainerConfigError`   | A referenced Secret is missing. `kubectl -n tee-sniper describe pod <name>` shows which.   |
| API readiness probe failing                     | Redis unreachable or wrong password. `kubectl logs deploy/tee-sniper-tee-sniper-api`.      |
| `helm install` fails with schema error          | Check `tag` is not `"latest"` and `logLevel` is one of DEBUG/INFO/WARNING/ERROR.            |
| CronJob runs but exits non-zero                 | API call failed. `kubectl logs job/<jobname> -n tee-sniper`. No automatic retry — by design.|
| Other in-cluster service can't reach API        | Add the `networkPolicy.apiAllowedClients` label to its pods.                               |

## Local smoke test (k3s/kind)

```sh
# kind cluster
kind create cluster
helm dep update charts/tee-sniper-api
kubectl create namespace tee-sniper
kubectl -n tee-sniper create secret generic tee-sniper-api --from-literal=shared-secret=test
kubectl -n tee-sniper create secret generic tee-sniper-cli \
  --from-literal=username=u --from-literal=pin=p \
  --from-literal=twilio-account-sid=AC --from-literal=twilio-auth-token=t \
  --from-literal=to-number=+1 --from-literal=from-number=+1 \
  --from-literal=shared-secret=test
kubectl -n tee-sniper create secret generic redis-auth --from-literal=password=devpass
helm install tee-sniper charts/tee-sniper-api -n tee-sniper \
  -f charts/tee-sniper-api/values-dev.yaml \
  --set redis.master.persistence.storageClass=standard
kubectl -n tee-sniper get pods -w
```
```

- [ ] **Step 2: Commit**

```sh
git add charts/tee-sniper-api/README.md
git commit -m "docs(helm): add chart README with install, upgrade, and troubleshooting"
```

---

## Task 8: CI workflow for chart linting and validation

**Goal:** Every PR touching `charts/` runs `helm lint`, renders both value overlays, and runs `kubeconform`.

**Files:**
- Create: `.github/workflows/helm-chart.yml`

- [ ] **Step 1: Create `.github/workflows/helm-chart.yml`**

```yaml
name: Helm Chart

on:
  push:
    branches: [ main ]
    paths:
      - 'charts/**'
      - '.github/workflows/helm-chart.yml'
  pull_request:
    branches: [ main ]
    paths:
      - 'charts/**'
      - '.github/workflows/helm-chart.yml'

jobs:
  lint-and-validate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Set up Helm
        uses: azure/setup-helm@v4
        with:
          version: v3.14.4

      - name: Add Bitnami repo
        run: helm repo add bitnami https://charts.bitnami.com/bitnami && helm repo update

      - name: Helm dependency update
        run: helm dep update charts/tee-sniper-api

      - name: Helm lint
        run: helm lint charts/tee-sniper-api

      - name: Install kubeconform
        run: |
          curl -sSL -o /tmp/kubeconform.tgz \
            https://github.com/yannh/kubeconform/releases/download/v0.6.7/kubeconform-linux-amd64.tar.gz
          tar -xzf /tmp/kubeconform.tgz -C /tmp
          sudo mv /tmp/kubeconform /usr/local/bin/

      - name: Validate dev values
        run: |
          helm template testrel charts/tee-sniper-api \
            -f charts/tee-sniper-api/values-dev.yaml \
            | kubeconform -strict -summary -kubernetes-version 1.27.0 -ignore-missing-schemas

      - name: Validate prod values
        run: |
          helm template testrel charts/tee-sniper-api \
            -f charts/tee-sniper-api/values-prod.yaml \
            | kubeconform -strict -summary -kubernetes-version 1.27.0 -ignore-missing-schemas

      - name: Schema rejects tag=latest
        run: |
          if helm template testrel charts/tee-sniper-api --set api.image.tag=latest > /dev/null 2>&1; then
            echo "FAIL: schema should have rejected tag=latest"
            exit 1
          fi
          echo "OK: schema rejected tag=latest"
```

- [ ] **Step 2: Verify the workflow file is valid YAML**

```sh
yq '.jobs."lint-and-validate".steps | length' .github/workflows/helm-chart.yml
```

Expected: a number (count of steps), not an error.

- [ ] **Step 3: Commit**

```sh
git add .github/workflows/helm-chart.yml
git commit -m "ci: add Helm chart lint and kubeconform validation workflow"
```

- [ ] **Step 4: Push and observe CI**

```sh
git push
```

Expected: GitHub Actions shows a passing `Helm Chart / lint-and-validate` job on the PR (or main, depending on branch).

---

## Done

When all tasks above are merged:
- `charts/tee-sniper-api/` is a complete, lint-clean chart deployable to k3s.
- Adding a new booking schedule is a one-line values change.
- CI rejects malformed values, `latest` tags, and invalid manifests.
- The README walks a fresh operator from zero to a running deployment.

Issue #28 (Phase 7 of Epic #30) can be closed referencing this work.
