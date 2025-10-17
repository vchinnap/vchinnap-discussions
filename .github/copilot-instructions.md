## Repo orientation (short)

This repository contains a collection of AWS-focused utilities, CloudFormation templates, Python Lambda handlers, CDK helpers (TypeScript), and a small React UI used as a static site. Primary areas to look at:

- `src/` — main code: many Python scripts (lambda handlers, remediations), TypeScript CDK helpers (`context-utils.ts`), and UI sources under `src/components`.
- `src/cloud-formation/` — CloudFormation templates (e.g. `discussions-ui.yaml`) that wire S3/CloudFront + a Lambda seeder and show how the frontend talks to a backend API.
- `src/config/` — AWS Config rules, remediation helpers, and sample SSM/CloudWatch scripts.

When editing code, prefer to change files in `src/` and keep CloudFormation templates and CDK helpers consistent with naming conventions used in `context-utils.ts`.

## Big-picture architecture notes

- Frontend: static UI deployed to a private S3 bucket + CloudFront (see `src/cloud-formation/discussions-ui.yaml`). The site is seeded by an inline Node.js Lambda that writes `index.html` to S3. The UI posts to an API endpoint defined by the CFN parameter `ApiEndpoint`. It supports two response modes: `json` and `stream` (SSE-style reader in the client).
- Backend: multiple Python Lambda scripts under `src/` (examples: `lambda.py`, `awsbackup_updated.py`) integrate with AWS services — common integrations: SSM (start automation), SNS (notifications), S3, CloudWatch, and Config/Remediation patterns under `src/config/`.
- Infra helpers: TypeScript helpers like `src/context-utils.ts` supply environment/context values used by CDK stacks. The repo mixes CDK constructs and plain CloudFormation templates — keep both in sync when changing resource names or ARNs.

## Project-specific conventions and patterns

- Environment & naming: `src/context-utils.ts` resolves `stage`, `accountID`, `region`, and builds region/account-specific KMS alias and subnet/SG lists. Tests and infra stacks expect these exact context keys (`stage`, `accountID`, `stageShortCode`, etc.).
- Seeded UI: The CloudFormation template seeds a single `index.html` via an inline Lambda (see `discussions-ui.yaml` → `Seeder` and `SeedWebsite`). Edits to the UI should preserve the seeding flow or replace it with a build artifact that the seeder writes to S3.
- Streaming API: UI supports a streaming mode implemented by reading fetch Response.body via a reader. Any backend implementing streaming must produce newline-separated frames with `data: <json>\n\n` (see `discussions-ui.yaml` client JS for parsing logic).
- AWS clients in Python: Lambdas initialize Boto3 clients at module import time (e.g., `ssm_client = boto3.client('ssm')`). Keep this pattern for consistency but be mindful of local testing/mocking.

## Common developer workflows (discoverable from repo files)

- Run or test Python lambdas locally: use pytest in `src/tests.py` or run small script harnesses. Many lambdas assume AWS creds; for local tests use `AWS_PROFILE` or moto for mocking.
- Deploy UI via CloudFormation: `src/cloud-formation/discussions-ui.yaml` deploys S3 + CloudFront + Seeder. The template expects `ApiEndpoint` and `ResponseMode` parameters. If you change the UI, either update the seeder lambda or deploy the built static files to the bucket it creates.
- Updating CDK helpers: `src/context-utils.ts` is referenced by CDK stacks — when altering stage/region mapping, ensure tests or stacks relying on `subnetIds`/`securityGroupIds` are updated.

## Integration points and external dependencies

- AWS services used: S3, CloudFront, Lambda, SNS, SSM (Automation), CloudWatch, AWS Config. Look for direct Boto3 usage in Python files and IAM roles/policies in CloudFormation.
- Config/Remediation: `src/config/` contains Config rule helpers and SSM documents (`tags-delete-ssm.yaml`). Changes to these files often require coordinated updates to any Lambda remediations that call SSM documents.

## Examples to reference when making changes

- To implement or change frontend streaming behavior, inspect `src/cloud-formation/discussions-ui.yaml` → inline HTML/JS and follow its `data: <json>` framing.
- To add a new Lambda that triggers remediation and notifies, mirror `src/lambda.py` which starts an SSM Automation and publishes to SNS.
- For CDK context values and infra mapping, edit `src/context-utils.ts` and add entries for new `stage-account-region` keys.

## What to avoid / gotchas

- Don’t rename KMS alias or subnet/SG keys casually — they are referenced across CDK helpers and CloudFormation parameters.
- Inline CloudFormation Lambdas (like the Seeder) are used to bootstrap artifacts; if you remove the inline seeder, provide an alternative process to upload the UI to S3.

## If you need to run build or deploy steps (quick tips)

- There is no single monorepo build task. Use language-specific tools: npm/React build for frontend (under `src/components`), pytest for Python tests, and CloudFormation/CDK CLI to deploy infra. When in doubt, inspect the template parameters in `src/cloud-formation/*.yaml`.

## Where to look next

- `src/cloud-formation/discussions-ui.yaml` — UI + seeder example
- `src/context-utils.ts` — CDK context & naming patterns
- `src/lambda.py` and other `src/*.py` — Lambda integration examples (SSM, SNS)
- `src/config/*` — Config rules, SSM docs, remediation scripts

If any section is unclear or you want the file tuned to a different level of detail (more examples, CI/deploy commands, or testing snippets), tell me what to expand and I’ll iterate.
