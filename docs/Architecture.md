Original architecture proposal:
1. Provider keeps Grafana, data sources, credentials, and raw data.
2. Provider publishes a dashboard definition containing panels and query models—not data.
3. Consumer imports that dashboard into its Grafana.
4. The consumer-side DIL Grafana plugin sends authorized queries to the provider through DIL.
5. Provider validates the contract and returns Grafana data frames for visualization.
Grafana supports backend data-source plugins through QueryData, and these plugins can perform server-side authentication and resource calls. This is also the appropriate architecture for externally shared dashboards. Grafana backend data-source plugins, backend plugin capabilities, externally shared dashboards
One important distinction: the data would remain provider-owned and provider-stored, but query results would still temporarily travel to the consumer Grafana for rendering. The provider must therefore enforce:
- DIL contract and membership authorization
- Query allowlists and dataset permissions
- Time-range, row-count, and rate limits
- Short-lived access tokens
- Query and data-transfer audit logging
- No provider Grafana credentials inside dashboard JSON
There are two possible implementations:
- Simpler: share a link or embedded view to the provider’s Grafana. The consumer does not receive a separate dashboard copy.
- More integrated: import the dashboard into the consumer Grafana and use a DIL backend data-source plugin to execute queries remotely. This is probably what you want.
For an MVP, I would implement:
- A dashboard manifest containing panel definitions and query templates
- A provider-side DIL query endpoint
- A consumer Grafana backend data-source plugin
- Contract-based authorization for each dashboard/dataset
- “Import shared dashboard” functionality
- Audit records for dashboard views and queries
This is a medium-sized integration rather than a small panel plugin, because the connector needs a query-oriented API. The existing DIL transfer flow is not ideal for interactive Grafana queries; a dedicated, restricted query service would be safer and faster.


9:24 AM








It would need to be grafana dataplane implementation. Could you make a implementation requirement specification for data-plane extension for this and for the grafana plugin that allow integrated query excution and data exchange







9:29 AM






Worked for 42s



DIL Grafana Data-Plane Extension
Implementation Requirements Specification
1. Objective
Implement a DIL data-plane extension and Grafana plugin that allow a dashboard hosted in one Grafana instance to be used by another Grafana instance while:
- Data remains stored at the provider.
- Provider Grafana credentials are never exposed.
- Queries are authorized through a DIL agreement.
- Query execution occurs on the provider side.
- Only authorized query results are returned to the consumer Grafana.
- All access is auditable.
The solution should use a Grafana backend data-source plugin implementing QueryData, which is Grafana’s standard mechanism for backend query execution and returning data frames. Grafana backend data-source plugins
2. Proposed architecture
Consumer Grafana
  └── DIL Grafana data-source plugin
        └── Consumer DIL Connector
              └── DIL data-plane query request
                    └── Provider DIL Connector
                          └── Provider Grafana adapter
                                └── Provider data source / database
The provider’s Grafana instance must not be directly exposed to the consumer.
The consumer receives only:
- Dashboard metadata
- Panel configuration
- Query templates
- Query results
The consumer must not receive:
- Provider datasource credentials
- Provider Grafana API credentials
- Arbitrary provider Grafana API access
- Unrestricted database queries
- Unapproved dashboards or datasets
3. DIL data-plane requirements
3.1 Capability discovery
The provider connector must advertise a Grafana query capability, for example:
{
  "type": "dil:grafana-query",
  "version": "1.0",
  "features": [
    "dashboard-manifest",
    "time-range-query",
    "multi-query",
    "variables"
  ],
  "supportedFormats": [
    "grafana-dataframe-json"
  ]
}
The capability should identify:
- Supported protocol version
- Supported Grafana datasource types
- Maximum time range
- Maximum data points
- Maximum response size
- Whether streaming is supported
- Whether dashboard variables are supported
- Whether annotations are supported
The provider must not advertise a datasource type unless it can execute and authorize that query type.
3.2 Agreement requirements
Every query must reference an existing finalized DIL agreement:
{
  "agreementId": "agreement-123",
  "offerId": "offer-456",
  "datasetId": "dataset-789",
  "dataspaceId": "gxdch"
}
The connector must reject queries when:
- The agreement does not exist.
- The agreement is not finalized.
- The agreement has expired.
- The agreement has been revoked.
- The dataset or dashboard is not included in the agreement.
- The requesting participant is not the agreement participant.
Query execution must not trigger a new contract negotiation. Contract negotiation belongs to the control plane; query execution belongs to the data plane.
3.3 Query endpoint
The provider connector should expose a protected endpoint similar to:
POST /api/dsp/data-plane/grafana/query
The endpoint must be authenticated using the existing DIL connector identity and authorization mechanisms.
Example request:
{
  "protocolVersion": "1.0",
  "requestId": "8d81f6f0-8be8-4f19-b5c4-b1a8d997d40a",
  "agreementId": "agreement-123",
  "offerId": "offer-456",
  "datasetId": "dataset-789",
  "dataspaceId": "gxdch",
  "dashboardId": "dashboard-001",
  "panelId": "panel-004",
  "timeRange": {
    "from": "2026-09-25T00:00:00Z",
    "to": "2026-09-25T12:00:00Z"
  },
  "variables": {
    "site": "Oulu"
  },
  "queries": [
    {
      "refId": "A",
      "datasourceType": "prometheus",
      "queryModelVersion": "1.0",
      "model": {
        "expr": "temperature_celsius",
        "legendFormat": "{{device}}"
      }
    }
  ],
  "maxDataPoints": 2000,
  "intervalMs": 15000
}
The request must include a unique requestId for tracing and replay protection.
3.4 Query response
The provider connector should return Grafana-compatible data frames:
{
  "protocolVersion": "1.0",
  "requestId": "8d81f6f0-8be8-4f19-b5c4-b1a8d997d40a",
  "status": "ok",
  "dataFrames": [
    {
      "refId": "A",
      "name": "temperature",
      "schema": {
        "name": "temperature",
        "fields": [
          {
            "name": "time",
            "type": "time"
          },
          {
            "name": "value",
            "type": "number"
          }
        ]
      },
      "data": {
        "values": [
          ["2026-09-25T10:00:00Z"],
          [21.4]
        ]
      }
    }
  ],
  "warnings": [],
  "statistics": {
    "durationMs": 245,
    "rows": 1,
    "bytes": 512
  }
}
Errors must be normalized:
{
  "status": "error",
  "error": {
    "code": "QUERY_NOT_AUTHORIZED",
    "message": "The agreement does not permit access to this panel",
    "retryable": false
  }
}
The provider must not return database credentials, internal URLs, SQL errors containing secrets, or unrestricted datasource metadata.
3.5 Provider-side query execution
The provider data plane should support an adapter interface:
GrafanaQueryAdapter
  - validate_query()
  - authorize_query()
  - execute_query()
  - convert_to_grafana_frames()
