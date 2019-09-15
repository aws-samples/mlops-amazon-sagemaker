import boto3
import os
import tempfile
import json
from boto3.session import Session

sagemaker = boto3.client('sagemaker')
code_pipeline = boto3.client('codepipeline')

def lambda_handler(event, context):
    try:
        # Read in information from previous get_status job
        previousStepEvent = read_job_info(event)
        jobName = previousStepEvent['TrainingJobName']
        jobArn = previousStepEvent['TrainingJobArn']
        print("[INFO]TrainingJobName:", jobName)
        print("[INFO]TrainingJobArn:", jobArn)
        modelArtifact = previousStepEvent['ModelArtifacts']['S3ModelArtifacts']
        print("[INFO]Model Artifacts:", modelArtifact)
        trainingImage = previousStepEvent['AlgorithmSpecification']['TrainingImage']
        print("[INFO]TrainingImage:", trainingImage)

            
        print("[INFO]Creating new endpoint configuration")
        configText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        config_param = json.loads(configText)
        
        event['stage'] = 'Deployment'
        event['status'] = 'Creating'
        
        endpoint_environment = config_param["EndpointConfigName"]
        print("[INFO]Endpoint environment:", endpoint_environment)
        
        # endpoint_environment can be changed based on specific environment setup
        # valid values are 'Dev','Test','Prod'
        # value input below should be representative to the first target environment in your pipeline (typically Dev or Test)
        if endpoint_environment == 'Dev':
            print("[INFO]Environment Input is Dev so Creating model resource from training artifact")
            create_model(jobName, trainingImage , modelArtifact)
        else:
            print("[INFO]Environment Input is not equal to Dev meaning model already exists - no need to recreate")
 
        endpoint_config_name= jobName+'-'+ endpoint_environment
        print("[INFO]EndpointConfigName:", endpoint_config_name)

        event['message'] = 'Creating Endpoint Hosting"{} started."'.format(endpoint_config_name)
         
        create_endpoint_config(jobName,endpoint_config_name,config_param)
    
        create_endpoint(endpoint_config_name)

        event['models'] = 'ModelName:"'.format(jobName)
        event['status'] = 'InService'
        event['endpoint'] = endpoint_config_name
        event['endpoint_config'] = endpoint_config_name
        event['job_name'] = jobName
        
        write_job_info_s3(event)
        put_job_success(event)
    
    except Exception as e:
        print(e)
        print('Unable to create deployment job.')
        event['message'] = str(e)
        put_job_failure(event)

    return event 
        
def create_model(jobName, trainingImage, modelArtifact):
    """ Create SageMaker model.
    Args:
        jobName (string): Name to label model with
        trainingImage (string): Registry path of the Docker image that contains the model algorithm
        modelArtifact (string): URL of the model artifacts created during training to download to container
    Returns:
        (None)
    """
    # Role to pass to SageMaker training job that has access to training data in S3, etc
    SageMakerRole = os.environ['SageMakerExecutionRole']
    
    try:
        response=sagemaker.create_model(
            ModelName=jobName,
            PrimaryContainer={
                'Image': trainingImage,
                'ModelDataUrl': modelArtifact
            },
            ExecutionRoleArn=SageMakerRole
        )
    except Exception as e:
        print(e)
        print("ERROR:", "create_model", response)
        raise(e)
    
def create_endpoint_config(jobName,endpoint_config_name,config_param):
    """ Create SageMaker endpoint configuration. 
    Args:
        jobName (string): Name to label endpoint configuration with. For easy identification of model deployed behind endpoint the endpoint name will match the trainingjob
    Returns:
        (None)
        
        { "InitialInstanceCount": "1", "InitialVariantWeight": "1", "InstanceType": "ml.t2.medium", "EndpointConfigName": "Dev" }
    """
    try:
        
        deploy_instance_type = config_param['InstanceType']
        initial_variant_weight = config_param['InitialVariantWeight']
        initial_instance_count = config_param['InitialInstanceCount']
        print('[INFO]DEPLOY_INSTANCE_TYPE:', deploy_instance_type)
        print('[INFO]INITIAL_VARIANT_WEIGHT:', initial_variant_weight)
        print('[INFO]INITIAL_INSTANCE_COUNT:', initial_instance_count)

        response = sagemaker.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[
                {
                    'VariantName': 'AllTraffic',
                    'ModelName': jobName,
                    'InitialInstanceCount': initial_instance_count,
                    'InitialVariantWeight': initial_variant_weight,
                    'InstanceType': deploy_instance_type,
                }
            ]
        )
        print("[SUCCESS]create_endpoint_config:", response)
        return response 
    except Exception as e:
        print(e)
        print("[ERROR]create_endpoint_config:", response)
        raise(e)

