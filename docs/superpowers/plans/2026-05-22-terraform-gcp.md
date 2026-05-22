# Terraform GCP Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codify all GCP infrastructure (Cloud Run, Artifact Registry, Secret Manager, IAM) as Terraform modules with a GCS remote state backend, and replace the raw `gcloud` CLI calls in GitHub Actions with `terraform apply`.

**Architecture:** Root module at `infra/` composes four child modules (`cloud-run`, `artifact-registry`, `secrets`, `iam`). GCS bucket holds Terraform state with team locking. Two `.tfvars` files (`dev`, `prod`) parametrise the environments. GitHub Actions runs `terraform plan` on PR and `terraform apply` on merge to main.

**Tech Stack:** Terraform >= 1.7, `hashicorp/google` provider >= 6.0, GCS backend, existing GCP project + Cloud Run service.

---

## Prerequisites

- Terraform CLI installed locally: `brew install terraform` or https://developer.hashicorp.com/terraform/install
- `gcloud` CLI authenticated: `gcloud auth application-default login`
- GCP project ID available: `gcloud config get-value project`
- Existing Cloud Run service name and Artifact Registry repo URL from `backend/.github/workflows/deploy-backend.yml` secrets

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `infra/backend.tf` | GCS remote state backend |
| Create | `infra/main.tf` | Root module — composes child modules |
| Create | `infra/variables.tf` | Input variables shared across modules |
| Create | `infra/outputs.tf` | Outputs (Cloud Run URL, image repo URL) |
| Create | `infra/environments/dev.tfvars` | Dev-specific variable values |
| Create | `infra/environments/prod.tfvars` | Prod-specific variable values |
| Create | `infra/modules/iam/main.tf` | Service account + role bindings |
| Create | `infra/modules/iam/variables.tf` | IAM module variables |
| Create | `infra/modules/iam/outputs.tf` | Service account email output |
| Create | `infra/modules/artifact-registry/main.tf` | Docker repo |
| Create | `infra/modules/artifact-registry/variables.tf` | Registry module variables |
| Create | `infra/modules/artifact-registry/outputs.tf` | Repository URL output |
| Create | `infra/modules/secrets/main.tf` | Secret Manager secrets + IAM bindings |
| Create | `infra/modules/secrets/variables.tf` | Secrets module variables |
| Create | `infra/modules/secrets/outputs.tf` | Secret resource IDs output |
| Create | `infra/modules/cloud-run/main.tf` | Cloud Run v2 service |
| Create | `infra/modules/cloud-run/variables.tf` | Cloud Run module variables |
| Create | `infra/modules/cloud-run/outputs.tf` | Service URL output |
| Modify | `.github/workflows/deploy-backend.yml` | Replace gcloud deploy with terraform apply |
| Create | `infra/.gitignore` | Exclude `.terraform/`, `*.tfstate`, `tfplan` |

---

## Task 1: Bootstrap GCS State Bucket

> This is the only manual step. The GCS bucket cannot manage itself.

- [ ] **Step 1: Create the state bucket**

Replace `YOUR_PROJECT_ID` with your actual GCP project ID:

```bash
gcloud storage buckets create gs://ethic-companion-tfstate \
  --project=YOUR_PROJECT_ID \
  --location=us-central1 \
  --uniform-bucket-level-access

gcloud storage buckets update gs://ethic-companion-tfstate \
  --versioning
```

Expected: `Creating gs://ethic-companion-tfstate/...` then `Updating gs://ethic-companion-tfstate/...`

- [ ] **Step 2: Verify bucket exists**

```bash
gcloud storage buckets describe gs://ethic-companion-tfstate --format="value(name)"
```

Expected: `ethic-companion-tfstate`

---

## Task 2: Infra Directory Skeleton

