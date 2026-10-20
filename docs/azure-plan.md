# Azure plan - PS07 Vegetation Change Monitor

Status: **design only**. Nothing here has been deployed; no Azure account was used.

## Architecture

```
Analyst browser --HTTPS--> Azure App Service (Linux, container: this repo's Dockerfile)
                                   |  managed identity (RBAC)
                                   v
                       Blob Storage account
                         - inputs/   uploaded .npz scenes (two dates + masks)
                         - results/  results.json, change.csv, change.png
                                   |
                       Application Insights + Log Analytics (logs, metrics, alerts)
```

The current code analyses an uploaded `.npz` in memory (limit 5 MB) and returns results. Persisting
to Blob Storage is the planned extension; it is *not implemented* in this repository.

## Choices

| Concern | Choice | Why |
|---|---|---|
| Compute | App Service Linux, B1 (dev/test) or P0v3 (prod), container deploy | Stateless FastAPI app, small arrays, no GPU. Simplest operational model. |
| Larger scenes | Later: Azure Container Apps job or Functions reading from Blob | Real scenes (thousands of pixels square) should run as a batch job, not in a request. |
| Storage | Standard LRS StorageV2 account, private containers, soft delete on | Cheap, durable enough for derived products; source imagery can be re-fetched. |
| Registry | Azure Container Registry (Basic) | Hosts the image built by GitHub Actions. |

## Identity and secrets

- GitHub Actions authenticates to Azure with **OIDC federated credentials** on an Entra app registration
  (no client secret stored in GitHub). Repository variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
  `AZURE_SUBSCRIPTION_ID`.
- The App Service has a **system-assigned managed identity** with `Storage Blob Data Contributor` on the
  storage account only, and `AcrPull` on the registry. No connection strings or keys in app settings.
- Storage account: public blob access disabled, TLS 1.2 minimum, shared-key access disabled.
- The app handles no personal data. Farm boundaries can be sensitive, so containers stay private.

## Monitoring

- Application Insights (OpenTelemetry distro) for request rate, latency, failures; `/api/health` as the
  availability-test target.
- Alerts: HTTP 5xx > 5 in 5 min; p95 latency > 3 s; failed availability test.
- Log Analytics retention 30 days.

## Deployment steps

1. `az group create` the resource group; create ACR, storage account, App Service plan and web app
   (container, port 8000), enable system-assigned identity, assign the two roles above.
2. Create the Entra app registration with a federated credential for
   `repo:<owner>/<repo>:environment:production`; grant it `Contributor` on the resource group only.
3. Add the three repository variables. Add a manually triggered `deploy.yml` (workflow_dispatch) that:
   `azure/login@v2` (OIDC) -> `az acr build` -> `az webapp config container set` -> health check
   `GET /api/health`. (Not included in this repo because it cannot be verified without a subscription.)
4. Verify: open the site, run the sample, check Application Insights shows the request.

## Cost-control assumptions (estimates, not quotes)

- B1 plan plus Basic ACR plus small LRS storage is expected to cost on the order of tens of USD per month
  in dev; verify with the Azure pricing calculator for your region.
- Stop or delete the dev resource group when not in use; set a budget alert at a low monthly limit.
- Keep request size capped (5 MB) and autoscale max instances at 2.
