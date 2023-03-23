import json
import boto3
from sagemaker.model_metrics import ModelMetrics, MetricsSource


def create_model_package_group(model_package_group_name, model_package_group_description, sagemaker_session):
    sagemaker_client = sagemaker_session.sagemaker_client

    # Check if model package group already exists
    model_package_group_exists = False
    model_package_groups = sagemaker_client.list_model_package_groups(NameContains=model_package_group_name)
    for list_item in model_package_groups['ModelPackageGroupSummaryList']:
        if list_item['ModelPackageGroupName'] == model_package_group_name:
            model_package_group_exists = True

    # Create new model package group if it doesn't already exist
    if model_package_group_exists != True:
        sagemaker_client.create_model_package_group(ModelPackageGroupName=model_package_group_name,
                                                  ModelPackageGroupDescription=model_package_group_description)
    else:
        print(f'{model_package_group_name} Model Package Group already exists')


def create_training_job_metrics(estimator, s3_prefix, region, bucket_name, problem_type='regression'):
    # Define supervised learning problem type
    if problem_type == 'regression':
        model_metrics_report = {'regression_metrics': {}}
    elif problem_type == 'classification':
        model_metrics_report = {'classification_metrics': {}}
    
    # Parse training job metrics defined in metric_definitions
    training_job_info = estimator.latest_training_job.describe()
    training_job_name = training_job_info['TrainingJobName']
    metrics = training_job_info['FinalMetricDataList']
    for metric in metrics:
        metric_dict = {metric['MetricName']: {'value': metric['Value'], 'standard_deviation': 'NaN'}}
        if problem_type == 'regression':
            model_metrics_report['regression_metrics'].update(metric_dict)
        if problem_type == 'classification':
            model_metrics_report['classification_metrics'].update(metric_dict)
            
    with open('training_metrics.json', 'w') as f:
        json.dump(model_metrics_report, f)
    
    training_metrics_s3_prefix = f'{s3_prefix}/training_jobs/{training_job_name}/training_metrics.json'
    s3_client = boto3.client('s3', region_name=region)
    s3_client.upload_file(Filename='training_metrics.json', Bucket=bucket_name, Key=training_metrics_s3_prefix)
    training_metrics_s3_uri = f's3://{bucket_name}/{training_metrics_s3_prefix}'
    model_statistics = MetricsSource('application/json', training_metrics_s3_uri)
    model_metrics = ModelMetrics(model_statistics=model_statistics)
    return model_metrics
