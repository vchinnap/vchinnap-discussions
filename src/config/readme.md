| Role                       | Management Scope                | Can Modify Runbooks? | Can Start/Stop Jobs? | Can Manage Permissions? |
| -------------------------- | ------------------------------- | -------------------- | -------------------- | ----------------------- |
| **Automation Contributor** | Full automation account         | ✅ Yes                | ✅ Yes                | ❌ No                    |
| **Automation Operator**    | Limited: view/operate jobs only | ❌ No                 | ✅ Yes                | ❌ No                    |
| ([Microsoft Learn][1])     |                                 |                      |                      |                         |

[1]: https://learn.microsoft.com/en-us/azure/automation/automation-role-based-access-control?utm_source=chatgpt.com "Manage role permissions and security in Azure Automation"









Here’s a **clean Confluence-style description** along with the formatted content you can paste directly into your Confluence page:

---

## 📄 Azure Automation – CDK Source and Reference Details

This document provides an overview of the Azure Automation account setup, support operations, and readiness processes, along with relevant source code locations and escalation paths. It is intended to guide internal teams in understanding the ownership, repository structure, and how to seek support for CDK or DevOps-related issues.

---

### 🔗 Jira Ticket

* **[HCOPS-3153 – Azure Automation Implementation Tracking](https://OMB.atlassian.net/browse/HCOPS-3153)**

---

### 📘 Related Confluence Pages

| Topic                               | Description                                                 | Link                                                                                   |
| ----------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **Azure Automation**                | Core automation configuration and lifecycle management      | Azure Automation - Cloud Services Azure - OMB Enterprise Confluence                    |
| **Azure MOR (Mandatory Readiness)** | Mandatory operational readiness checklist and compliance    | Azure Automation MOR - Cloud Services Azure - OMB Enterprise Confluence                |
| **Support Operations**              | Day-to-day automation support practices and hand-off steps  | Azure Automation Support Operations - Cloud Services Azure - OMB Enterprise Confluence |
| **Setup Guide**                     | End-to-end setup guide for provisioning automation accounts | Azure Automation Setup - Cloud Services Azure - OMB Enterprise Confluence              |

> 🔗 *Please replace the links above with actual Confluence URLs if needed.*

---

### 🌐 Cloud Blog Posts

* **[Latest Updates & Announcements](https://OMB.atlassian.net/wiki/spaces/AUTOMATE/pages/243271660/News+Announcements+Blog+Updates)**

---

### 🧩 Source Code Reference

* **Repo**: `HCOPS-CDKTF-Test_TU3450`
* **Path**: `/infra/lib` at `master`
* **Environment**: `OMB-Prod/COPS-CDKTF-Test_TU3450`

---

### 🛠️ Support & Escalation

For any CDK pipeline or DevOps-related concerns:

* 📥 **Reach out to**: `ing_CLOUD_AUTOMATION` via Microsoft Teams
* 🧾 **Include**: an Incident Ticket with relevant error/log information

---

Let me know if you'd like this exported as a `.docx` or `.confluence` storage format.
