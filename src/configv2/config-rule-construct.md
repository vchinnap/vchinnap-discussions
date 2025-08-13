Center: This construct deploys an AWS Config rule (managed or custom) and wires an SSM remediation to it.

Inputs: We provide the rule metadata, scope (tags or resource types), remediation doc + params, networking, KMS, and roles.

Actions: The construct loads the remediation JSON, creates the SSM document, creates the Config rule, and sets dependencies so tagging happens after the rule exists.

Paths: If custom, we spin up an eval Lambda and a config rule that triggers on changes or periodically; if managed, we use the AWS identifier. Both get tagged via a small tagging Lambda + Custom Resource.

Remediation: Config’s remediation points to our SSM document. It’s manual by default with concurrency/error controls and retries.

Ops: IAM is least-privileged, Lambdas run in our subnets/SGs, logs are KMS-encrypted.

Outcome: Compliant rule deployment, consistent tagging, and ready-to-run remediation.
