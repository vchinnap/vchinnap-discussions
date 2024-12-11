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




You're absolutely right! Let me refine and enhance these queries to ensure accuracy and meaningful insights for each widget.

---

### **1. Logs Table Widget**
**Purpose**: Display detailed information about all backup jobs (FAILED, ABORTED, EXPIRED).

#### Query:
```sql
fields @timestamp, @message
| parse @message /Status: (?<status>[^,]+), Job ID: (?<job_id>[^,]+), Resource Type: (?<resource_type>[^,]+), Message: (?<error_message>.+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| sort @timestamp desc
| limit 100
| display @timestamp, job_id, status, resource_type, error_message
```

---

### **2. Pie Chart Widget**
**Purpose**: Show the percentage distribution of job statuses (FAILED, ABORTED, EXPIRED).

#### Query:
```sql
fields @message
| parse @message /Status: (?<status>[^,]+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| stats count(*) as job_count by status
| display status, job_count
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
| display bin(1h) as time_period, status, job_count
```

---

### **4. Bar Chart Widget**
**Purpose**: Compare the count of backup jobs by resource type and status.

#### Query:
```sql
fields @message
| parse @message /Status: (?<status>[^,]+), Resource Type: (?<resource_type>[^,]+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| stats count(*) as job_count by resource_type, status
| display resource_type, status, job_count
```

---

### **5. Stacked Area Chart Widget**
**Purpose**: Visualize cumulative trends for all job statuses over time.

#### Query:
```sql
fields @timestamp, @message
| parse @message /Status: (?<status>[^,]+)/
| filter status in ["FAILED", "ABORTED", "EXPIRED"]
| stats sum(1) as job_count by bin(1h), status
| display bin(1h) as time_period, status, job_count
```

---

### **Enhanced Features**
1. **Use `bin(1h)` or `bin(1d)`**:
   - `bin(1h)`: Hourly trends (fine-grained data).
   - `bin(1d)`: Daily trends (coarser aggregation).

2. **Error Message Insights** (Optional):
   - Add error message parsing to the bar chart to understand the most common failure reasons.

   #### Query:
   ```sql
   fields @message
   | parse @message /Status: (?<status>[^,]+), Resource Type: (?<resource_type>[^,]+), Message: (?<error_message>.+)/
   | filter status = "FAILED"
   | stats count(*) as failure_count by resource_type, error_message
   | sort failure_count desc
   ```

3. **Filter by Time Range**:
   - Modify time ranges in your queries for specific focus (e.g., last 7 days).

---

### Widget Mapping
- **Logs Table**: Logs Table Query
- **Pie Chart**: Pie Chart Query
- **Line Chart**: Line Chart Query
- **Bar Chart**: Bar Chart Query
- **Stacked Area Chart**: Stacked Area Chart Query

Let me know if you need help fine-tuning or visualizing these!
