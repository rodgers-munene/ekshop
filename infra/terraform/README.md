# Backend AWS deployment — one-time bootstrap

Stack: a single **EC2** instance running the backend in Docker, an **ECR**
repo for images, **Secrets Manager** for env vars, and GitHub Actions
deploying via **SSM Run Command** (no SSH key, no open port 22) using an
**OIDC** role (no long-lived AWS keys in GitHub). Terraform provisions
everything. Nothing here was applied for you — these are the exact commands
to run once, locally, with your own AWS credentials.

> **Why EC2 instead of App Runner**: App Runner is gated behind an
> AWS account verification step on new accounts (`SubscriptionRequiredException`)
> that can take anywhere from hours to a support-case round trip to clear.
> EC2 has no such gate. This trades App Runner's managed HTTPS/autoscaling
> for a bit more manual ops (see "Follow-ups" below) in exchange for being
> able to deploy today.

## Prerequisites

- An AWS account, with the AWS CLI configured locally (`aws configure`)
  using a user/role with sufficient permissions (IAM, EC2, ECR, Secrets
  Manager, SSM) to create the resources below.
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.6.
- Docker, and repo push access to `rodgers-munene/ekshop` on GitHub.

## 1. Configure variables

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Fill in `terraform.tfvars`: at minimum `secret_env.DATABASE_URL` (your
Supabase connection string) and `secret_env.SECRET_KEY` (generate a real one
— see the comment in the file; don't reuse a weak local dev value in
production). `terraform.tfvars` is gitignored — it holds secrets, never
commit it.

## 2. Apply

```bash
terraform init
terraform apply
```

This creates: the ECR repo, the EC2 instance (Amazon Linux 2023, Docker
installed via user-data, no container running yet), its instance IAM role,
the Secrets Manager secret, and the GitHub OIDC provider + deploy role.

## 3. Wire up GitHub

```bash
terraform output
```

In the GitHub repo settings → **Secrets and variables → Actions**, add:

| Secret | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `github_actions_role_arn` output |
| `EC2_INSTANCE_ID` | `ec2_instance_id` output |
| `SECRETS_MANAGER_ARN` | `secrets_manager_secret_arn` output |
| `DATABASE_URL` | same value as `secret_env.DATABASE_URL` in tfvars (the migration job in CI runs `alembic upgrade head` directly against the DB, separately from the app container) |
| `SECRET_KEY` | same value as `secret_env.SECRET_KEY` in tfvars |

No AWS access keys go in GitHub — the workflow (`.github/workflows/deploy-backend.yml`)
authenticates via OIDC using `AWS_DEPLOY_ROLE_ARN`.

## 4. Ship it

Push to `main` with a change under `backend/`. The workflow will: run
`alembic upgrade head`, build the image, push `:latest` and `:<git-sha>` to
ECR, then run a deploy script on the EC2 instance via `aws ssm send-command`
(pulls the new image, refreshes the env file from Secrets Manager, restarts
the container) and waits for it to report `Success`.

Your API is live at the `backend_url` output (`http://<elastic-ip>`).
Update `plain_env.FRONTEND_URL`, `plain_env.CORS_ORIGINS`, and
`plain_env.MPESA_CALLBACK_URL` in `terraform.tfvars` once you know the real
frontend origin and callback URL, then `terraform apply` again (this updates
the Secrets Manager secret; re-run the GitHub Actions workflow, or manually
re-run the SSM deploy command, to pick up the change — the running container
doesn't auto-reload env vars).

## Follow-ups this setup intentionally defers

- **HTTPS**: the instance currently serves plain HTTP. Once you have a
  domain, point it at the Elastic IP and add Nginx + Let's Encrypt
  (`certbot`) on the instance as a reverse proxy in front of the container,
  or put a Classic/Application Load Balancer with an ACM cert in front of
  it. Either is a follow-up, not required to get the pipeline working today.
- **App Runner migration**: if/when the AWS account verification clears
  (check with `aws apprunner list-services --region eu-west-1` — it stops
  returning `SubscriptionRequiredException`), moving to App Runner later is
  a clean swap: same ECR repo and Secrets Manager secret, different compute
  layer. Not urgent — EC2 works fine for launch traffic.
- **Zero-downtime deploys**: the current deploy script stops the old
  container before starting the new one, so there's a brief gap on every
  deploy. Fine at this stage; revisit if that becomes noticeable.

## Notes

- **Cost**: `t3.micro` is free-tier eligible for 12 months on a new AWS
  account (750 hrs/month); afterward it's roughly $7–8/month. Plus ~$0.40/mo
  for the Secrets Manager secret and negligible ECR storage. No RDS cost
  since Postgres stays on Supabase.
- **Access**: no SSH key pair is created and port 22 is not open. For
  interactive shell access, use **SSM Session Manager**
  (`aws ssm start-session --target <instance-id>`) instead of SSH.
- **State file**: `terraform.tfstate` contains the secret values in
  plaintext (Terraform has to know what it set). It's gitignored, but for
  anything beyond solo use, move to an encrypted remote backend (S3 + KMS +
  a DynamoDB lock table) rather than keeping state on a laptop — see the
  commented `backend "s3"` block in `versions.tf`.
- **Rollback**: push the previous commit's image tag back as `:latest`
  (`docker pull <repo>:<old-sha> && docker tag ... :latest && docker push`)
  and re-run the deploy workflow, or run the deploy script manually via SSM
  with an older tag.
- **Changing secrets/env vars later**: edit `terraform.tfvars`, run
  `terraform apply`, then re-trigger a deploy (push to `main`, or manually
  re-run the last successful workflow run) so the container picks up the
  refreshed Secrets Manager values.
