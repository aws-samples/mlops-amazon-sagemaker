'''
This Lambda function creates an Endpoint Configuration and deploys a model to an Endpoint. 
The name of the model to deploy is provided via the `event` argument
'''

import json
import boto3

region = boto3.Session().region_name
sm_client = boto3.client('sagemaker', region_name=region)

print(f'boto3 version: {boto3.__version__}')
print(f'region: {region}')


def lambda_handler(event, context):
    """
    Approve the model package for deployment, create a SageMaker model
    """
    
    region = event['region']
    aws_account_id = event['aws_account_id']
    model_package_group_name = event['model_package_group_name']
    instance_count = event['instance_count']
    role_arn = event['role_arn']
    
    # Optional fields
    try:
        model_package_version = event['model_package_version']
    except:
        # Get the latest version
        model_package_version = sm_client.list_model_packages(ModelPackageGroupName=model_package_group_name)['ModelPackageSummaryList'][0]['ModelPackageVersion']
        
    try:
        model_name = event['model_name']
    except:
        model_name = f'{model_package_group_name}-model-{model_package_version}'
    
    model_package_version_arn = f'arn:aws:sagemaker:{region}:{aws_account_id}:model-package/{model_package_group_name}/{model_package_version}'
    print(f'Using model package version ARN: {model_package_version_arn}')
    model_package_details = sm_client.describe_model_package(ModelPackageName=model_package_version_arn)

    realtime_inference_instance_types = model_package_details['InferenceSpecification']['SupportedRealtimeInferenceInstanceTypes']
    
    container_list = [{'ModelPackageName': model_package_version_arn}]
    
    # Approve model package to be used as SageMaker model and for deployment
    sm_client.update_model_package(ModelPackageArn=model_package_version_arn,
                                   ModelApprovalStatus='Approved')
    sm_client.create_model(ModelName=model_name,
                           Containers=container_list,
                           ExecutionRoleArn=role_arn)

    endpoint_name = f'{model_name}-endpoint'
    create_endpoint_config_response = sm_client.create_endpoint_config(
        EndpointConfigName=endpoint_name,
        ProductionVariants=[
            {
                'InstanceType': realtime_inference_instance_types[0],
                'InitialVariantWeight': 1,
                'InitialInstanceCount': instance_count,
                'ModelName': model_name,
                'VariantName': 'AllTraffic',
            }
        ],
    )

    create_endpoint_response = sm_client.create_endpoint(EndpointName=endpoint_name, EndpointConfigName=endpoint_name)
    return {
        'statusCode': 200,
        'body': json.dumps('Created Endpoint!')
    }
