import boto3
import json

print(f"boto3 version: {boto3.__version__}")

def lambda_handler(event, context):
    evaluation_report = event['evaluation_report']
    evaluation_threshold = event['evaluation_threshold']
    model_url = event['model_url']
    
    print(f"event: {event}")
    
    s3_client = boto3.client('s3')

    bucket = evaluation_report.split('/')[2]
    key = '/'.join(evaluation_report.split('/')[3:])
    s3_clientobj = s3_client.get_object(Bucket=bucket, Key=key)

    for line in s3_clientobj['Body'].iter_lines():
        object = json.loads(line)
        print(f"line: {object}")
        mse = object['regression_metrics']['mse']['value']
        break # Only one line in file
    
    threshold_exceeded = False
    if mse > evaluation_threshold:
        threshold_exceeded = True
    
    return {'model_metric_value': mse,
            'threshold_exceeded': threshold_exceeded,
            'model_url': model_url}