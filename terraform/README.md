# West Discovery — Infrastructure as Code

Terraform configuration for deploying the West Discovery platform on AWS. This provisions all infrastructure needed to run containerized services on ECS Fargate, including networking integration, container registry, secrets management, and a GitHub Actions CI/CD pipeline via OIDC.

---

## Table of Contents

- [What This Spins Up](#what-this-spins-up)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Adding a New Service](#adding-a-new-service)
- [Enabling Production](#enabling-production)
- [Secrets Management](#secrets-management)
- [IAM Roles & Policies](#iam-roles--policies)
- [CI/CD Integration](#cicd-integration)
- [Modules Reference](#modules-reference)
- [Destroying Infrastructure](#destroying-infrastructure)

---

## What This Spins Up

Running `terraform apply` for the integration environment creates the following AWS resources:

### Networking
- Connects to your **existing VPC** and subnets (no new VPC is created)
- Uses your existing **private subnets** for ECS task placement
- Uses your existing **public subnets** for load balancer placement

### Container Registry (ECR)
- One **ECR repository** per service (e.g. `transaction-api`)
- Lifecycle policy to retain the last 30 images per repository
- Image scanning on push enabled

### ECS Cluster
- One **ECS Fargate cluster** named `<project>-integration`
- Container Insights enabled for CloudWatch metrics
- Both `FARGATE` and `FARGATE_SPOT` capacity providers registered

### Per-Service Resources
For each service defined in the `services` variable:

| Resource | Name Pattern |
|---|---|
| ECS Service | `<service-name>` inside `<project>-integration` cluster |
| ECS Task Definition | `<service-name>-integration` |
| Application Load Balancer | `<service-name>-integration-alb` |
| ALB Target Group | `<service-name>-integration-tg` |
| ALB Security Group | `<service-name>-integration-alb-sg` |
| ECS Tasks Security Group | `<service-name>-integration-tasks-sg` |
| CloudWatch Log Group | `/ecs/<project>/integration/<service-name>` |

### IAM
Four IAM roles and several policies are created. See the [IAM Roles & Policies](#iam-roles--policies) section for a full breakdown.

### Secrets
- One **AWS Secrets Manager** secret per service per environment
- Path pattern: `<service-name>/<environment>` (e.g. `transaction-api/integration`)
- All secrets stored as a single JSON object under that path
- IAM policies attached to both the task role and task execution role

---

## Architecture

### Overall Infrastructure Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                          AWS Account                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     Existing VPC                         │   │
│  │                                                          │   │
│  │   ┌─────────────────────┐  ┌─────────────────────────┐  │   │
│  │   │   Public Subnets    │  │    Private Subnets       │  │   │
│  │   │                     │  │                          │  │   │
│  │   │  ┌───────────────┐  │  │  ┌────────────────────┐ │  │   │
│  │   │  │      ALB      │  │  │  │   ECS Fargate Task  │ │  │   │
│  │   │  │ (per service) │──┼──┼─▶│   (per service)    │ │  │   │
│  │   │  └───────────────┘  │  │  └────────────────────┘ │  │   │
│  │   │                     │  │           │              │  │   │
│  │   │  ┌───────────────┐  │  │           │              │  │   │
│  │   │  │ NAT Gateway   │  │  │           ▼              │  │   │
│  │   │  │  (existing)   │  │  │  ┌────────────────────┐ │  │   │
│  │   │  └───────────────┘  │  │  │   Secrets Manager  │ │  │   │
│  │   └─────────────────────┘  │  └────────────────────┘ │  │   │
│  │                            └─────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────┐ │
│  │     ECR      │   │ CloudWatch   │   │        IAM          │ │
│  │ (per service)│   │  Log Groups  │   │  Roles & Policies   │ │
│  └──────────────┘   └──────────────┘   └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Traffic Flow

```
  Internet
     │
     ▼
┌─────────────────────────────────┐
│  ALB (public subnet)            │
│  Port 80/443                    │
│  Security Group: 0.0.0.0/0 in  │
└────────────────┬────────────────┘
                 │  forwards to target group
                 ▼
┌─────────────────────────────────┐
│  ECS Fargate Task (private      │
│  subnet)                        │
│  Port: container_port           │
│  Security Group: ALB SG only    │
└────────────────┬────────────────┘
                 │  outbound via NAT Gateway
                 ▼
           Internet / AWS APIs
           (ECR, Secrets Manager,
            CloudWatch, etc.)
```

### CI/CD Flow

```
  Developer
     │
     │  git push
     ▼
┌─────────────────────────────────────────────────────────┐
│                    GitHub Actions                        │
│                                                         │
│  ┌──────────┐    ┌─────────────────┐    ┌───────────┐  │
│  │  build   │───▶│deploy-integration│   │deploy-prod│  │
│  │          │    │                 │    │           │  │
│  │ • Docker │    │ • integration   │    │ • main    │  │
│  │   build  │    │   branch only   │    │   branch  │  │
│  │ • ECR    │    │                 │    │   only    │  │
│  │   push   │    └────────┬────────┘    └─────┬─────┘  │
│  └──────────┘             │                   │        │
└──────────────────────────┼───────────────────┼────────┘
                           │ OIDC              │ OIDC
                           ▼                   ▼
                    ┌─────────────┐    ┌──────────────┐
                    │  IAM Role   │    │   IAM Role   │
                    │ integration │    │  production  │
                    └──────┬──────┘    └──────┬───────┘
                           │                  │
                           ▼                  ▼
                    ┌─────────────────────────────────┐
                    │              ECS                │
                    │  • Register task definition     │
                    │  • Update service               │
                    │  • Wait for stability           │
                    └─────────────────────────────────┘
```

### Cluster and Service Layout

```
┌──────────────────────────────────────────────────┐
│         ECS Cluster: transaction-api-integration  │
│                                                  │
│   ┌──────────────────────────────────────────┐   │
│   │  Service: transaction-api                 │   │
│   │  Task Definition: transaction-api-integration│ │
│   │  Launch Type: FARGATE                    │   │
│   └──────────────────────────────────────────┘   │
│                                                  │
│   ┌──────────────────────────────────────────┐   │
│   │  Service: new-service  (future)          │   │
│   │  Task Definition: new-service-integration│   │
│   └──────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│        ECS Cluster: transaction-api-production    │
│                  (commented out)                 │
└──────────────────────────────────────────────────┘
```

### Secrets Structure

```
AWS Secrets Manager
└── transaction-api/
    └── integration          ← single secret, JSON object
        ├── BOOTSTRAP_SERVERS
        ├── CONFLUENT_CLOUD_USERNAME
        ├── CONFLUENT_CLOUD_PASSWORD
        ├── GLOBUS_CLIENT_ID
        ├── GLOBUS_CLIENT_SECRET
        └── TOPIC
```

---

## Prerequisites

Before running Terraform you will need the following:

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5.0
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured with sufficient permissions
- [jq](https://jqlang.github.io/jq/download/) (used by the secrets script)
- An existing AWS VPC with tagged public and private subnets
- A GitHub repository with Actions enabled
- The GitHub OIDC provider already registered in your AWS account

  To check if the OIDC provider exists:
  ```bash
  aws iam list-open-id-connect-providers | grep token.actions
  ```

  To create it if it doesn't exist, uncomment the `aws_iam_openid_connect_provider` resource in `modules/iam/main.tf`.

### Required Subnet Tags

The Terraform data sources look up subnets by tag. Your existing subnets must be tagged as follows:

| Tag Key | Tag Value |
|---|---|
| `Tier` | `private` |
| `Tier` | `public` |

If your subnets use different tags, update the `data "aws_subnets"` blocks in `main.tf` accordingly.

---

## Project Structure

```
terraform/
├── main.tf                  # Root module — wires everything together
├── variables.tf             # Input variable definitions
├── outputs.tf               # Output values (ALB URLs, role ARNs, etc.)
├── terraform.tfvars         # Your variable values (do not commit secrets)
├── envs/
│   ├── integration.tfvars   # Integration environment values
│   └── production.tfvars    # Production environment values
├── scripts/
│   ├── tf.sh                # Wrapper script for safe plan/apply
│   └── create-secrets.sh    # Script to populate Secrets Manager
├── ecs/
│   └── task-definition.json # ECS task definition used by GitHub Actions
└── modules/
    ├── cluster/             # ECS cluster (one per environment)
    ├── ecr/                 # ECR repository (one per service)
    ├── iam/                 # IAM roles and policies
    ├── secrets/             # Secrets Manager policy and attachments
    └── service/             # ECS service, ALB, task definition, log group
```

---

## Quick Start

### 1. Configure your variables

Copy and edit the tfvars file:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Fill in your values. Note that `github_org` and `github_repo` are set per service, not at the top level:

```hcl
aws_region = "us-east-1"
project    = "transaction-api"
vpc_id     = "vpc-0abc1234def56789"

services = {
  "transaction-api" = {
    container_port     = 8080
    container_cpu      = 512
    container_memory   = 1024
    health_check_path  = "/health"
    log_retention_days = 30
    desired_count      = 1
    github_org         = "your-github-org"
    github_repo        = "transaction-api"
  }
}
```

### 2. Initialize Terraform

```bash
cd terraform
terraform init
```

### 3. Plan and apply

Using the wrapper script (recommended):

```bash
chmod +x scripts/tf.sh
./scripts/tf.sh integration plan
./scripts/tf.sh integration apply
```

Or directly with Terraform:

```bash
terraform plan -var-file="envs/integration.tfvars" -out=tfplan.integration
terraform apply tfplan.integration
```

### 4. Capture outputs

After apply, grab the role ARNs needed for GitHub Environment secrets:

```bash
terraform output github_actions_integration_role_arn  # → integration AWS_ROLE_TO_ASSUME
terraform output github_actions_production_role_arn   # → production AWS_ROLE_TO_ASSUME
terraform output ecr_repository_urls                  # → ECR repository URLs
terraform output integration_service_urls             # → ALB DNS names
```

### 5. Configure GitHub Environments

The workflow uses GitHub Environments so that the same secret name (`AWS_ROLE_TO_ASSUME`) holds a different role ARN per environment. This avoids maintaining separately named secrets like `AWS_PROD_ROLE_TO_ASSUME` at the repo level.

In your GitHub repository go to **Settings → Environments** and create two environments:

**`integration` environment:**

| Secret | Value |
|---|---|
| `AWS_ROLE_TO_ASSUME` | Value of `github_actions_integration_role_arn` output |

**`production` environment:**

| Secret | Value |
|---|---|
| `AWS_ROLE_TO_ASSUME` | Value of `github_actions_production_role_arn` output |

Optionally, on the `production` environment enable **Required reviewers** under Protection Rules. This pauses the production deploy job and waits for a manual approval before proceeding.

To get the role ARNs after apply:

```bash
terraform output github_actions_integration_role_arn
terraform output github_actions_production_role_arn
```

### 6. Update the task definition

After apply, update `ecs/task-definition.json` with the real role ARNs:

```bash
# Get the ARNs
terraform output -json | jq '{
  executionRoleArn: .ecs_task_execution_role_arn.value,
  taskRoleArn: .ecs_task_role_arn.value
}'
```

Replace the `FILL_IN_AFTER_APPLY` placeholders in `ecs/task-definition.json` with those values and commit the file to your repository.

### 7. Create secrets

Populate Secrets Manager with your application secrets:

```bash
chmod +x scripts/create-secrets.sh

# Interactive
./scripts/create-secrets.sh integration

# From a .env file
./scripts/create-secrets.sh integration --env-file .env
```

---

## Adding a New Service

No Terraform markup changes needed. Just add an entry to the `services` map in your `.tfvars` file:

```hcl
services = {
  "transaction-api" = {
    container_port     = 8080
    container_cpu      = 512
    container_memory   = 1024
    health_check_path  = "/health"
    log_retention_days = 30
    desired_count      = 1
    github_org         = "your-github-org"
    github_repo        = "transaction-api"
  }
  "new-service" = {
    container_port     = 9090
    container_cpu      = 256
    container_memory   = 512
    health_check_path  = "/ping"
    log_retention_days = 14
    desired_count      = 1
    github_org         = "your-github-org"
    github_repo        = "new-service"
  }
}
```

Then plan and apply:

```bash
./scripts/tf.sh integration plan
./scripts/tf.sh integration apply
```

Terraform will create a new ECR repository, ECS service, ALB, security groups, log group, and secrets policy for the new service automatically.

---

## Enabling Production

Production resources are defined but commented out throughout the codebase. To enable them:

1. Uncomment the production blocks in `main.tf`:
   - `module "cluster_production"`
   - `module "secrets_production"`
   - `module "services_production"`
   - The production ARN inputs to `module "iam"`

2. Uncomment the production outputs in `outputs.tf`

3. Uncomment the production variables in `modules/iam/variables.tf`

4. Plan and apply using the production var file:

```bash
./scripts/tf.sh production plan
./scripts/tf.sh production apply  # will prompt for confirmation
```

---

## Secrets Management

All application secrets are stored in AWS Secrets Manager as a single JSON object per service per environment. ECS injects them as environment variables at container startup — your application code does not need an SDK to access them.

### Creating / updating secrets

```bash
# Interactive prompts
./scripts/create-secrets.sh integration

# From a .env file
./scripts/create-secrets.sh integration --env-file .env
./scripts/create-secrets.sh production  --env-file .env.production
```

### Secret path structure

```
transaction-api/integration   ← full JSON object
transaction-api/production    ← full JSON object
```

### Referencing secrets in the task definition

Each secret is referenced individually using the `::key::` suffix syntax:

```json
"secrets": [
  {
    "name": "BOOTSTRAP_SERVERS",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:transaction-api/integration::BOOTSTRAP_SERVERS::"
  }
]
```

### .env file format

```bash
BOOTSTRAP_SERVERS=pkc-abc123.us-east-1.aws.confluent.cloud:9092
CONFLUENT_CLOUD_USERNAME=myuser
CONFLUENT_CLOUD_PASSWORD=mypassword
GLOBUS_CLIENT_ID=abc-123
GLOBUS_CLIENT_SECRET=supersecret
TOPIC=my-topic
```

> ⚠️ Never commit `.env` files to version control. Add them to `.gitignore`.

---

## IAM Roles & Policies

This is one of the most important parts of the infrastructure to understand. Four IAM roles are created, each with a distinct purpose and a tightly scoped set of permissions. No role has more access than it needs.

---

### Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          IAM Roles                                  │
│                                                                     │
│   GitHub Actions         │          ECS                            │
│   ─────────────          │          ───                            │
│                          │                                         │
│  ┌───────────────────┐   │   ┌────────────────────────────────┐   │
│  │  Integration Role │   │   │     Task Execution Role        │   │
│  │  (OIDC)           │   │   │     (ecs-tasks.amazonaws.com)  │   │
│  │                   │   │   │                                │   │
│  │  • ECR push/pull  │   │   │  • ECR pull                    │   │
│  │  • ECS deploy     │   │   │  • Secrets Manager read        │   │
│  └───────────────────┘   │   │  • CloudWatch logs write       │   │
│                          │   └────────────────────────────────┘   │
│  ┌───────────────────┐   │                                         │
│  │  Production Role  │   │   ┌────────────────────────────────┐   │
│  │  (OIDC)           │   │   │     Task Role                  │   │
│  │                   │   │   │     (ecs-tasks.amazonaws.com)  │   │
│  │  • ECR push/pull  │   │   │                                │   │
│  │  • ECS deploy     │   │   │  • Secrets Manager read        │   │
│  └───────────────────┘   │   │  • KMS decrypt                 │   │
│                          │   └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Role 1: GitHub Actions Integration Role

**Name:** `<project>-github-actions-integration`
**Assumed by:** GitHub Actions jobs running on the `integration` or `add-ci-cd` branches
**How it's assumed:** OIDC (no static credentials)

This role is what GitHub Actions uses to authenticate with AWS during a CI/CD run. It is only assumable by the specific GitHub repositories and branches defined in the trust policy — any other repository or branch will be denied.

The trust policy is built **dynamically** from each service's `github_org` and `github_repo` values in the `services` map. If you have multiple services from different repositories, all of their repos will be added to the trust policy automatically.

#### Trust Policy (who can assume this role)

```
GitHub Actions OIDC token — one entry per service repo:
    sub: repo:<github_org>/<github_repo>:ref:refs/heads/integration
    sub: repo:<github_org>/<github_repo>:ref:refs/heads/add-ci-cd
    aud: sts.amazonaws.com
```

The trust policy uses `StringLike` on the `sub` claim so only workflows running from the matching repos and branches can assume it. A workflow from a fork or a different branch cannot assume this role.

The role is resolved in GitHub Actions via the `integration` **GitHub Environment** secret `AWS_ROLE_TO_ASSUME`. When a job declares `environment: integration`, GitHub injects the integration role ARN automatically.

#### Permissions

| Policy | Type | What It Allows |
|---|---|---|
| `<project>-ecr-push-pull` | Managed | Push and pull images to/from all service ECR repositories |
| `ecs-deploy` (inline) | Inline | Register task definitions, describe and update ECS services |

The ECR policy grants two sets of permissions. The `ecr:GetAuthorizationToken` action is scoped to `*` because it is account-level and cannot be scoped to a specific repository. All other ECR actions are scoped to only the specific repository ARNs created by this Terraform:

```
ecr:GetAuthorizationToken         → resource: *
ecr:BatchCheckLayerAvailability   → resource: arn:aws:ecr:...:repository/transaction-api
ecr:CompleteLayerUpload           → resource: arn:aws:ecr:...:repository/transaction-api
ecr:InitiateLayerUpload           → resource: arn:aws:ecr:...:repository/transaction-api
ecr:PutImage                      → resource: arn:aws:ecr:...:repository/transaction-api
ecr:UploadLayerPart               → resource: arn:aws:ecr:...:repository/transaction-api
ecr:BatchGetImage                 → resource: arn:aws:ecr:...:repository/transaction-api
ecr:GetDownloadUrlForLayer        → resource: arn:aws:ecr:...:repository/transaction-api
```

The ECS deploy inline policy is scoped broadly on `ecs:*` actions (required because task definition ARNs are dynamic), but includes a tightly scoped `iam:PassRole` that only permits passing the two ECS roles — not any IAM role in the account:

```
ecs:RegisterTaskDefinition   → resource: *  (ARNs are dynamic, can't scope further)
ecs:DescribeTaskDefinition   → resource: *
ecs:DescribeServices         → resource: *
ecs:UpdateService            → resource: *
ecs:ListTaskDefinitions      → resource: *
iam:PassRole                 → resource: arn:...:role/<project>-ecs-task-execution
                                           arn:...:role/<project>-ecs-task
```

---

### Role 2: GitHub Actions Production Role

**Name:** `<project>-github-actions-production`
**Assumed by:** GitHub Actions jobs running on the `main` branch only
**How it's assumed:** OIDC (no static credentials)

Identical permissions to the integration role, but with a stricter trust policy that only allows assumption from the `main` branch using `StringEquals` (not `StringLike`). This means only a merge to `main` can trigger a production deployment — no wildcards.

Like the integration role, the trust policy is built dynamically from each service's `github_org` and `github_repo`. The role is resolved in GitHub Actions via the `production` **GitHub Environment** secret `AWS_ROLE_TO_ASSUME`. When a job declares `environment: production`, GitHub injects the production role ARN automatically.

#### Trust Policy

```
GitHub Actions OIDC token — one entry per service repo:
    sub: repo:<github_org>/<github_repo>:ref:refs/heads/main   (exact match)
    aud: sts.amazonaws.com
```

#### Permissions

Same as the integration role — ECR push/pull and ECS deploy. The separation into two roles (rather than one shared role) means you can independently audit, restrict, or revoke production access without affecting integration deployments.

---

### Role 3: ECS Task Execution Role

**Name:** `transaction-api-ecs-task-execution`
**Assumed by:** `ecs-tasks.amazonaws.com` (the ECS agent, not your code)
**When it's active:** During container startup, before your application code runs

This role is used by the ECS infrastructure itself — not your application. When ECS starts a new task it uses this role to pull the Docker image from ECR, fetch secrets from Secrets Manager, and set up CloudWatch log streaming. Once the container is running, this role is no longer active.

#### Permissions

| Policy | Type | What It Allows |
|---|---|---|
| `AmazonECSTaskExecutionRolePolicy` | AWS Managed | ECR pull, CloudWatch Logs write |
| `transaction-api-integration-secrets-access` | Managed (from secrets module) | Secrets Manager read, KMS decrypt |

The AWS managed policy `AmazonECSTaskExecutionRolePolicy` covers the baseline ECS needs:

```
ecr:GetAuthorizationToken          → Pull images from ECR
ecr:BatchCheckLayerAvailability    → Pull images from ECR
ecr:GetDownloadUrlForLayer         → Pull images from ECR
ecr:BatchGetImage                  → Pull images from ECR
logs:CreateLogStream               → Write container logs to CloudWatch
logs:PutLogEvents                  → Write container logs to CloudWatch
```

The secrets policy is attached here because ECS needs to read secrets **before** the container starts in order to inject them as environment variables. Without this attachment, tasks that reference secrets in their task definition will fail with `ResourceInitializationError`.

```
secretsmanager:GetSecretValue      → resource: arn:...:secret:transaction-api/integration/*
secretsmanager:DescribeSecret      → resource: arn:...:secret:transaction-api/integration/*
kms:Decrypt                        → resource: (your KMS key ARN, or * if default)
kms:GenerateDataKey                → resource: (your KMS key ARN, or * if default)
```

---

### Role 4: ECS Task Role

**Name:** `transaction-api-ecs-task`
**Assumed by:** `ecs-tasks.amazonaws.com` (your running container)
**When it's active:** While your application code is running

This is the role your application code uses at runtime. If your app makes any direct AWS SDK calls — for example calling Secrets Manager to refresh a credential, writing to S3, publishing to SNS — those calls are made using this role's credentials.

The same secrets policy is also attached here (in addition to the execution role) to cover the case where application code calls Secrets Manager directly at runtime rather than relying solely on the injected environment variables.

#### Permissions

| Policy | Type | What It Allows |
|---|---|---|
| `transaction-api-integration-secrets-access` | Managed (from secrets module) | Secrets Manager read, KMS decrypt |

If your service needs additional AWS permissions at runtime (e.g. S3 read, SQS publish), you would add those permissions to this role — not the execution role.

---

### How the Two ECS Roles Work Together

A common point of confusion is why there are two separate ECS roles. The distinction maps to two different phases of the container lifecycle:

```
ECS schedules a new task
         │
         ▼
┌─────────────────────────────────────────────┐
│  STARTUP PHASE — Task Execution Role        │
│                                             │
│  1. Pull image from ECR                     │
│  2. Fetch secrets from Secrets Manager      │
│  3. Inject secrets as environment variables │
│  4. Set up CloudWatch log stream            │
│                                             │
│  Role: transaction-api-ecs-task-execution    │
└───────────────────┬─────────────────────────┘
                    │  container starts
                    ▼
┌─────────────────────────────────────────────┐
│  RUNTIME PHASE — Task Role                  │
│                                             │
│  5. Application code runs                   │
│  6. Any AWS SDK calls use this role         │
│     (Secrets Manager, S3, SQS, etc.)        │
│                                             │
│  Role: transaction-api-ecs-task              │
└─────────────────────────────────────────────┘
```

In practice, if you only use the `secrets` block in your task definition and your app never calls AWS directly, only the execution role's secrets permission is strictly needed. Both roles have it attached for completeness and to avoid issues if the app ever does make a direct SDK call.

---

### Role and Policy Attachment Summary

```
<project>-github-actions-integration
    └── <project>-ecr-push-pull             (managed policy attachment)
    └── ecs-deploy                          (inline policy)

<project>-github-actions-production         (commented out until production enabled)
    └── <project>-ecr-push-pull             (managed policy attachment)
    └── ecs-deploy                          (inline policy)

<project>-ecs-task-execution
    └── AmazonECSTaskExecutionRolePolicy    (AWS managed policy attachment)
    └── <service>-integration-secrets-access  (managed policy attachment)

<project>-ecs-task
    └── <service>-integration-secrets-access  (managed policy attachment)
```

---

## CI/CD Integration

The GitHub Actions workflow in `.github/workflows/ci-cd.yml` integrates with this infrastructure via OIDC — no static AWS credentials are stored in GitHub. Each deploy job declares a GitHub Environment (`integration` or `production`), and GitHub resolves `secrets.AWS_ROLE_TO_ASSUME` from that environment's secret store rather than the repo level. This means the same secret name holds a different role ARN per environment.

### How OIDC authentication works

```
GitHub Actions job
      │  (declares environment: integration OR production)
      │
      │  requests OIDC token
      ▼
GitHub OIDC Provider
      │
      │  token contains: repo, branch, ref
      ▼
AWS STS AssumeRoleWithWebIdentity
      │
      │  validates token against IAM trust policy
      │  (checks repo + branch match)
      ▼
IAM Role resolved from GitHub Environment secret
      │
      │  short-lived credentials (1 hour)
      ▼
AWS APIs (ECR push, ECS deploy)
```

### GitHub Environments and secret resolution

```
GitHub Repository
├── Environments
│   ├── integration
│   │   └── AWS_ROLE_TO_ASSUME = arn:...:role/<project>-github-actions-integration
│   └── production
│       └── AWS_ROLE_TO_ASSUME = arn:...:role/<project>-github-actions-production
│
└── Workflow jobs
    ├── build            (no environment — uses repo-level secrets if any)
    ├── deploy-integration
    │   └── environment: integration  ← resolves AWS_ROLE_TO_ASSUME from here
    └── deploy-production
        └── environment: production   ← resolves AWS_ROLE_TO_ASSUME from here
```

### Branch to environment mapping

| Branch | GitHub Environment | AWS IAM Role | Secret Resolved From |
|---|---|---|---|
| `integration` | `integration` | `<project>-github-actions-integration` | integration environment |
| `add-ci-cd` | `integration` | `<project>-github-actions-integration` | integration environment |
| `main` | `production` | `<project>-github-actions-production` | production environment |

### Production protection rules

The `production` GitHub Environment supports **Required reviewers** under **Settings → Environments → production → Protection Rules**. When enabled, the `deploy-production` job pauses after the build completes and sends a notification to the designated reviewers. A manual approval is required before the deployment proceeds.

```
build job completes
        │
        ▼
deploy-production job triggered
        │
        ▼
┌───────────────────────────────┐
│  Waiting for approval         │
│  GitHub Environment: production│
│  Required reviewers notified  │
└──────────────┬────────────────┘
               │  reviewer approves
               ▼
      deployment proceeds
```

This is independent of the branch restriction on the IAM trust policy — both guards must pass for a production deployment to succeed.

---

## Modules Reference

### `cluster`
Creates an ECS Fargate cluster for a given environment. One cluster per environment, shared by all services.

| Variable | Description |
|---|---|
| `project` | Top-level project name (used to name the cluster) |
| `environment` | Environment name (`integration`, `production`) |

### `ecr`
Creates an ECR repository for a service with a lifecycle policy.

| Variable | Description |
|---|---|
| `repository_name` | Name of the repository (matches service name) |
| `image_retention_count` | Number of images to retain (default: 30) |

### `iam`
Creates all IAM roles and policies — GitHub Actions OIDC roles (one per environment), ECS task execution role, and ECS task role. Trust policies are built dynamically from each service's `github_org` and `github_repo` values, so multiple repos can be granted access by adding entries to the `services` map.

| Variable | Description |
|---|---|
| `services` | Full services map — `github_org` and `github_repo` are read per service to build OIDC trust policies |
| `ecr_repository_arns` | List of ECR repo ARNs the CI roles can push and pull |
| `integration_cluster_arn` | ARN of the integration ECS cluster |
| `integration_service_arns` | List of integration ECS service ARNs |

### `secrets`
Creates a Secrets Manager IAM policy scoped to a service/environment path and attaches it to the ECS roles.

| Variable | Description |
|---|---|
| `project` | Service name (used to build the secret path) |
| `environment` | Environment name |
| `kms_key_arns` | KMS key ARNs for decryption (default: `["*"]`) |

### `service`
Creates all per-service resources: ALB, target group, security groups, ECS task definition, ECS service, and CloudWatch log group.

| Variable | Description |
|---|---|
| `service_name` | Name of the service |
| `cluster_id` | ECS cluster ID to deploy into |
| `container_port` | Port the container listens on |
| `health_check_path` | ALB health check path |
| `desired_count` | Number of running tasks |

---

## Destroying Infrastructure

### Remove a single service
Remove it from the `services` map in your `.tfvars` and apply:

```bash
./scripts/tf.sh integration plan
./scripts/tf.sh integration apply
```

Terraform will destroy all resources associated with that service. Note that Secrets Manager schedules deletion with a 30-day recovery window by default.

### Destroy everything

```bash
terraform destroy -var-file="envs/integration.tfvars"
```

> ⚠️ This is irreversible. ECR images and Secrets Manager secrets will be permanently deleted.

---

## Notes

- The `task_definition` and `container_definitions` fields on ECS resources use `ignore_changes` — this allows CI/CD to update running task definitions without Terraform reverting them on the next apply.
- ECR repositories use `MUTABLE` image tags to support the branch-based tagging strategy in the CI workflow (`main`, `integration`, `<branch>-<sha>`).
- NAT Gateways must exist on the private subnet route tables in your existing VPC. Without them, ECS tasks will fail to pull images from ECR.