def check_endpoint_exists(endpoint_name):
    """ Check if SageMaker endpoint for model already exists.
    Args:
        endpoint_name (string): Name of endpoint to check if exists.
    Returns:
        (boolean)
        True if endpoint already exists.
        False otherwise.
    """
    try:
        response = sagemaker.describe_endpoint(
            EndpointName=endpoint_name
        )
        print("[SUCCESS]check_endpoint_exists:", response)
        return True
    except Exception as e:
        print("[ERROR]check_endpoint_exists:", response)
        return False

    
def create_endpoint(endpoint_config_name):
    print("[INFO]Creating Endpoint")
    """ Create SageMaker endpoint with input endpoint configuration.
    Args:
        jobName (string): Name of endpoint to create.
        EndpointConfigName (string): Name of endpoint configuration to create endpoint with.
    Returns:
        (None)
    """
    try:
        response = sagemaker.create_endpoint(
            EndpointName=endpoint_config_name,
            EndpointConfigName=endpoint_config_name
        )
        
        print("[SUCCESS]create_endpoint:", response)
        return response 
        
    except Exception as e:
        print(e)
        print("[ERROR]create_endpoint:", response)
        raise(e)

def update_endpoint(endpoint_name, config_name):
    """ Update SageMaker endpoint to input endpoint configuration. 
    Args:
        endpoint_name (string): Name of endpoint to update.
        config_name (string): Name of endpoint configuration to update endpoint with.
    Returns:
        (None)
    """
    try:
        sagemaker.update_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=config_name
        )
    except Exception as e:
        print(e)
        print("[ERROR]update_endpoint:", e)
        raise(e)

def read_job_info(event):

    tmp_file = tempfile.NamedTemporaryFile()

    #objectKey = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']
    objectKey = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']
   
    print("[INFO]Object:", objectKey)

    bucketname = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
    print("[INFO]Bucket:", bucketname)
    
    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                  aws_secret_access_key=artifactCredentials['secretAccessKey'],
                  aws_session_token=artifactCredentials['sessionToken'])
   
 
    s3 = session.resource('s3')

    obj = s3.Object(bucketname,objectKey)
  
    item = json.loads(obj.get()['Body'].read().decode('utf-8'))
    
    print("Item:", item)
  
    return item
    
def write_job_info_s3(event):
    print(event)

    objectKey = event['CodePipeline.job']['data']['outputArtifacts'][0]['location']['s3Location']['objectKey']

    bucketname = event['CodePipeline.job']['data']['outputArtifacts'][0]['location']['s3Location']['bucketName']

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    artifactName = event['CodePipeline.job']['data']['outputArtifacts'][0]['name']

    # S3 Managed Key for Encryption
    S3SSEKey = os.environ['SSEKMSKeyIdIn']
    
    json_data = json.dumps(event)
    print(json_data)

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                  aws_secret_access_key=artifactCredentials['secretAccessKey'],
                  aws_session_token=artifactCredentials['sessionToken'])
   

    s3 = session.resource("s3")
    #object = s3.Object(bucketname, objectKey + '/event.json')
    object = s3.Object(bucketname, objectKey)
    print(object)
    object.put(Body=json_data, ServerSideEncryption='aws:kms', SSEKMSKeyId=S3SSEKey)
    print('event written to s3')

def put_job_success(event):
    
    print("[SUCCESS]Endpoint Deployed")
    print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])

def put_job_failure(event):  
    print('[ERROR]Putting job failure')
    print(event['message'])
    #code_pipeline.put_job_failure_result(jobId=event['CodePipeline.job']['id'], failureDetails={'message': event['message'], 'type': 'JobFailed'})
    #temporary very ugly fix - stuck in loop and need to adding logic checking existing - it is creating model, endpoint config and endpoint successfully
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])