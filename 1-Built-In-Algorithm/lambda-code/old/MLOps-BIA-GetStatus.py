import boto3
import os
import json
import tempfile
import zipfile
import botocore

from boto3.session import Session

sagemaker = boto3.client('sagemaker')
code_pipeline = boto3.client('codepipeline')

SSEKMSKeyId = os.environ['SSEKMSKeyIdIn']


def lambda_handler(event, context):
    try:
        
        previousStepEvent = read_job_info(event)
        print('previousStepEvent info is:', previousStepEvent)
        jobName = previousStepEvent['job_name']
        print("jobName is:", jobName)
        
        
        eventText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        eventJson = json.loads(eventText)
        stage = eventJson['stage']
        print("Stage is:", stage)
        
        
        if stage == 'Training':
            name = jobName
            training_details = describe_training_job(name)
            status = training_details['TrainingJobStatus']
            print('Training job is:', status)
            if status == 'Completed':
                #need to call success
                print('status is completed')
                print(training_details)
                s3_output_path = training_details['OutputDataConfig']['S3OutputPath']
                model_data_url = os.path.join(s3_output_path, name, 'output/model.tar.gz')
                event['message'] = 'Training job "{}" complete. Model data uploaded to "{}"'.format(name, model_data_url)
                event['model_data_url'] = model_data_url
                write_job_info_s3(event, training_details)
                put_job_success(event)
            elif status == 'Failed':
                #need to call failure
                print('status is failed')
                failure_reason = training_details['FailureReason']
                event['message'] = 'Training job failed. {}'.format(failure_reason)
                put_job_failure(event)
            elif status == 'InProgress':
                #need to call continue
                print('status is still in process')
                continue_job_later(event, 'Training job still in process.') 
        elif stage == 'Deployment':
            print("Made it to deploy logic")
            jobName = previousStepEvent['endpoint']
            print("Deployment endpoint name is:", jobName)
            endpoint_details = describe_endpoint(jobName)
            status = endpoint_details['EndpointStatus']
            print("Deployment Status is:", status)
            if status == 'InService':
                print('endpoint is in service')
                print(endpoint_details)
                event['message'] = 'Deployment completed for endpoint "{}".'.format(endpoint_details)
                put_job_success(event)
            elif status == 'Failed':
                failure_reason = endpoint_details['FailureReason']
                event['message'] = 'Deployment failed for endpoint "{}". {}'.format(jobName, failure_reason)
            elif status == 'RollingBack':
                event['message'] = 'Deployment failed for endpoint "{}", rolling back to previously deployed version.'.format(jobName)
            elif status == 'Creating':
                #need to call continue
                print('status is still in creating')
                continue_job_later(event, 'Endpoint Creation still in process.') 
        event['status'] = status
        return event
    except Exception as e:
        print(e)
        event['message'] = str(e)
        put_job_failure(event)
        return 'failed'


def describe_training_job(name):
   
    try:
        response = sagemaker.describe_training_job(
            TrainingJobName=name
        )
    except Exception as e:
        print(e)
        print('Unable to describe training job.')
        raise(e)
    return response
    
def describe_endpoint(jobName):
    try:
        response = sagemaker.describe_endpoint(
            EndpointName=jobName
        )
    except Exception as e:
        print(e)
        print('Unable to describe endpoint.')
        raise(e)
    return response

def put_job_success(event):
   #need to add code to do the s3 upload of the information for the next stage.
    print('Putting job success')
    print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])
  
def put_job_failure(event):
    
    print('Putting job failure')
    print(event['message'])
    code_pipeline.put_job_failure_result(jobId=event['CodePipeline.job']['id'], failureDetails={'message': event['message'], 'type': 'JobFailed'})

def continue_job_later(event, message):
   
    
    # Use the continuation token to keep track of any job execution state
    # This data will be available when a new job is scheduled to continue the current execution
    continuation_token = json.dumps({'previous_job_id': event['CodePipeline.job']['id']})
    
    print('Putting job continuation')
    print(message)
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'], continuationToken=continuation_token)

def read_job_info(event):

    tmp_file = tempfile.NamedTemporaryFile()

    objectKey = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']
    print("Object Key:", objectKey)

    bucketname = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
    print("bucketname:", bucketname)

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                  aws_secret_access_key=artifactCredentials['secretAccessKey'],
                  aws_session_token=artifactCredentials['sessionToken'])
   
 
    s3 = session.resource('s3')

    obj = s3.Object(bucketname,objectKey)
    
    print("Object:", obj)
  
    item = json.loads(obj.get()['Body'].read().decode('utf-8'))
    
    print("Item is:", item)
  
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
    #object = s3.Object(bucketname, objectKey + '/event.json')
    object = s3.Object(bucketname, objectKey)
    print(object)
    object.put(Body=json_data, ServerSideEncryption='aws:kms', SSEKMSKeyId=SSEKMSKeyId)
    print('event written to s3')