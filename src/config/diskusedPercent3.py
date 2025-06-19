Checking alarms for instance: i-0abc123def456
✅ Matched alarm for instance i-0abc123def456, path /var
{
  "AlarmName": "i-0abc123def456 : Disk used percent exceeds defined threshold for MountPoint : /var - HCOPSConfig",
  "MetricName": "disk_used_percent",
  "Dimensions": [
    { "Name": "InstanceId", "Value": "i-0abc123def456" },
    { "Name": "path", "Value": "/var" }
  ],
  ...
}
Evaluation: i-0abc123def456 - COMPLIANT
Annotation: Red Hat Linux: All required disk_used_percent alarms are present.
