# DIL Grafana deployment

Argo CD Helm chart and optional local test deployment for Grafana with the DIL
datasource and dashboard-sharing plugins. Uses the official, unmodified Grafana
image (13.0.1 by default). Both plugins are downloaded from the published
`DIL-Grafana-Plugin-source` release during Grafana startup.

## Prepare

1. The default values install datasource version 0.3.0 and dashboard app version
   0.1.0 from the published HTTPS release. Keep these URLs pinned to reviewed
   artifacts when upgrading. The chart uses Grafana's synchronous plugin
   preinstall setting and provisions the dashboard app for organization 1.
2. Push this folder to `Data-Space-Lab/DIL-Grafana-deployment` (or change repoURL
   in `argocd-application.yaml` to your repository).
3. Select the target tenant's kubectl context and create its namespace/secret:

```bash
kubectl create namespace dil-grafana
read -rs -p 'Grafana admin password: ' ADMIN_PASSWORD
read -rs -p 'Consumer GRAFANA_CLIENT_TOKEN: ' CONNECTOR_TOKEN
kubectl -n dil-grafana create secret generic dil-grafana-credentials \
  --from-literal=admin-user=admin \
  --from-literal=admin-password="$ADMIN_PASSWORD" \
  --from-literal=connector-token="$CONNECTOR_TOKEN"
unset ADMIN_PASSWORD CONNECTOR_TOKEN
```

The connector-token Secret key must match `GRAFANA_CLIENT_TOKEN` on the consumer
dataplane container. Prefer External Secrets/your secret manager for routine
operations; the command above exposes values briefly in process arguments.
Never commit plaintext secret manifests. If the image is private, create a GHCR
pull secret in this namespace and set `imagePullSecrets: [{name: ghcr-pull}]`.

## Values

The Grafana image version and independent plugin package versions are in
`values.yaml`.
Set a real HTTPS
`grafana.rootUrl`. Leave datasource.enabled=false to configure in Grafana's UI,
or enable it and supply connectorUrl, agreementId, datasetId, offerId and
dashboardId. Secret token values are injected at runtime into secure datasource
provisioning. The retained setting name `connectorUrl` points to the consumer
dataplane, not its connector DSP or management API. Use one datasource per
finalized agreement/dashboard and start a `grafana-query` transfer first.
Configure the connector/dataplane private authorization link as described in
`DIL-Connector-source/Dataplane/GRAFANA-INTEGRATION.md`; this chart only deploys Grafana.

The chart enables a 5Gi PVC, non-root execution, resource limits and health
probes. Grafana installs both ZIPs into its plugin directory on the data PVC and
provisions the dashboard app through `/etc/grafana/provisioning/plugins`.
PVC pruning/deletion is disabled to
preserve local dashboards. The admin password environment variable initializes
new Grafana databases; changing the Secret does not reset an existing account.

The two local plugins are unsigned release artifacts, so both IDs are allowed by
default. After installing signed artifacts, set `grafana.allowUnsignedPlugin=false`
and remove the corresponding IDs from `grafana.allowUnsignedPlugins`. Do not
install untrusted unsigned plugins.

## Argo CD

```bash
helm lint .
helm template dil-grafana . --namespace dil-grafana
kubectl apply -f argocd-application.yaml
```

Sync the `dil-grafana` application in the tenant's Argo CD. It targets that
cluster's `https://kubernetes.default.svc`, not the host cluster. Set up an
Ingress with ingress.enabled or use your existing Envoy RouteManagementUI to
route the public Grafana hostname to service `dil-grafana`, namespace
`dil-grafana`, port 3000. No public route or Keycloak client is created
automatically. Configure Grafana OIDC separately using your tenant's policy.

For an initial check without a public route:

```bash
kubectl -n dil-grafana rollout status deployment/dil-grafana
kubectl -n dil-grafana port-forward svc/dil-grafana 13000:3000
```

Open http://127.0.0.1:13000. Installation into an existing Grafana is also
supported using the plugin artifact; this chart is for a separate instance.

## Local integration test

Build/export the plugin first, then:

```bash
cd /home/vmuser/DIL-Grafana-Plugin-source
docker build --output type=local,dest=artifacts .
cd /home/vmuser/DIL-Grafana-deployment
docker compose up -d
```

This mounts the extracted plugin into official Grafana 13.0.1 at
http://127.0.0.1:13000. Login: `admin` / `local-demo-only`. The `DIL local fixture`
datasource uses synthetic data, not a real agreement or DCP exchange.
Never deploy the fixture or its credentials into a tenant.

`dev/browser_test.py` uses Playwright to test dashboard import and desktop/mobile
rendering. It accepts `GRAFANA_TEST_URL`. Test another Grafana release with
`GRAFANA_VERSION=13.2.0 docker compose up -d --force-recreate`.
Use `docker compose down` to remove the disposable environment. No production
Grafana data is mounted. The initial architecture proposal is preserved in
`docs/Architecture.md`.