Two implementation modes are possible:
Preferred long-term mode
The data-plane adapter queries the provider’s native data service directly.
Advantages:
- Better security control
- Better performance
- No dependency on provider Grafana API internals
- Easier query auditing
- Easier data-source-specific authorization
Practical initial mode
The adapter calls the provider Grafana HTTP API internally, for example /api/ds/query, using a provider-side service account.
This mode requires:
- Datasource UID allowlists
- Dashboard and panel allowlists
- Query model validation
- Query timeout enforcement
- No exposure of the Grafana API to the consumer
- A dedicated least-privilege Grafana service account
Grafana datasource query models are not universally portable. The dashboard manifest must therefore specify the datasource type and query-model version. The initial implementation should support a limited set of datasource types rather than claim universal compatibility.
3.6 Security requirements
The data plane must:
- Validate the caller’s connector identity.
- Validate the DIL agreement.
- Validate the requested dataset and dashboard.
- Validate the panel and query model.
- Enforce provider-defined query policies.
- Enforce time-range limits.
- Enforce maximum data points and response size.
- Enforce concurrency limits.
- Apply request timeouts.
- Reject replayed requests where applicable.
- Avoid logging tokens, credentials, or complete sensitive queries.
- Use TLS for all connector communication.
- Use short-lived authorization tokens or connector-to-connector authentication.
- Never require the consumer to know provider Grafana credentials.
The provider should support query policy fields such as:
{
  "allowedDashboards": ["dashboard-001"],
  "allowedPanels": ["panel-004", "panel-005"],
  "allowedTimeRange": "90d",
  "maxDataPoints": 10000,
  "maxResponseBytes": 10485760,
  "refreshIntervalSeconds": 30
}
3.7 Audit requirements
Every query must generate an audit event containing:
- Request ID
- Agreement ID
- Consumer participant DID
- Provider participant DID
- Dashboard ID
- Panel ID
- Dataset ID
- Query hash
- Query start and completion time
- Source connector address
- Response status
- Number of returned rows or points
- Response size
- Duration
- Failure reason, if applicable
Raw credentials and sensitive query values must not be stored in logs.
The existing connector audit framework can be extended with an event type such as:
grafana.query.requested
grafana.query.completed
grafana.query.rejected
grafana.query.failed
3.8 Performance requirements
Initial synchronous-query requirements:
- Default query timeout: 10 seconds
- Configurable maximum timeout: 30 seconds
- Connection pooling between connectors
- Maximum concurrent queries per agreement
- Provider-side response caching where permitted
- Request cancellation when the Grafana request is cancelled
- Response size limit
- Query deduplication for identical dashboard refreshes
For queries exceeding the synchronous timeout, a future version may provide:
POST /api/dsp/data-plane/grafana/query-jobs
GET  /api/dsp/data-plane/grafana/query-jobs/{jobId}
Streaming should not be required for the first version.
4. Shared dashboard manifest
A shared dashboard must contain configuration, not data.
Example:
{
  "manifestVersion": "1.0",
  "dashboardId": "dashboard-001",
  "title": "Industrial Temperature",
  "providerDid": "did:web:provider.example",
  "datasetId": "dataset-789",
  "offerId": "offer-456",
  "datasource": {
    "type": "dil-grafana",
    "logicalId": "provider-telemetry"
  },
  "variables": [
    {
      "name": "site",
      "type": "constant",
      "allowedValues": ["Oulu", "Helsinki"]
    }
  ],
  "panels": [
    {
      "id": "panel-004",
      "title": "Temperature",
      "type": "timeseries",
      "query": {
        "datasourceType": "prometheus",
        "model": {
          "expr": "temperature_celsius",
          "legendFormat": "{{device}}"
        }
      }
    }
  ]
}
The manifest must not contain:
- Historical data
- Provider Grafana tokens
- Database passwords
- Provider datasource credentials
- Unrestricted arbitrary query endpoints
Grafana supports dashboard templates and datasource placeholders, which can be used for this import model. Grafana dashboard templates
5. Grafana plugin requirements
5.1 Plugin type
The primary plugin must be a Grafana backend data-source plugin:
DIL Grafana Data Source
It should use Grafana’s DataSourceWithBackend model, with backend support for:
- QueryData
- CheckHealth
- CallResource
- Secure configuration
- Optional streaming in a later release
The backend plugin must call the consumer’s DIL connector rather than calling the provider Grafana directly.
5.2 Datasource configuration
The plugin configuration should include:
- Consumer connector URL
- Dataspace identifier
- Provider participant DID
- Agreement ID
- Offer ID
- Dataset ID
- Optional dashboard ID
- TLS configuration
- Secure connector authentication configuration
Sensitive configuration must use Grafana’s secure JSON fields and must not appear in exported dashboard JSON.
5.3 Query execution
For every Grafana query, the plugin backend must:
1. Receive Grafana’s DataQueryRequest.
2. Add the dashboard time range.
3. Add maxDataPoints and intervalMs.
4. Add the agreement and dataset identifiers.
5. Generate a request ID.
6. Send the request to the consumer DIL connector.
7. Convert the response into Grafana data frames.
8. Map DIL errors into Grafana errors.
9. Preserve warnings and query statistics.
The browser must not call the provider connector directly.
5.4 Plugin query editor
The query editor should provide:
- Provider and dataset selection
- Offer/agreement selection
- Dashboard and panel binding
- Datasource type selection
- Query-model editor
- Query preview
- Variable selection
- Time-range controls
- Maximum data-point configuration
For the initial implementation, a JSON query-model editor may be acceptable. Datasource-specific editors can be added later.
5.5 Dashboard import
A separate Grafana app plugin or companion UI should provide:
- “Import shared dashboard”
- Provider and dataspace selection
- Agreement selection
- Dashboard manifest retrieval
- Local datasource UID mapping
- Variable configuration
- Permission validation
- Dashboard refresh
- Re-import or update handling
A data-source plugin alone does not provide a complete dashboard-sharing user experience. The import and manifest management should therefore be implemented as a small companion app plugin or GUI module.
6. Data exchange lifecycle
1. Provider publishes dashboard/query offer
2. Consumer discovers offer
3. Consumer requests DIL agreement
4. Agreement is finalized
5. Consumer imports dashboard manifest
6. Consumer Grafana panel invokes QueryData
7. Plugin sends query through consumer connector
8. Provider connector validates agreement and policy
9. Provider adapter executes query locally
10. Provider returns Grafana data frames
11. Consumer Grafana renders the result
12. Both connectors persist audit events
Dashboard refreshes must not renegotiate the contract.
7. Functional acceptance criteria
The implementation is acceptable when:
1. A provider can publish a dashboard manifest without publishing data.
2. A consumer can discover and import the dashboard after agreement finalization.
3. The consumer Grafana can render a provider panel.
4. Provider datasource credentials never leave the provider.
5. Provider Grafana is not externally exposed.
6. Queries execute on the provider side.
7. Revoking the DIL agreement immediately prevents new queries.
8. Unauthorized panels and datasets are rejected.
9. Provider outages produce a clear Grafana error.
10. Queries are visible in provider audit logs.
11. Query responses are converted into native Grafana data frames.
12. Multiple panels can refresh concurrently within configured limits.
8. Recommended implementation phases
Phase 1: Minimal query path
- Define query and response schemas.
- Add provider-side query endpoint.
- Add one provider adapter.
- Add connector authorization.
- Implement Grafana backend QueryData.
- Return Grafana JSON data frames.
- Add audit events.
Phase 2: Dashboard sharing
- Implement dashboard manifest.
- Add dashboard import app.
- Add dataset, offer, and agreement mapping.
- Add variable support.
- Add provider dashboard/panel allowlists.
Phase 3: Production features
- Query caching
- Streaming or asynchronous jobs
- Arrow response format
- Annotations
- Alerts
- Query cost policies
- Administrative usage statistics
- Provider-side query approval workflows
The key design decision is that the DIL data plane must expose a restricted, agreement-aware query service. The Grafana plugin should act as the consumer-side adapter, while the provider connector remains responsible for authorization, local query execution, and data governance.
