Perfect ✅ — I’ll give you that **full template**, but with the **option to easily flip between SELF vs. Security account trust**.

Here’s the **copy-ready StackSet template** with comments inline (enterprise style):

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: StackSet - IAM Role (trusts SELF for testing). Comments show how to trust a Security account later.

Parameters:
  RoleName:
    Type: String
    Default: HOPS-Lab-ExecutionRole
    Description: Name of the IAM Role to create in each target account (e.g., Lab).

Resources:
  LabExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Ref RoleName
      MaxSessionDuration: 3600  # 1 hour sessions; adjust if needed
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          # --- TRUST: SELF (for testing) ---
          # This allows any principal in THIS account (where the role is created)
          # to assume the role, provided their own IAM policy grants sts:AssumeRole.
          - Sid: TrustSelfAccountRoot
            Effect: Allow
            Principal:
              AWS: !Sub "arn:${AWS::Partition}:iam::${AWS::AccountId}:root"
            Action: "sts:AssumeRole"

          # --- TRUST: SECURITY ACCOUNT (COMMENTED FOR NOW) ---
          # To trust a whole external Security account later, uncomment and set the 12-digit ID:
          # - Sid: TrustSecurityAccountRoot
          #   Effect: Allow
          #   Principal:
          #     AWS: "arn:${AWS::Partition}:iam::<SECURITY_ACCOUNT_ID>:root"
          #   Action: "sts:AssumeRole"

          # --- TRUST: SPECIFIC ROLE IN SECURITY ACCOUNT (TIGHTER; COMMENTED) ---
          # To trust ONLY a specific role in the Security account, use this instead (safer):
          # - Sid: TrustSpecificSecurityRole
          #   Effect: Allow
          #   Principal:
          #     AWS: "arn:${AWS::Partition}:iam::<SECURITY_ACCOUNT_ID>:role/<SecurityRoleName>"
          #   Action: "sts:AssumeRole"

      # Keep lab-safe; swap to AdministratorAccess only if you really need it in sandboxes.
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/ReadOnlyAccess

      Tags:
        - Key: Owner
          Value: HCOPS
        - Key: Environment
          Value: Lab
        - Key: Purpose
          Value: AssumableLabReadOnly

  # (Optional) Example inline policy — keep commented until you need it.
  # This shows how you'd add least-privilege for SSM/Lambda tests later.
  # LabExecutionRoleInlinePolicy:
  #   Type: AWS::IAM::Policy
  #   Properties:
  #     PolicyName: HOPS-Lab-Extras
  #     Roles: [ !Ref LabExecutionRole ]
  #     PolicyDocument:
  #       Version: "2012-10-17"
  #       Statement:
  #         - Sid: ReadAutomationExecutions
  #           Effect: Allow
  #           Action: "ssm:GetAutomationExecution"
  #           Resource: !Sub "arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:automation-execution/*"

Outputs:
  RoleArn:
    Description: ARN of the IAM Role created in the target (Lab) account
    Value: !GetAtt LabExecutionRole.Arn
```

---

### 🔑 Key Notes

* **For testing**: trusts only *SELF* (account where StackSet runs).
* **For enterprise**: later uncomment one of the **Security account trust** blocks (root = whole account, role = fine-grained).
* **Partition variable** (`${AWS::Partition}`) makes it work in `aws`, `aws-cn`, and `aws-us-gov`.
* Safe default is **ReadOnlyAccess**. Swap to `AdministratorAccess` only in lab if you need.
* Inline policy block is scaffolded for SSM testing, commented out for now.

---

👉 Do you want me to also give you the **CLI command to assume this role** right after deployment (with example output), so you can validate the trust quickly in your Lab account?
