import json
import os
import tempfile

import boto3
from boto3.session import Session

from time import gmtime, strftime

code_pipeline = boto3.client('codepipeline')


def lambda_handler(event, context):
    try:
        ##Add timestamp to the jobname to make the endpoint unique.
        jobName = "datascience-project-" + strftime("%Y-%m-%d-%H-%M-%S", gmtime())

        ##Get the region name
        session = boto3.session.Session()
        region = session.region_name

        ##Get the model to be deployed
        objectKey = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']
        print("[INFO]Object:", objectKey)

        bucketname = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
        print("[INFO]Bucket:", bucketname)

        print("[INFO]Creating new endpoint configuration")
        configText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        config_param = json.loads(configText)

        event['stage'] = 'Deployment'
        event['status'] = 'Creating'

        endpoint_environment = config_param["EndpointConfigName"]
        ##TODO : This needs to come the pipeline, not hardcoded.
        # endpoint_environment="Tools"
        # endpoint_environment = "Stage"
        print("[INFO]Endpoint environment:", endpoint_environment)
        initial_variant_weight = config_param['InitialVariantWeight']
        print('[INFO]INITIAL_VARIANT_WEIGHT:', initial_variant_weight)

        trainingImage = config_param["TrainingImage"]

        modelArtifact = 'https://{}.s3-{}.amazonaws.com/{}'.format(bucketname, region, objectKey)
        print("Model artifact is ", modelArtifact)

        # endpoint_environment determines to which environment the model should be deployed.
        # valid values are 'Tools','Stage

        if endpoint_environment == 'Tools':
            print("Will deploy to tools account")
            sagemaker = boto3.client('sagemaker')

            print(
                "[INFO]Environment Input is Tools so creating model, endpoint_config and endpoint in the tools account")

            # Role to pass to SageMaker training job that has access to training data in S3, etc
            sagemakerRole = os.environ['SageMakerExecutionRole']

            create_model(sagemaker, sagemakerRole, jobName, trainingImage, modelArtifact)
            endpoint_config_name = jobName + '-' + endpoint_environment
            print("[INFO]EndpointConfigName:", endpoint_config_name)
            event['message'] = 'Creating Endpoint Hosting {} started.'.format(endpoint_config_name)

            create_endpoint_config(sagemaker, jobName, endpoint_config_name, config_param, initial_variant_weight)

            create_endpoint(sagemaker, endpoint_config_name)

            event['models'] = 'ModelName:"'.format(jobName)
            event['status'] = 'InService'
            event['endpoint'] = endpoint_config_name
            event['endpoint_config'] = endpoint_config_name
            event['job_name'] = jobName
            event['endpoint_environment'] = endpoint_environment

            write_job_info_s3(event)
            put_job_success(event)

        elif endpoint_environment == 'Stage':
            print("Will deploy to stage account")
            # This will be a cross account model deployment.
            # First download the model artifact and transfer it to stage account.

            ##Download to local.
            s3 = boto3.client('s3')
            downloaded_model_artifact = "/tmp/model.tar.gz"
            s3.download_file(bucketname, objectKey, downloaded_model_artifact)
            print("Downloaded model to local.")

            # Use the IAM role that is created in stage account, which gives access Stage accounts
            ##resources to Tools account.
            # This should have been created in the stage account
            stageAccountAccessArn = os.environ['StageAccountAccessRole']
            sagemakerRole = os.environ['SageMakerExecutionRole']

            sts_connection = boto3.client('sts')
            acct_b = sts_connection.assume_role(
                RoleArn=stageAccountAccessArn,
                RoleSessionName="cross_acct_lambda"
            )

            ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
            SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
            SESSION_TOKEN = acct_b['Credentials']['SessionToken']

            # create service client using the assumed role credentials, e.g. S3
            s3 = boto3.client(
                's3',
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_KEY,
                aws_session_token=SESSION_TOKEN,
            )

            print("stage_s3_client", s3)

            ##Copy model artifact to the Stage S3 bucket
            stage_bucket = os.environ['StageAccountS3Bucket']
            stage_objectKey = objectKey
            with open(downloaded_model_artifact, "rb") as f:
                s3.upload_fileobj(f, stage_bucket, stage_objectKey)

            # sagemaker = boto3.client('sagemaker')
            sagemaker = boto3.client(
                'sagemaker',
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_KEY,
                aws_session_token=SESSION_TOKEN,
            )

            print("stage_sagemaker_client", sagemaker)
            modelArtifact = 'https://{}.s3-{}.amazonaws.com/{}'.format(stage_bucket, region, stage_objectKey)

            print("modelArtifact in Stage account ", modelArtifact)

            # Role to pass to SageMaker training job that has access to training data in S3, etc
            sagemakerRole = os.environ['SageMakerExecutionRoleStage']

            create_model(sagemaker, sagemakerRole, jobName, trainingImage, modelArtifact)
            endpoint_config_name = jobName + '-' + endpoint_environment

            create_endpoint_config(sagemaker, jobName, endpoint_config_name, config_param, initial_variant_weight)

            create_endpoint(sagemaker, endpoint_config_name)

            event['models'] = 'ModelName:"'.format(jobName)
            event['status'] = 'InService'
            event['endpoint'] = endpoint_config_name
            event['endpoint_config'] = endpoint_config_name
            event['job_name'] = jobName
            event['endpoint_environment'] = endpoint_environment

            write_job_info_s3(event)
            put_job_success(event)

        else:
            print("[INFO]Environment Input is not equal to Tools or Stage, nothing to do.")
    except Exception as e:
        print(e)
        print('Unable to create deployment job.')
        event['message'] = str(e)
        put_job_failure(event)

    print("Returning the event ", event)

    return event


