# AWS Config Rule: EC2 Disk Usage Alarm Compliance

This Lambda function is used as a custom AWS Config rule to evaluate whether Amazon EC2 instances have CloudWatch alarms configured for `disk_used_percent` on required mount paths. The evaluation is based on the EC2's Linux OS flavor, determined via the instance's AMI.

## 📌 Use Case

Ensure EC2 instances (with `ConfigRule=True` tag) have CloudWatch alarms for disk usage (`disk_used_percent`) on critical mount paths, based on their Linux flavor.

## ✅ Supported OS Flavors

- **Amazon Linux**
  - Required path: `/`
- **Red Hat Enterprise Linux (RHEL)**
  - Required paths:
    - `/`
    - `/var`
    - `/tmp`
    - `/var/log`
    - `/var/log/audit`
    - `/home`
    - `/opt`
    - `/usr`

Instances with other OS flavors are skipped.

## 🔍 Evaluation Logic

- Filters EC2 instances using the `ConfigRule=True` tag.
- Determines the Linux OS flavor using the instance's `ImageId` via `describe_images`.
- Based on the OS flavor, defines the required mount paths to be monitored.
- Retrieves all existing CloudWatch alarms with `MetricName: disk_used_percent`.
- Checks if alarms exist for each required path on the instance.
- If **any** path is missing an alarm:
  - The instance is marked **NON_COMPLIANT**.
  - The annotation clearly states the **Linux flavor** and lists the **missing paths**.
- If **all** required alarms are present:
  - The instance is marked **COMPLIANT**.
  - The annotation confirms full compliance with OS flavor context.

## 🧪 Annotation Examples

- `Amazon Linux: Missing disk alarms for paths: /`
- `Red Hat Enterprise Linux: Missing disk alarms for paths: /var, /tmp, /usr`
- `Red Hat Enterprise Linux: All required disk_used_percent alarms are present.`