**Files:**
- Create: `infra/.gitignore`
- Create: `infra/backend.tf`
- Create: `infra/variables.tf`
- Create: `infra/outputs.tf`
- Create: `infra/environments/dev.tfvars`
- Create: `infra/environments/prod.tfvars`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p infra/modules/iam
mkdir -p infra/modules/artifact-registry
mkdir -p infra/modules/secrets
mkdir -p infra/modules/cloud-run
mkdir -p infra/environments
```

- [ ] **Step 2: Create .gitignore**

Create `infra/.gitignore`:

```
.terraform/
.terraform.lock.hcl
*.tfstate
*.tfstate.backup
tfplan
override.tf
override.tf.json
*_override.tf
*_override.tf.json
```

- [ ] **Step 3: Create backend.tf**

Create `infra/backend.tf`:

```hcl
terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0"
    }
  }

  backend "gcs" {
    bucket = "ethic-companion-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
```

- [ ] **Step 4: Create variables.tf**

Create `infra/variables.tf`:

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment: dev or prod"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be 'dev' or 'prod'."
  }
}

variable "cloud_run_service_name" {
  description = "Name of the Cloud Run service"
  type        = string
  default     = "ethic-companion-backend"
}

variable "container_image" {
  description = "Full container image URL (region-docker.pkg.dev/project/repo/image:tag)"
  type        = string
}

variable "min_instances" {
  description = "Minimum Cloud Run instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 5
}

variable "secret_names" {
  description = "Map of env var name → GCP Secret Manager secret name"
  type        = map(string)
  default = {
    SECRET_KEY              = "ethic-companion-secret-key"
    GROQ_API_KEY            = "ethic-companion-groq-api-key"
    GEMINI_API_KEY          = "ethic-companion-gemini-api-key"
    TAVILY_API_KEY          = "ethic-companion-tavily-api-key"
    COMPOSIO_API_KEY        = "ethic-companion-composio-api-key"
    LANGFUSE_PUBLIC_KEY     = "ethic-companion-langfuse-public-key"
    LANGFUSE_SECRET_KEY     = "ethic-companion-langfuse-secret-key"
  }
}
```

- [ ] **Step 5: Create outputs.tf**

Create `infra/outputs.tf`:

```hcl
output "cloud_run_url" {
  description = "Public URL of the Cloud Run service"
  value       = module.cloud_run.service_url
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = module.artifact_registry.repository_url
}

output "service_account_email" {
  description = "Cloud Run service account email"
  value       = module.iam.service_account_email
}
```

- [ ] **Step 6: Create environment tfvars**

Create `infra/environments/dev.tfvars`:

```hcl
project_id             = "YOUR_GCP_PROJECT_ID"
region                 = "us-central1"
environment            = "dev"
cloud_run_service_name = "ethic-companion-backend-dev"
container_image        = "us-central1-docker.pkg.dev/YOUR_GCP_PROJECT_ID/ethic-companion/backend:latest"
min_instances          = 0
max_instances          = 2
```

Create `infra/environments/prod.tfvars`:

```hcl
project_id             = "YOUR_GCP_PROJECT_ID"
region                 = "us-central1"
environment            = "prod"
cloud_run_service_name = "ethic-companion-backend"
container_image        = "us-central1-docker.pkg.dev/YOUR_GCP_PROJECT_ID/ethic-companion/backend:latest"
min_instances          = 1
max_instances          = 10
```

Replace `YOUR_GCP_PROJECT_ID` in both files with your actual project ID.

- [ ] **Step 7: Commit skeleton**

```bash
git add infra/
git commit -m "chore(infra): add Terraform skeleton with GCS backend and env vars"
```

---

## Task 3: IAM Module

**Files:**
- Create: `infra/modules/iam/main.tf`
- Create: `infra/modules/iam/variables.tf`
- Create: `infra/modules/iam/outputs.tf`

- [ ] **Step 1: Create variables.tf**

Create `infra/modules/iam/variables.tf`:

```hcl
variable "project_id" {
  type = string
}

variable "service_account_id" {
  description = "Short ID for the service account (no @... suffix)"
  type        = string
  default     = "ethic-companion-backend"
}
```

- [ ] **Step 2: Create main.tf**

Create `infra/modules/iam/main.tf`:

```hcl
resource "google_service_account" "backend" {
  account_id   = var.service_account_id
  display_name = "Ethic Companion Backend"
  project      = var.project_id
}

locals {
  roles = [
    "roles/run.invoker",
    "roles/cloudsql.client",
    "roles/secretmanager.secretAccessor",
    "roles/artifactregistry.reader",
    "roles/logging.logWriter",
  ]
}

resource "google_project_iam_member" "backend_roles" {
  for_each = toset(local.roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.backend.email}"
}
```

- [ ] **Step 3: Create outputs.tf**

Create `infra/modules/iam/outputs.tf`:

```hcl
output "service_account_email" {
  value = google_service_account.backend.email
}
```

- [ ] **Step 4: Validate module**

```bash
cd infra && terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 5: Commit**

```bash
git add infra/modules/iam/
git commit -m "chore(infra): add IAM module for least-privilege service account"
```

---

## Task 4: Artifact Registry Module

**Files:**
- Create: `infra/modules/artifact-registry/main.tf`
- Create: `infra/modules/artifact-registry/variables.tf`
- Create: `infra/modules/artifact-registry/outputs.tf`

- [ ] **Step 1: Create variables.tf**

Create `infra/modules/artifact-registry/variables.tf`:

```hcl
variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "repository_id" {
  type    = string
  default = "ethic-companion"
}

variable "service_account_email" {
  description = "Service account that gets reader access to pull images"
  type        = string
}
```

- [ ] **Step 2: Create main.tf**

Create `infra/modules/artifact-registry/main.tf`:

```hcl
resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = var.repository_id
  format        = "DOCKER"
  project       = var.project_id

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_artifact_registry_repository_iam_member" "reader" {
  location   = google_artifact_registry_repository.backend.location
  repository = google_artifact_registry_repository.backend.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${var.service_account_email}"
}
```

- [ ] **Step 3: Create outputs.tf**

Create `infra/modules/artifact-registry/outputs.tf`:

```hcl
output "repository_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}"
}
```

- [ ] **Step 4: Validate**

```bash
cd infra && terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 5: Commit**

