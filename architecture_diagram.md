# Lambda-S3-Redshift Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        AWS Lambda Function Architecture                          │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐
│   Event Trigger │───▶│    Lambda Function      │───▶│   Redshift Cluster      │
│                 │    │   RedshiftS3SP2         │    │ daab-redshift-cluster-  │
│ • API Gateway   │    │                         │    │ jr-bedrock              │
│ • EventBridge   │    │ ┌─────────────────────┐ │    │                         │
│ • Manual        │    │ │   Process Flow      │ │    │ Database: dev           │
└─────────────────┘    │ │                     │ │    │ User: awsuser           │
                       │ │ 1. List S3 objects  │ │    └─────────────────────────┘
┌─────────────────┐    │ │ 2. Read Rel*.txt    │ │              │
│   S3 Bucket     │◀───┤ │ 3. Parse procedures │ │              │
│ daab-lab-jfr-   │    │ │ 4. Execute on       │ │              ▼
│ datalake        │    │ │    Redshift         │ │    ┌─────────────────────────┐
│                 │    │ │ 5. Wait completion  │ │    │   Stored Procedures     │
│ Redshift/       │    │ │ 6. Return results   │ │    │                         │
│ └── Rel*.txt    │    │ └─────────────────────┘ │    │ • Multiple procedures   │
└─────────────────┘    └─────────────────────────┘    │ • Sequential execution  │
                                                      │ • Error handling        │
                                                      └─────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Data Flow Details                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. Event Input                    2. S3 Operations                             │
│  ┌─────────────────┐              ┌─────────────────────────────────────────┐   │
│  │ {               │              │ • list_objects_v2()                     │   │
│  │   "stored_      │              │   Prefix: "Redshift/Rel"               │   │
│  │    procedure_   │              │ • get_object()                          │   │
│  │    name": "...", │              │   Read first Rel*.txt file found       │   │
│  │   "parameters": │              │ • Parse content line by line            │   │
│  │    [...],       │              └─────────────────────────────────────────┘   │
│  │   "cluster_     │                                                            │
│  │    identifier": │              3. Redshift Operations                        │
│  │    "...",       │              ┌─────────────────────────────────────────┐   │
│  │   "database":   │              │ • execute_statement()                   │   │
│  │    "..."        │              │   For each procedure in file            │   │
│  │ }               │              │ • describe_statement()                  │   │
│  └─────────────────┘              │   Poll for completion (max 300s)       │   │
│                                   │ • Build CALL statements dynamically    │   │
│                                   └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Configuration & Environment                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Environment Variables:           Timeouts & Retries:                          │
│  ┌─────────────────────────┐     ┌─────────────────────────────────────────┐   │
│  │ • AWS_DEFAULT_REGION    │     │ • Connection timeout: 10s              │   │
│  │ • CLUSTER_ID            │     │ • Read timeout: 10s                    │   │
│  │ • DATABASE              │     │ • Max retries: 2                       │   │
│  │ • DB_USER               │     │ • Query completion wait: 300s          │   │
│  └─────────────────────────┘     └─────────────────────────────────────────┘   │
│                                                                                 │
│  Error Handling:                  Response Format:                             │
│  ┌─────────────────────────┐     ┌─────────────────────────────────────────┐   │
│  │ • File not found        │     │ • statusCode: 200/500                  │   │
│  │ • Execution failures    │     │ • execution_results[]                  │   │
│  │ • Timeout handling      │     │ • total_procedures                     │   │
│  │ • Individual proc fails │     │ • successful_procedures                │   │
│  └─────────────────────────┘     └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Execution Flow                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Step 1: Initialize Clients                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ boto3.client('s3') + boto3.client('redshift-data')                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│  Step 2: Find Rel* Files                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ list_objects_v2(Bucket='daab-lab-jfr-datalake', Prefix='Redshift/Rel') │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│  Step 3: Read & Parse Content                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ get_object() → decode('utf-8') → split('\n') → filter non-empty         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│  Step 4: Execute Each Procedure                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ FOR each line:                                                          │   │
│  │   • Build CALL statement                                                │   │
│  │   • execute_statement()                                                 │   │
│  │   • wait_for_completion()                                               │   │
│  │   • Collect results                                                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│  Step 5: Return Aggregated Results                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ JSON response with execution status for each procedure                  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. **S3 Integration**
- Bucket: `daab-lab-jfr-datalake`
- Path: `Redshift/Rel*.txt`
- Automatically finds first matching file

### 2. **Lambda Function**
- Name: `RedshiftS3SP2`
- Runtime: Python
- Handles multiple stored procedures sequentially

### 3. **Redshift Integration**
- Cluster: `daab-redshift-cluster-jr-bedrock`
- Database: `dev`
- User: `awsuser`
- Uses `redshift-data` API for serverless execution

### 4. **Error Resilience**
- Individual procedure failure tracking
- Timeout handling (300s max wait)
- Detailed error reporting
- Graceful degradation

### 5. **Response Structure**
```json
{
  "statusCode": 200,
  "body": {
    "message": "Executed N stored procedures successfully",
    "total_procedures": N,
    "successful_procedures": M,
    "execution_results": [
      {
        "procedure_number": 1,
        "procedure_name": "procedure_name",
        "query_id": "uuid",
        "status": "FINISHED",
        "sql_executed": "CALL procedure_name();"
      }
    ],
    "s3_content": "raw file content"
  }
}
```