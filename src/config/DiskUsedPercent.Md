# AWS Config Rule: EC2 Disk Usage Alarm Compliance

This Lambda function is used as a custom AWS Config rule to evaluate whether Amazon EC2 instances have CloudWatch alarms configured for `disk_used_percent` on required mount paths. The evaluation is based on the operating system flavor of the EC2 instance.

## 📌 Use Case

Ensure EC2 instances (with `ConfigRule=True` tag) have CloudWatch alarms for disk usage on critical mount paths, depending on the Linux OS flavor.

## ✅ Supported OS Flavors

- **Amazon Linux** – Only `/` path is checked.
- **Red Hat Enterprise Linux (RHEL)** – Checks the following paths:
  - `/`
  - `/var`
  - `/tmp`
  - `/var/log`
  - `/var/log/audit`

## 🔍 Evaluation Logic

- Filters EC2 instances by the tag `ConfigRule=True`.
- Determines Linux flavor from `PlatformDetails`.
- Searches for **CloudWatch alarms** using the `disk_used_percent` metric name and expected path dimensions.
- ⚠️ **Note**: This rule only verifies the presence of alarms. It does **not** check whether the underlying `disk_used_percent` metric is being actively pushed or contains recent data.

## 🧪 Annotation Examples

- `Amazon Linux: Missing disk alarms for paths: /`
- `Red Hat Enterprise Linux: Missing disk alarms for paths: /var, /tmp`
- `Red Hat Enterprise Linux: All required disk_used_percent alarms are present.`