```bash
git add infra/modules/artifact-registry/
git commit -m "chore(infra): add Artifact Registry module"
```

---

## Task 5: Secrets Module

**Files:**
- Create: `infra/modules/secrets/main.tf`
- Create: `infra/modules/secrets/variables.tf`
- Create: `infra/modules/secrets/outputs.tf`

- [ ] **Step 1: Create variables.tf**

Create `infra/modules/secrets/variables.tf`:

```hcl
variable "project_id" {
  type = string
}

variable "secret_names" {
  description = "Map of env var name → existing Secret Manager secret name"
  type        = map(string)
}

variable "service_account_email" {
  description = "Service account that gets secretAccessor on all secrets"
  type        = string
}
```

- [ ] **Step 2: Create main.tf**

Create `infra/modules/secrets/main.tf`:

```hcl
# Grant the Cloud Run SA access to each pre-existing secret.
# Secrets are created by ops (not Terraform) to avoid storing secret values in state.
resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = var.secret_names

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.service_account_email}"
}
```

- [ ] **Step 3: Create outputs.tf**

Create `infra/modules/secrets/outputs.tf`:

```hcl
output "secret_ids" {
  description = "Map of env var name → secret resource ID"
  value       = { for k, v in var.secret_names : k => "projects/${var.project_id}/secrets/${v}" }
}
```

- [ ] **Step 4: Validate**

```bash
cd infra && terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 5: Commit**

```bash
git add infra/modules/secrets/
git commit -m "chore(infra): add Secrets module for Secret Manager IAM bindings"
```

---

## Task 6: Cloud Run Module

**Files:**
- Create: `infra/modules/cloud-run/main.tf`
- Create: `infra/modules/cloud-run/variables.tf`
- Create: `infra/modules/cloud-run/outputs.tf`

- [ ] **Step 1: Create variables.tf**

Create `infra/modules/cloud-run/variables.tf`:

```hcl
variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_name" {
  type = string
}

variable "container_image" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "min_instances" {
  type    = number
  default = 0
}

variable "max_instances" {
  type    = number
  default = 5
}

variable "secret_ids" {
  description = "Map of env var name → secret resource ID (projects/.../secrets/name)"
  type        = map(string)
  default     = {}
}

variable "environment" {
  type = string
}
```

- [ ] **Step 2: Create main.tf**

Create `infra/modules/cloud-run/main.tf`:

```hcl
resource "google_cloud_run_v2_service" "backend" {
  name     = var.service_name
  location = var.region
  project  = var.project_id

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.container_image

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      # Inject each secret as an environment variable
      dynamic "env" {
        for_each = var.secret_ids
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        period_seconds    = 30
        failure_threshold = 3
      }

      ports {
        container_port = 8000
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      # Image tag is set by CI pipeline, not Terraform
      template[0].containers[0].image,
    ]
  }
}

# Allow unauthenticated invocations (public API)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
```

- [ ] **Step 3: Create outputs.tf**

Create `infra/modules/cloud-run/outputs.tf`:

```hcl
output "service_url" {
  value = google_cloud_run_v2_service.backend.uri
}
```

- [ ] **Step 4: Validate**

```bash
cd infra && terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 5: Commit**

```bash
git add infra/modules/cloud-run/
git commit -m "chore(infra): add Cloud Run v2 module with health probes and secret injection"
```

---

## Task 7: Root Module Composition

**Files:**
- Create: `infra/main.tf`

- [ ] **Step 1: Create main.tf**

Create `infra/main.tf`:

```hcl
module "iam" {
  source     = "./modules/iam"
  project_id = var.project_id
}

module "artifact_registry" {
  source                = "./modules/artifact-registry"
  project_id            = var.project_id
  region                = var.region
  service_account_email = module.iam.service_account_email

  depends_on = [module.iam]
}

module "secrets" {
  source                = "./modules/secrets"
  project_id            = var.project_id
  secret_names          = var.secret_names
  service_account_email = module.iam.service_account_email

  depends_on = [module.iam]
}

module "cloud_run" {
  source                = "./modules/cloud-run"
  project_id            = var.project_id
  region                = var.region
  service_name          = var.cloud_run_service_name
  container_image       = var.container_image
  service_account_email = module.iam.service_account_email
  min_instances         = var.min_instances
  max_instances         = var.max_instances
  secret_ids            = module.secrets.secret_ids
  environment           = var.environment

  depends_on = [module.iam, module.secrets]
}
```

