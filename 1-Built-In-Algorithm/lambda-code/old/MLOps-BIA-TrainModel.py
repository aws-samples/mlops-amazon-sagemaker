import boto3
import os
import json
import datetime
from time import gmtime, strftime
from boto3.session import Session

region = boto3.session.Session().region_name


SageMakerRole = os.environ['SageMakerExecutionRole']
SSEKMSKeyIdIn = os.environ['SSEKMSKeyIdIn']

sagemaker = boto3.client('sagemaker')
code_pipeline = boto3.client('codepipeline')

data_prefix = 'train'
artifact_bucket = 'amlops-model-artifacts'


def lambda_handler(event, context):
    try:
        
        print(event)
             
        train_start = strftime("%Y-%m-%d-%H-%M-%S", gmtime())
        train_start_calc = datetime.datetime.now()
        
    
        codepipeline_job = event['CodePipeline.job']['id']
        print('CODEPIPELINE_JOB:', codepipeline_job)
        print('TRAIN_START:', train_start)

        userParamText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        user_param = json.loads(userParamText)
        uniqueID = user_param['resourceidentifier']
        print('uniqueID', uniqueID)
        modelName = user_param['model-name']
        job_name = 'mlops-bia-' + modelName + uniqueID + strftime("%Y-%m-%d-%H-%M-%S", gmtime())
        print('job_name', job_name)
        
        container_path = user_param['container-path']
            
        event['job_name'] = job_name
        event['container'] = container_path
        event['stage'] = 'Training'
        event['status'] = 'InProgress'
        event['message'] = 'training job "{} started."'.format(job_name)
        event['s3_output'] = "s3://{}/{}/mlopsr-bia" + uniqueID + "/output".format(artifact_bucket, job_name)
 
        
        create_training_job(user_param, job_name, container_path)
        
        write_job_info_s3(event)
        put_job_success(event, train_start_calc)

    except Exception as e:
        print(e)
        print('ERROR: Unable to create training job.')
        event['message'] = str(e)
        put_job_failure(event)

    return event

def create_training_job(user_param, job_name, container_path):

    try:
        print("USER PARAMETERS:", user_param)
 
        print("S3 Bucket OUTPUT Passing into training params:", artifact_bucket)
        
        data_bucket = user_param['databucket']
        print("S3 Bucket INPUT Passing into training params:", data_bucket)
        data_prefix = 'cleansed-data'
        print("S3 Prefix INPUT Passing into training params:", data_prefix)
       
        
        train_instance_type = user_param['traincompute']
        print('train_instance_type', train_instance_type)
        

        create_training_params = \
        {
            "RoleArn": SageMakerRole,
            "TrainingJobName": job_name,
            "AlgorithmSpecification": {
                "TrainingImage": container_path,
                "TrainingInputMode": "File"
         },
            "ResourceConfig": {
                "InstanceCount": 1,
                "InstanceType": train_instance_type,
                "VolumeSizeInGB": 10
            },
            "InputDataConfig": [
                {
                    "ChannelName": "training",
                    "DataSource": {
                        "S3DataSource": {
                            "S3DataType": "S3Prefix",
                            "S3Uri": "s3://{}/{}/train".format(data_bucket, data_prefix),
                            "S3DataDistributionType": "FullyReplicated"
                        }
                    },
                    "ContentType": "csv",
                    "CompressionType": "None"
                }
            ],
            "OutputDataConfig": {
                "S3OutputPath": "s3://{}/{}/output".format(artifact_bucket, job_name)
            },
            "StoppingCondition": {
                "MaxRuntimeInSeconds": 60 * 60
            }
        }    
        
    
        response = sagemaker.create_training_job(**create_training_params)

    except Exception as e:
        print(str(e))
        raise(e)
        
def write_job_info_s3(event):
    print(event)

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
    object = s3.Object(bucketname, objectKey)
    print(object)
    object.put(Body=json_data, ServerSideEncryption='aws:kms', SSEKMSKeyId=SSEKMSKeyIdIn)
    
    print('SUCCESS: Job Information Written to S3')

def put_job_success(event, train_start_calc):
    
    train_end = strftime("%Y-%m-%d-%H-%M-%S", gmtime())
    train_end_calc = datetime.datetime.now()
    print('TRAIN_END_SUCCESS:', train_end)
    total_train_time = train_end_calc - train_start_calc
    print('TOTAL_TRAIN_TIME:', total_train_time)
    print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])

def put_job_failure(event):
   
    print('Putting job failure')
    print(event['message'])
    code_pipeline.put_job_failure_result(jobId=event['CodePipeline.job']['id'], failureDetails={'message': event['message'], 'type': 'JobFailed'})
    return event   