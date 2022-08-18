import time
import os
import boto3
import ast
import json

region = boto3.Session().region_name
sm_client = boto3.client('sagemaker', region_name=region)
s3_client = boto3.client('s3', region_name=region)

print(f'boto3 version: {boto3.__version__}')
print(f'region: {region}')


def create_training_job_metrics(training_job_name, training_job_details, s3_bucket,
                                s3_prefix, problem_type='regression'):
    # Define supervised learning problem type
    if problem_type == 'regression':
        model_metrics_report = {'regression_metrics': {}}
    elif problem_type == 'classification':
        model_metrics_report = {'classification_metrics': {}}
    
    # Parse training job metrics defined in metric_definitions
    model_metric_results = training_job_details['FinalMetricDataList']
    for metric in model_metric_results:
        metric_dict = {metric['MetricName']: {'value': metric['Value'], 'standard_deviation': 'NaN'}}
        if problem_type == 'regression':
            model_metrics_report['regression_metrics'].update(metric_dict)
        if problem_type == 'classification':
            model_metrics_report['classification_metrics'].update(metric_dict)
            
    with open('/tmp/training_metrics.json', 'w') as f:
        json.dump(model_metrics_report, f)
    
    training_metrics_s3_prefix = f'{s3_prefix}/step_functions_training_jobs/{training_job_name}/training_metrics.json'
    s3_client.upload_file(Filename='/tmp/training_metrics.json', Bucket=s3_bucket, Key=training_metrics_s3_prefix)
    training_metrics_s3_uri = f's3://{s3_bucket}/{training_metrics_s3_prefix}'
    return training_metrics_s3_uri


def lambda_handler(event, context):
    # Get payload data
    training_job_name = event['training_job_name']
    model_package_group_name = event['model_package_group_name']
    model_package_group_description = event['model_package_group_description']
    problem_type = event['problem_type']
    content_types = event['content_types']
    response_types = event['response_types']
    inference_instances = event['inference_instances']
    transform_instances = event['transform_instances']
    approval_status = event['approval_status']
    s3_bucket = event['s3_bucket']
    s3_prefix = event['s3_prefix']
    
    # Get model info
    training_job_details = sm_client.describe_training_job(TrainingJobName=training_job_name)
    model_url = training_job_details['ModelArtifacts']['S3ModelArtifacts']
    image_uri = training_job_details['AlgorithmSpecification']['TrainingImage']
    training_metrics_s3_uri = create_training_job_metrics(training_job_name, training_job_details,
                                                          s3_bucket, s3_prefix, problem_type=problem_type)
    
    # Create model package 
    try:
        response = sm_client.create_model_package(
            ModelPackageGroupName=model_package_group_name,
            ModelPackageDescription=model_package_group_description,
            ModelApprovalStatus=approval_status,
            InferenceSpecification={
                'Containers': [
                    {
                        'Image': image_uri,
                        'ModelDataUrl': model_url
                    }
                ],
                'SupportedContentTypes': ast.literal_eval(content_types),
                'SupportedResponseMIMETypes': ast.literal_eval(response_types),
            },
            ModelMetrics={
                'ModelQuality': {
                    'Statistics': {
                        'ContentType': 'application/json',
                        'S3Uri': training_metrics_s3_uri
                    }
                }
            }
        )
        model_package_arn = response['ModelPackageArn']
        print(f'ModelPackage Version ARN: {model_package_arn}')
    except Exception as e:
        print(e)