def create_model(sagemaker, sagemakerRole, jobName, trainingImage, modelArtifact):
    """ Create SageMaker model.
    Args:
        jobName (string): Name to label model with
        trainingImage (string): Registry path of the Docker image that contains the model algorithm
        modelArtifact (string): URL of the model artifacts created during training to download to container
    Returns:
        (None)
    """

    try:
        response = sagemaker.create_model(
            ModelName=jobName,
            PrimaryContainer={
                'Image': trainingImage,
                'ModelDataUrl': modelArtifact
            },
            ExecutionRoleArn=sagemakerRole
        )
    except Exception as e:
        print(e)
        print("ERROR:", "create_model", response)
        raise (e)


def create_endpoint_config(sagemaker, jobName, endpoint_config_name, config_param, initial_variant_weight):
    """ Create SageMaker endpoint configuration.
    Args:
        jobName (string): Name to label endpoint configuration with. For easy identification of model deployed behind endpoint the endpoint name will match the trainingjob
    Returns:
        (None)

        { "InitialInstanceCount": "1", "InitialVariantWeight": "1", "InstanceType": "ml.t2.medium", "EndpointConfigName": "Dev" }
    """
    try:

        deploy_instance_type = config_param['InstanceType']
        initial_instance_count = config_param['InitialInstanceCount']
        print('[INFO]DEPLOY_INSTANCE_TYPE:', deploy_instance_type)
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
        raise (e)


def create_endpoint(sagemaker, endpoint_config_name):
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
        raise (e)


def read_job_info(event):
    tmp_file = tempfile.NamedTemporaryFile()

    objectKey = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']

    print("[INFO]Object:", objectKey)

    bucketname = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
    print("[INFO]Bucket:", bucketname)

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                      aws_secret_access_key=artifactCredentials['secretAccessKey'],
                      aws_session_token=artifactCredentials['sessionToken'])

    s3 = session.resource('s3')

    obj = s3.Object(bucketname, objectKey)

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
    # object = s3.Object(bucketname, objectKey + '/event.json')
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
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])