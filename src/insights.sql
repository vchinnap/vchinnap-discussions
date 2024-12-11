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



Here are the **CloudWatch Logs Insights queries** tailored for each widget type:

---

### **1. Logs Table Widget**
**Purpose**: Display detailed information about backup jobs (FAILED, ABORTED, EXPIRED).

#### Query:
```sql
fields @timestamp, @message
| parse @message /Status: (?<status>[^,]+), Job ID: (?<job_id>[^,]+), Resource Type: (?<resource_type>[^,]+), Message: (?<error_message>.+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| display @timestamp, job_id, status, resource_type, error_message
| sort @timestamp desc
| limit 100
```

---

### **2. Pie Chart Widget**
**Purpose**: Visualize the percentage distribution of job statuses (FAILED, ABORTED, EXPIRED).

#### Query:
```sql
fields @timestamp, @message
| parse @message /Status: (?<status>[^,]+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| stats count(*) as job_count by status
```

---

### **3. Line Chart Widget**
**Purpose**: Track trends in backup job statuses over time.

#### Query:
```sql
fields @timestamp, @message
| parse @message /Status: (?<status>[^,]+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| stats count(*) as job_count by bin(1h), status
| sort bin(1h)
```

---

### **4. Bar Chart Widget**
**Purpose**: Compare the count of backup jobs by resource type and status.

#### Query:
```sql
fields @timestamp, @message
| parse @message /Status: (?<status>[^,]+), Resource Type: (?<resource_type>[^,]+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| stats count(*) as job_count by resource_type, status
| sort job_count desc
```

---

### **5. Stacked Area Chart Widget**
**Purpose**: Track cumulative trends of all job statuses (FAILED, ABORTED, EXPIRED) over time.

#### Query:
```sql
fields @timestamp, @message
| parse @message /Status: (?<status>[^,]+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| stats count(*) as job_count by bin(1h), status
| sort bin(1h)
```

---

### Widget Mapping for Easy Setup:
1. **Logs Table**: Use the **Logs Table Query**.
2. **Pie Chart**: Use the **Pie Chart Query**.
3. **Line Chart**: Use the **Line Chart Query**.
4. **Bar Chart**: Use the **Bar Chart Query**.
5. **Stacked Area Chart**: Use the **Stacked Area Chart Query**.

Copy-paste these queries into the respective widgets when adding them to your **CloudWatch dashboard**. Let me know if you need help setting this up!