- [ ] **Step 2: Init and validate**

```bash
cd infra && terraform init
terraform validate
```

Expected: `Terraform has been successfully initialized!` then `Success! The configuration is valid.`

- [ ] **Step 3: Run plan against dev (dry run — no apply)**

```bash
cd infra && terraform plan -var-file=environments/dev.tfvars
```

Expected: plan output showing resources to create/import. No errors. Review that the plan looks correct before proceeding.

- [ ] **Step 4: Commit**

```bash
git add infra/main.tf
git commit -m "chore(infra): wire root module from iam → registry → secrets → cloud-run"
```

---

## Task 8: Import Existing Resources

> Terraform needs to own resources that already exist. Import them so `terraform apply` doesn't try to recreate them.

- [ ] **Step 1: Import the existing Cloud Run service**

Replace `YOUR_PROJECT_ID`, `YOUR_REGION`, `YOUR_SERVICE_NAME` with actual values from the existing deployment:

```bash
cd infra && terraform import \
  -var-file=environments/prod.tfvars \
  module.cloud_run.google_cloud_run_v2_service.backend \
  "projects/YOUR_PROJECT_ID/locations/YOUR_REGION/services/YOUR_SERVICE_NAME"
```

Expected: `Import successful!`

- [ ] **Step 2: Import the existing Artifact Registry repo**

```bash
cd infra && terraform import \
  -var-file=environments/prod.tfvars \
  module.artifact_registry.google_artifact_registry_repository.backend \
  "projects/YOUR_PROJECT_ID/locations/YOUR_REGION/repositories/ethic-companion"
```

Expected: `Import successful!`

- [ ] **Step 3: Run plan to confirm zero changes**

```bash
cd infra && terraform plan -var-file=environments/prod.tfvars
```

Expected: `No changes. Your infrastructure matches the configuration.`

If there are unexpected diffs, investigate before applying — do not force-apply.

- [ ] **Step 4: Commit terraform state reference**

```bash
# The .terraform.lock.hcl should be committed (reproducible provider versions)
git add infra/.terraform.lock.hcl
git commit -m "chore(infra): commit provider lock file after successful import"
```

---

## Task 9: Update GitHub Actions

**Files:**
- Modify: `.github/workflows/deploy-backend.yml`

- [ ] **Step 1: Replace the deploy job**

In `.github/workflows/deploy-backend.yml`, replace the entire `deploy:` job with:

```yaml
  deploy:
    name: Terraform Apply → Deploy to Cloud Run
    needs: test
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SA_EMAIL }}

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.7"

      - name: Build and push Docker image
        env:
          IMAGE: ${{ secrets.ARTIFACT_REGISTRY_REPO }}/backend:${{ github.sha }}
        run: |
          gcloud auth configure-docker ${{ secrets.GCP_REGION }}-docker.pkg.dev --quiet
          docker build -t $IMAGE ./backend
          docker push $IMAGE
          echo "IMAGE=$IMAGE" >> $GITHUB_ENV

      - name: Run database migrations
        working-directory: backend
        run: python -m scripts.run_migrations
        env:
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
          ENVIRONMENT: "production"
          GOOGLE_CLOUD_PROJECT: ${{ secrets.GCP_PROJECT }}

      - name: Terraform Init
        run: terraform -chdir=infra init

      - name: Terraform Plan
        run: |
          terraform -chdir=infra plan \
            -var-file=environments/prod.tfvars \
            -var="container_image=${{ env.IMAGE }}" \
            -out=tfplan

      - name: Terraform Apply
        run: terraform -chdir=infra apply tfplan

      - name: Print deployed URL
        run: terraform -chdir=infra output cloud_run_url
```

Also add a plan-only step to the PR workflow (add a new job to `ci.yml` or the existing PR check):

```yaml
  terraform-plan:
    name: Terraform Plan (PR check)
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SA_EMAIL }}
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.7"
      - name: Terraform Init
        run: terraform -chdir=infra init
      - name: Terraform Validate
        run: terraform -chdir=infra validate
      - name: Terraform Plan
        run: |
          terraform -chdir=infra plan \
            -var-file=environments/prod.tfvars \
            -var="container_image=placeholder:latest"
```

- [ ] **Step 2: Verify CI passes on a test PR**

Push to a branch, open a PR, confirm the `Terraform Plan` job runs and produces a clean plan.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy-backend.yml
git commit -m "chore(ci): replace gcloud deploy with terraform apply in GitHub Actions"
```
