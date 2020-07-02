import boto3
import csv
import botocore
from time import gmtime, strftime
from boto3.session import Session
import json
import os
import math

sagemaker = boto3.client('sagemaker')
code_pipeline = boto3.client('codepipeline')
runtime_client = boto3.client('runtime.sagemaker')

# ARN of IAM role Amazon SageMaker can assume to access model artifacts and docker image for deployment
# SageMakerRole = os.environ['SageMakerExecutionRole']


# use json to send data to model and get back the prediction.
JSON_CONTENT_TYPE = "text/csv"


def lambda_handler(event, context):
    try:

        # Read In CodePipeline Data
        #    - Previous Event Step Information = Resources created in the previous step (Ex. Hosting Endpoint)
        #    - User Parameters: This function accepts the following User Parameters from CodePipeline
        #         { "env": "Dev"}
        #             where:
        #                  env = Environment, Valid Values (Dev, Test)
        #

        previousStepEvent = read_job_info(event)
        endpointName = previousStepEvent['endpoint']

        evalText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        test_info = json.loads(evalText)

        environment = test_info["env"]
        print("[INFO]ENVIRONMENT:", environment)

        endpointConfigSuffix = test_info['endpointConfigSuffix']
        print("[INFO]endpointConfigName is:", endpointConfigSuffix)

        # Environment variable containing S3 bucket for data used for validation and/or smoke test
        data_bucket = os.environ['S3DataModelBucket']
        print("[INFO]DATA_BUCKET:", data_bucket)

        # eval = evaluate_model(data_bucket,endpointConfigSuffix,endpointName)

        write_job_info_s3(event)
        put_job_success(event)

        if endpointConfigSuffix == 'Tools':
            key = 'data/abalone.validation'

            print("[INFO]Smoke Test Info:" + environment + " S3 Data Bucket: " + data_bucket + " S3 Prefix/Key: " + key)
            dev_eval = evaluate_model(data_bucket, key, endpointName, endpointConfigSuffix)
            print('[SUCCESS] Smoke Test Complete')

            write_job_info_s3(event)
            put_job_success(event)

        elif endpointConfigSuffix == 'Stage':
            key = 'data/abalone.validation'
            print("[INFO]Full Test Info:" + environment + " S3 Data Bucket: " + data_bucket + " S3 Prefix/Key: " + key)
            test_eval = evaluate_model(data_bucket, key, endpointName, endpointConfigSuffix)
            print('[SUCCESS] Full Test Complete')
            write_job_info_s3(event)
            put_job_success(event)

    except Exception as e:
        print(e)
        print('[ERROR]Unable to successfully invoke endpoint')
        event['message'] = str(e)
        put_job_failure(event)

    return event


def evaluate_model(data_bucket, key, endpointName, endpointConfigSuffix):
    # Get the object from the event and show its content type
    s3 = boto3.resource('s3')
    download_path = '/tmp/tmp.test'

    preds = ""

    try:

        response = s3.Bucket(data_bucket).download_file(key, download_path)

        with open(download_path, 'r') as f:
            payload = f.read().strip()

        labels = [int(line.split(' ')[0]) for line in payload.split('\n')]
        test_data = [line for line in payload.split('\n')]
        preds = batch_predict(test_data, 100, endpointName, 'text/x-libsvm', endpointConfigSuffix)

        print(preds)

    except botocore.exceptions.ClientError as e:
        print(e)
        print('[ERRORUnable to get predictions')
        event['message'] = str(e)
        put_job_failure(e)

    return preds


def do_predict(data, endpoint_name, content_type, endpointConfigSuffix):
    payload = '\n'.join(data)
    if endpointConfigSuffix == 'Tools':

        response = runtime_client.invoke_endpoint(EndpointName=endpoint_name,
                                                  ContentType=content_type,
                                                  Body=payload)
        result = response['Body'].read()
        result = result.decode("utf-8")
        result = result.split(',')
        preds = [float((num)) for num in result]
        preds = [math.ceil(num) for num in preds]
    elif endpointConfigSuffix == 'Stage':

        stageAccountAccessArn = os.environ['StageAccountAccessRole']

        sts_connection = boto3.client('sts')

        acct_b = sts_connection.assume_role(
            RoleArn=stageAccountAccessArn,
            RoleSessionName="cross_acct_lambda"
        )

        ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
        SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
        SESSION_TOKEN = acct_b['Credentials']['SessionToken']

        cross_account_runtime_client = boto3.client(
            'runtime.sagemaker',
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            aws_session_token=SESSION_TOKEN
        )

        print("Created cross account sagemaker runtime client")

        response = cross_account_runtime_client.invoke_endpoint(EndpointName=endpoint_name,
                                                                ContentType=content_type,
                                                                Body=payload)
        result = response['Body'].read()
        result = result.decode("utf-8")
        result = result.split(',')
        preds = [float((num)) for num in result]
        preds = [math.ceil(num) for num in preds]
    return preds


def batch_predict(data, batch_size, endpoint_name, content_type, endpointConfigSuffix):
    items = len(data)
    arrs = []

    for offset in range(0, items, batch_size):
        if offset + batch_size < items:
            results = do_predict(data[offset:(offset + batch_size)], endpoint_name, content_type, endpointConfigSuffix)
            arrs.extend(results)
        else:
            arrs.extend(do_predict(data[offset:items], endpoint_name, content_type, endpointConfigSuffix))
        # sys.stdout.write('.')
    return (arrs)


def write_job_info_s3(event):
    KMSKeyIdSSEIn = os.environ['SSEKMSKeyIdIn']

    objectKey = event['CodePipeline.job']['data']['outputArtifacts'][0]['location']['s3Location']['objectKey']
    bucketname = event['CodePipeline.job']['data']['outputArtifacts'][0]['location']['s3Location']['bucketName']

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']
    artifactName = event['CodePipeline.job']['data']['outputArtifacts'][0]['name']

    json_data = json.dumps(event)

    print(json_data)

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                      aws_secret_access_key=artifactCredentials['secretAccessKey'],
                      aws_session_token=artifactCredentials['sessionToken'])

    s3 = session.resource("s3")
    object = s3.Object(bucketname, objectKey + '/event.json')
    object = s3.Object(bucketname, objectKey)
    print(object)
    object.put(Body=json_data, ServerSideEncryption='aws:kms', SSEKMSKeyId=KMSKeyIdSSEIn)


def read_job_info(event):
    print("[DEBUG]EVENT IN:", event)
    bucketname = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
    print("[INFO]Previous Job Info Bucket:", bucketname)

    objectKey = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']
    print("[INFO]Previous Job Info Object:", objectKey)

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                      aws_secret_access_key=artifactCredentials['secretAccessKey'],
                      aws_session_token=artifactCredentials['sessionToken'])

    s3 = session.resource('s3')

    obj = s3.Object(bucketname, objectKey)

    item = json.loads(obj.get()['Body'].read().decode('utf-8'))

    print("[INFO]Previous CodePipeline Job Info Sucessfully Read:", item)
    return item


def put_job_success(event):
    # print('Putting job success')
    print("[PASS] Smoke Test")
    # print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])


def put_job_failure(event):
    print('Putting job failure')
    print(event['message'])
    event['successful_inferences'] = 'Inferences Successfully Passed Test'
    code_pipeline.put_job_failure_result(jobId=event['CodePipeline.job']['id'],
                                         failureDetails={'message': event['message'], 'type': 'JobFailed'})