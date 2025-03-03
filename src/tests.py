Sure! Below is the **Python handler function** that you need to **paste in the AWS Systems Manager Console** while creating the **Automation Document**.

---

### **✅ Handler Code for SSM Automation Document**
```python
def handler(event, context):
    msg = """AWS Config non-compliant resource.
    ResourceId: {resourceId}
    ResourceType: {resourceType}
    ComplianceType: {complianceType}
    AWS Account ID: {accountId}
    AWS Region: {awsRegion}
    Config Rule Name: {configRuleName}
    Details: {annotation}""".format(**event)
    
    return {"message": msg}
```

---

### **🛠 Steps to Use in AWS Console**
1. **Go to** `AWS Systems Manager` > `Documents`.
2. **Click on** `Create document`.
3. **Enter the Name**: `CustomConfigNotification`.
4. **Select Document Type**: `Automation`.
5. **Select Language**: `Python`.
6. **Paste the handler function** in the `Script` section.
7. **For Input Parameters**, add:
   - `resourceId`
   - `resourceType`
   - `complianceType`
   - `accountId`
   - `awsRegion`
   - `configRuleName`
   - `annotation`
8. **Click Create Document.**

✅ **Your SSM Automation Document is now ready!** 🚀
