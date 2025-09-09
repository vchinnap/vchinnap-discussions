Here’s what that template does—at a glance and end-to-end:

### What it enforces

* **Policy:** Every EC2 instance you scope (those tagged `ConfigRule=True`) must have **`${RequiredTagKey}=${RequiredTagValue}`** (defaults to `Snapshot_Required=Yes`).

### What it creates

1. **Evaluator IAM role (`EvalRole`)**

   * Lets a Lambda **describe EC2** and **put AWS Config evaluations**.

2. **Evaluator Lambda (`EvaluatorFn`)**

   * Scans **only instances with `ConfigRule=True`** (blast-radius control).
   * If required tag is **missing** or **wrong**, reports **NON\_COMPLIANT** to AWS Config; else **COMPLIANT**.

3. **Invoke permission + Config Rule (`RequiredTagRule`)**

   * Config invokes the Lambda on configuration changes (instance/tag updates).
   * Gives you a **Config rule** result you can see in the console/compliance dashboards.

4. **Remediation IAM role (`RemediationRole`)**

   * Permissions for SSM Automation to **DescribeInstances**, **CreateTags**, and **mark Security Hub findings RESOLVED**.

5. **SSM Automation doc (`EnsureRequiredTagDoc`) – 7-step SH style**

   * **Parse**: Read a **Security Hub findings array (ASFF)** to extract `InstanceId`.
   * **Branch**: If no instance found → **Resolve** (no-op).
   * **Describe**: Get the current value of the required tag on the instance.
   * **Check**: If already compliant → **Resolve** (no action).
   * **DryRun** (STRING): If `"true"` → **Resolve** without changes.
   * **Act**: If needed, **CreateTags** on the instance to set the required key/value.
   * **Resolve**: **BatchUpdateFindings** to set SH workflow status **RESOLVED** (with note).

6. **Outputs**

   * Names/ARNs for the rule, Lambda, SSM doc, and remediation role.

### Important wiring notes

* The **SSM runbook is Security Hub–driven** (expects `FindingsJson`).
  It is **not** linked to the Config rule via `AWS::Config::RemediationConfiguration` (intentionally omitted).
* Typical trigger for the runbook is:
  **Security Hub Finding → EventBridge rule → StartAutomationExecution** (passing `$.detail.findings` into `FindingsJson`).
* You still keep the **Config rule** for posture visibility/tracking; remediation is handled in the **Security Hub flow**.

### Parameters you can tweak

* **Naming:** `Team`, `Service`, `Purpose` → applied to all OMBASR resource names.
* **Policy:** `RequiredTagKey`, `RequiredTagValue` (defaults: `Snapshot_Required=Yes`).
* **Safety:** `DryRun` (STRING: `"true"`/`"false"`). Default is safe (**no changes**) unless you flip it at execution time.
