import json
import boto3
import os
import time
from urllib.parse import unquote_plus

def wait_for_completion(redshift_client, query_id, max_wait=300):
    """Wait for query to complete and return status"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = redshift_client.describe_statement(Id=query_id)
        status = response['Status']
        if status in ['FINISHED', 'FAILED', 'ABORTED']:
            return response
        time.sleep(2)
    return {'Status': 'TIMEOUT'}

def lambda_handler(event, context):
    """Retrieve and execute stored procedure from S3 on Redshift"""
    
    # Log the incoming event for debugging
    print(f"Received event: {json.dumps(event)}")
    
    # Initialize clients
    region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
    config = boto3.session.Config(
        connect_timeout=10,
        read_timeout=10,
        retries={'max_attempts': 2}
    )
    s3_client = boto3.client('s3', region_name=region, config=config)
    redshift_client = boto3.client('redshift-data', region_name=region, config=config)
    
    # Always find and use any Rel* txt file from S3 bucket
    bucket = 'daab-lab-jfr-datalake'
    
    # Find any Rel* txt file in the bucket
    list_response = s3_client.list_objects_v2(Bucket=bucket, Prefix='Redshift/Rel')
    if 'Contents' in list_response:
        rel_files = [obj['Key'] for obj in list_response['Contents'] if obj['Key'].lower().endswith('.txt')]
        if rel_files:
            sp_key = rel_files[0]  # Use first Rel* file found
            print(f"Using Rel* file: {sp_key}")
        else:
            raise Exception("No Rel*.txt files found in s3://daab-lab-jfr-datalake/Redshift/")
    else:
        raise Exception("No files found with prefix Redshift/Rel in bucket")
    
    # Extract other parameters
    sp_name = event.get('stored_procedure_name')
    sp_params = event.get('parameters', [])
    cluster_identifier = event.get('cluster_identifier', os.environ.get('CLUSTER_ID', 'daab-redshift-cluster-jr-bedrock'))
    database = event.get('database', os.environ.get('DATABASE', 'dev'))
    db_user = event.get('db_user', os.environ.get('DB_USER', 'awsuser'))
    
    try:
        # Log S3 details for debugging
        print(f"Attempting to read from S3 - Bucket: {bucket}, Key: {sp_key}")
        
        # List bucket contents to debug
        try:
            list_response = s3_client.list_objects_v2(Bucket=bucket, Prefix='Redshift/', MaxKeys=10)
            if 'Contents' in list_response:
                print(f"Files in Redshift/ folder: {[obj['Key'] for obj in list_response['Contents']]}")
            else:
                print("No files found in Redshift/ folder")
        except Exception as list_error:
            print(f"Error listing bucket contents: {list_error}")
        
        # Retrieve the Rel* file content
        response = s3_client.get_object(Bucket=bucket, Key=sp_key)
        sp_content = response['Body'].read().decode('utf-8').strip()
        print(f"Successfully read S3 content: {sp_content[:100]}...")
        
        # Parse multiple stored procedures from file
        lines = [line.strip() for line in sp_content.split('\n') if line.strip()]
        
        execution_results = []
        all_successful = True
        
        # Execute each stored procedure
        for i, line in enumerate(lines):
            try:
                # Build CALL statement for each line
                if line.upper().startswith('CALL'):
                    call_sql = line if line.endswith(';') else line + ';'
                    proc_name = line.split('(')[0].replace('CALL ', '').replace('call ', '').strip()
                elif '(' in line and ')' in line:
                    call_sql = f"CALL {line}" + (';' if not line.endswith(';') else '')
                    proc_name = line.split('(')[0].strip()
                else:
                    call_sql = f"CALL {line}();"
                    proc_name = line
                
                print(f"Executing procedure {i+1}: {call_sql}")
                
                # Execute stored procedure
                exec_response = redshift_client.execute_statement(
                    ClusterIdentifier=cluster_identifier,
                    Database=database,
                    DbUser=db_user,
                    Sql=call_sql
                )
                
                # Wait for execution to complete
                exec_status = wait_for_completion(redshift_client, exec_response['Id'])
                
                result = {
                    'procedure_number': i + 1,
                    'procedure_name': proc_name,
                    'query_id': exec_response['Id'],
                    'status': exec_status['Status'],
                    'sql_executed': call_sql
                }
                
                if exec_status['Status'] != 'FINISHED':
                    all_successful = False
                    result['error'] = exec_status.get('Error', 'Unknown error')
                
                execution_results.append(result)
                
            except Exception as proc_error:
                all_successful = False
                execution_results.append({
                    'procedure_number': i + 1,
                    'procedure_name': line,
                    'status': 'ERROR',
                    'error': str(proc_error)
                })
        
        return {
            'statusCode': 200 if all_successful else 500,
            'body': json.dumps({
                'message': f'Executed {len(lines)} stored procedures' + (' successfully' if all_successful else ' with some failures'),
                'total_procedures': len(lines),
                'successful_procedures': sum(1 for r in execution_results if r.get('status') == 'FINISHED'),
                'execution_results': execution_results,
                's3_content': sp_content
            })
        }
        
    except Exception as e:
        # Get available files for debugging
        try:
            list_response = s3_client.list_objects_v2(Bucket=bucket, Prefix='Redshift/', MaxKeys=20)
            available_files = [obj['Key'] for obj in list_response.get('Contents', [])] if 'Contents' in list_response else []
        except:
            available_files = ['Unable to list files']
            
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'bucket': bucket,
                'key': sp_key,
                'available_files': available_files
            })
        }