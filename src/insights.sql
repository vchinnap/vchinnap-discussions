fields @timestamp, @message
| parse @message /Resource Name: (?<resource_name>[^,]+), Status: (?<status>[^,]+), Job ID: (?<job_id>[^,]+), Resource Type: (?<resource_type>[^,]+), Message: (?<error_message>.+)/
| filter status = "FAILED" and resource_type = "RDS"
| sort @timestamp desc
| display resource_name, status, job_id, resource_type, error_message
| limit 50
