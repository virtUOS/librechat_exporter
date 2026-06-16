# librechat-exporter Helm chart

Deploys the [LibreChat Prometheus exporter](https://github.com/virtUOS/librechat_exporter)
to Kubernetes: a single Deployment that reads metrics from MongoDB and exposes
them on port `8000` at `/metrics`.

## Installing

```sh
helm install librechat-exporter ./charts/librechat-exporter \
  --set mongodb.uri="mongodb://my-mongo:27017/"
```

By default the chart creates a Secret holding the MongoDB URI. To reference an
existing Secret instead:

```sh
helm install librechat-exporter ./charts/librechat-exporter \
  --set mongodb.existingSecret=my-secret \
  --set mongodb.existingSecretKey=mongodb-uri
```

## Prometheus scraping

The chart always creates a `Service`. To have the Prometheus Operator scrape it,
enable the `ServiceMonitor` (requires the `monitoring.coreos.com` CRDs):

```sh
helm install librechat-exporter ./charts/librechat-exporter \
  --set serviceMonitor.enabled=true
```

Without the operator, scrape the Service directly or add
`prometheus.io/scrape` annotations via `service.annotations`.

## Configuration

The exporter is configured entirely through environment variables. Set them via
the `env` map (simple values) or `extraEnv` (raw entries with `valueFrom`).

| Key | Default | Description |
| --- | --- | --- |
| `replicaCount` | `1` | Number of exporter replicas |
| `image.repository` | `ghcr.io/virtuos/librechat_exporter` | Image repository |
| `image.tag` | `""` (chart `appVersion`) | Image tag |
| `image.pullPolicy` | `IfNotPresent` | Image pull policy |
| `imagePullSecrets` | `[]` | Image pull secrets |
| `mongodb.uri` | `mongodb://mongodb:27017/` | MongoDB URI (used when `existingSecret` is empty) |
| `mongodb.existingSecret` | `""` | Existing Secret holding the MongoDB URI |
| `mongodb.existingSecretKey` | `mongodb-uri` | Key within `existingSecret` |
| `env` | `{}` | Extra env vars as a name/value map (e.g. `METRICS_TIMEZONE`, `LOGGING_LEVEL`, `ENABLE_*`, `LIBRECHAT_URL`) |
| `extraEnv` | `[]` | Extra env vars as raw entries (`valueFrom`, etc.) |
| `service.type` | `ClusterIP` | Service type |
| `service.port` | `8000` | Service port |
| `service.annotations` | `{}` | Service annotations |
| `serviceMonitor.enabled` | `false` | Create a Prometheus Operator ServiceMonitor |
| `serviceMonitor.interval` | `60s` | Scrape interval |
| `serviceMonitor.scrapeTimeout` | `""` | Scrape timeout |
| `serviceMonitor.labels` | `{}` | Extra ServiceMonitor labels (e.g. to match a Prometheus release) |
| `serviceMonitor.honorLabels` | `false` | Honor labels on scrape |
| `serviceMonitor.relabelings` | `[]` | Endpoint relabelings |
| `serviceMonitor.metricRelabelings` | `[]` | Metric relabelings |
| `serviceAccount.create` | `true` | Create a ServiceAccount |
| `serviceAccount.name` | `""` | ServiceAccount name (generated when empty) |
| `serviceAccount.annotations` | `{}` | ServiceAccount annotations |
| `livenessProbe` / `readinessProbe` | `httpGet /metrics` | Probe configuration |
| `resources` | `{}` | Container resource requests/limits |
| `podAnnotations` / `podLabels` | `{}` | Extra pod metadata |
| `podSecurityContext` / `securityContext` | `{}` | Security contexts |
| `nodeSelector` / `tolerations` / `affinity` | `{}` / `[]` / `{}` | Scheduling controls |

See the exporter's main [README](../../README.md) for the full list of supported
environment variables.
