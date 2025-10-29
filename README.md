# RedshiftS3SP2 - Lambda Function

AWS Lambda function that automatically executes Redshift stored procedures from S3 files.

## Overview

This Lambda function reads stored procedure definitions from S3 and executes them sequentially on Amazon Redshift. It automatically discovers `Rel*.txt` files in the S3 bucket and processes multiple procedures from a single file.

## Architecture

```
S3 Bucket → Lambda Function → Redshift Cluster
```

- **S3**: `daab-lab-jfr-datalake/Redshift/Rel*.txt`
- **Lambda**: `RedshiftS3SP2`
- **Redshift**: `daab-redshift-cluster-jr-bedrock`

## Features

- Automatic file discovery (finds first `Rel*.txt` file)
- Sequential execution of multiple stored procedures
- Individual procedure error handling
- Comprehensive execution reporting
- Timeout management (300s per procedure)

## Configuration

### Environment Variables
- `CLUSTER_ID`: Redshift cluster identifier
- `DATABASE`: Target database name
- `DB_USER`: Database user
- `AWS_DEFAULT_REGION`: AWS region

### Default Values
- Cluster: `daab-redshift-cluster-jr-bedrock`
- Database: `dev`
- User: `awsuser`
- Region: `us-east-1`

## Usage

### Event Input
```json
{
  "stored_procedure_name": "optional",
  "parameters": [],
  "cluster_identifier": "optional",
  "database": "optional",
  "db_user": "optional"
}
```

### Response Format
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
    ]
  }
}
```

## File Format

S3 files should contain one stored procedure call per line:
```
procedure_name1()
CALL procedure_name2(param1, param2)
procedure_name3
```

## Error Handling

- File not found: Returns available files list
- Individual procedure failures: Continues with remaining procedures
- Timeout: 300s maximum wait per procedure
- Connection issues: 2 retry attempts with 10s timeouts

## Files

- `lambda_function.py`: Main Lambda function code
- `architecture_diagram.md`: Detailed architecture documentation
- `requirements.txt`: Python dependencies

## Dependencies

- `boto3`: AWS SDK for Python
- `json`: JSON processing
- `os`: Environment variables
- `time`: Timeout handling