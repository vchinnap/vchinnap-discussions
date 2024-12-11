fields @timestamp, @message
| parse @message /Resource Name: (?<resource_name>[^,]+), Status: (?<status>[^,]+), Job ID: (?<job_id>[^,]+), Resource Type: (?<resource_type>[^,]+), Message: (?<error_message>.+)/
| filter status = "FAILED" and resource_type = "RDS"
| sort @timestamp desc
| display resource_name, status, job_id, resource_type, error_message
| limit 50



fields @timestamp, @message
| parse @message /Resource Name: (?<resource_name>[^,]+), Resource ID: (?<resource_id>[^,]+), Status: (?<status>[^,]+), Job ID: (?<job_id>[^,]+), Resource Type: (?<resource_type>[^,]+), Message: (?<error_message>.+)/
| filter status = "FAILED" and resource_type = "RDS"
| sort @timestamp desc
| display @timestamp, resource_name, resource_id, status, job_id, resource_type, error_message
| limit 50



fields @timestamp, @message
| parse @message /Status: (?<status>[^,]+), Resource Type: (?<resource_type>[^,]+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| stats count(*) as job_count by bin(1h), status, resource_type
| sort bin(1h) asc
| display bin(1h) as time_period, status, resource_type, job_count
