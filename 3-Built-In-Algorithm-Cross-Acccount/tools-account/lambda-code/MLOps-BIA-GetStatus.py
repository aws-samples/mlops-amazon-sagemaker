import boto3
import os
import json
import tempfile
import botocore

from boto3.session import Session

sagemaker = boto3.client('sagemaker')
code_pipeline = boto3.client('codepipeline')

SSEKMSKeyId = os.environ['SSEKMSKeyIdIn']


def lambda_handler(event, context):
    try:

        previousStepEvent = read_job_info(event)
        print('[INFO]previousStepEvent info is:', previousStepEvent)
        jobName = previousStepEvent['job_name']
        print("[INFO]jobName is:", jobName)

        print('TEST')

        eventText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        eventJson = json.loads(eventText)
        print("[INFO]eventJson is:", eventJson)
        stage = eventJson['stage']
        print("[INFO]Stage is:", stage)

        endpointConfigSuffix = eventJson['endpointConfigSuffix']
        print("[INFO]endpointConfigName is:", endpointConfigSuffix)

        if stage == 'Deployment':
            jobName = previousStepEvent['endpoint']
            print("[INFO]Deployment endpoint name is:", jobName)
            endpoint_details = describe_endpoint(endpointConfigSuffix, jobName)
            status = endpoint_details['EndpointStatus']
            print("[INFO]Deployment Status is:", status)
            if status == 'InService':
                print('[SUCCESS]endpoint is in service')
                print(endpointConfigSuffix, endpoint_details)
                event['message'] = 'Deployment completed for endpoint "{}".'.format(endpoint_details)
                put_job_success(event)
            elif status == 'Failed':
                failure_reason = endpoint_details['FailureReason']
                event['message'] = 'Deployment failed for endpoint "{}". {}'.format(jobName, failure_reason)
            elif status == 'RollingBack':
                event[
                    'message'] = 'Deployment failed for endpoint "{}", rolling back to previously deployed version.'.format(
                    jobName)
            elif status == 'Creating':
                print('status is still in creating')
                continue_job_later(event, 'Endpoint Creation still in process.')
        event['status'] = status
        return event
    except Exception as e:
        print(e)
        event['message'] = str(e)
        put_job_failure(event)
        return 'failed'


def describe_endpoint(endpointConfigSuffix, jobName):
    try:
        if endpointConfigSuffix == 'Stage':
            stageAccountAccessArn = os.environ['StageAccountAccessRole']

            sts_connection = boto3.client('sts')

            acct_b = sts_connection.assume_role(
                RoleArn=stageAccountAccessArn,
                RoleSessionName="cross_acct_lambda"
            )

            ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
            SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
            SESSION_TOKEN = acct_b['Credentials']['SessionToken']

            # sagemaker = boto3.client('sagemaker')
            cross_account_sagemaker = boto3.client(
                'sagemaker',
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_KEY,
                aws_session_token=SESSION_TOKEN,
            )

            print("Created cross account sagemaker client")

            response = cross_account_sagemaker.describe_endpoint(
                EndpointName=jobName
            )

        elif endpointConfigSuffix == 'Tools':
            response = sagemaker.describe_endpoint(
                EndpointName=jobName
            )
    except Exception as e:
        print(e)
        print('[ERROR]Unable to describe endpoint.')
        raise (e)
    return response


def put_job_success(event):
    # need to add code to do the s3 upload of the information for the next stage.
    print('[INFO]Putting job success')
    print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])


def put_job_failure(event):
    print('[INFO]Putting job failure')
    print(event['message'])
    code_pipeline.put_job_failure_result(jobId=event['CodePipeline.job']['id'],
                                         failureDetails={'message': event['message'], 'type': 'JobFailed'})


def continue_job_later(event, message):
    # Use the continuation token to keep track of any job execution state
    # This data will be available when a new job is scheduled to continue the current execution
    continuation_token = json.dumps({'previous_job_id': event['CodePipeline.job']['id']})

    print('[INFO]Putting job continuation')
    print(message)
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'], continuationToken=continuation_token)


def read_job_info(event):
    tmp_file = tempfile.NamedTemporaryFile()

    objectKey = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']
    print("[INFO]Object Key:", objectKey)

    bucketname = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
    print("[INFO]Bucket Name:", bucketname)

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                      aws_secret_access_key=artifactCredentials['secretAccessKey'],
                      aws_session_token=artifactCredentials['sessionToken'])

    s3 = session.resource('s3')

    obj = s3.Object(bucketname, objectKey)

    item = json.loads(obj.get()['Body'].read().decode('utf-8'))

    return item


def write_job_info_s3(event, writeData):
    objectKey = event['CodePipeline.job']['data']['outputArtifacts'][0]['location']['s3Location']['objectKey']

    bucketname = event['CodePipeline.job']['data']['outputArtifacts'][0]['location']['s3Location']['bucketName']

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    artifactName = event['CodePipeline.job']['data']['outputArtifacts'][0]['name']
    json_data = json.dumps(writeData, indent=4, sort_keys=True, default=str)

    print(json_data)

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                      aws_secret_access_key=artifactCredentials['secretAccessKey'],
                      aws_session_token=artifactCredentials['sessionToken'])

    s3 = session.resource("s3")
    # object = s3.Object(bucketname, objectKey + '/event.json')
    object = s3.Object(bucketname, objectKey)
    print(object)
    object.put(Body=json_data, ServerSideEncryption='aws:kms', SSEKMSKeyId=SSEKMSKeyId)
    print('[INFO]event written to s3')