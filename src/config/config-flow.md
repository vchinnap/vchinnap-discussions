```mermaid
flowchart TD
    A([Start]) --> B["CDK Stack Deploys ConfigRule"]

    B --> C["Managed Rule"]
    B --> D["Custom Rule"]

    C --> E["Remediation Document (SSM)"]
    E --> F["Send to Security Hub"]

    D --> G["Lambda Function Evaluates Compliance"]
    G --> H["Remediation Document (SSM)"]
    H --> I["Send to Security Hub"]
```
