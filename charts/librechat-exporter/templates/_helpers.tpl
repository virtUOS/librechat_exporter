{{/* Expand the name of the chart. */}}
{{- define "librechat-exporter.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Create a fully qualified app name. */}}
{{- define "librechat-exporter.fullname" -}}
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

{{/* Chart name and version label. */}}
{{- define "librechat-exporter.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Common labels. */}}
{{- define "librechat-exporter.labels" -}}
helm.sh/chart: {{ include "librechat-exporter.chart" . }}
{{ include "librechat-exporter.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* Selector labels. */}}
{{- define "librechat-exporter.selectorLabels" -}}
app.kubernetes.io/name: {{ include "librechat-exporter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Service account name. */}}
{{- define "librechat-exporter.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "librechat-exporter.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/* Name of the Secret holding the MongoDB URI. */}}
{{- define "librechat-exporter.mongodbSecretName" -}}
{{- if .Values.mongodb.existingSecret }}
{{- .Values.mongodb.existingSecret }}
{{- else }}
{{- include "librechat-exporter.fullname" . }}
{{- end }}
{{- end }}

{{/* Key within the MongoDB Secret. */}}
{{- define "librechat-exporter.mongodbSecretKey" -}}
{{- if .Values.mongodb.existingSecret }}
{{- .Values.mongodb.existingSecretKey }}
{{- else }}
{{- "mongodb-uri" }}
{{- end }}
{{- end }}
