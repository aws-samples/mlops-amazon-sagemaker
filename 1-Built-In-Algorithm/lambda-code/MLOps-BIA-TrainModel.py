import boto3
import os
import json
import datetime
from time import gmtime, strftime
from boto3.session import Session

region = boto3.session.Session().region_name

sagemaker = boto3.client('sagemaker')
code_pipeline = boto3.client('codepipeline')

def lambda_handler(event, context):
    try:
        
        print(event)
             
        train_start = strftime("%Y-%m-%d-%H-%M-%S", gmtime())
        train_start_calc = datetime.datetime.now()
    
        codepipeline_job = event['CodePipeline.job']['id']
        print('[INFO]CODEPIPELINE_JOB:', codepipeline_job)
        print('[INFO]TRAIN_START:', train_start)
        
        
        userParamText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        user_param = json.loads(userParamText)
        job_name = 'mlops-bia-xgboost-' + strftime("%Y-%m-%d-%H-%M-%S", gmtime())
        print('[INFO]TRAINING_JOB_NAME:', job_name)
    
        event['job_name'] = job_name
        event['stage'] = 'Training'
        event['status'] = 'InProgress'
        event['message'] = 'training job "{} started."'.format(job_name)
 
        
        
        create_training_job(user_param, job_name)
        
        write_job_info_s3(event)
        put_job_success(event)

    except Exception as e:
        print(e)
        print('[ERROR] Unable to create training job.')
        event['message'] = str(e)
        put_job_failure(event)

    return event

def create_training_job(user_param, job_name):

    try:
        print("[INFO]CODEPIPELINE_USER_PARAMETERS:", user_param)

        # Environment variable containing S3 bucket for storing the model artifact
        model_artifact_bucket = os.environ['ModelArtifactBucket']
        print("[INFO]MODEL_ARTIFACT_BUCKET:", model_artifact_bucket)

        # Environment variable containing S3 bucket containing training data
        data_bucket = os.environ['S3DataBucket']
        print("[INFO]TRAINING_DATA_BUCKET:", data_bucket)

 
        # Role to pass to SageMaker training job that has access to training data in S3, etc
        SageMakerRole = os.environ['SageMakerExecutionRole']
        
        #Get ECR information for BIA
        algo_version = user_param['Algorithm']
        ecr_path = os.environ['AlgoECR']
        container_path = ecr_path + '/' + algo_version
        print('[INFO]Container Path', container_path)
        
        train_instance_type = user_param['traincompute']
        train_volume_size = user_param['traininstancevolumesize']
        train_instance_count = user_param['traininstancecount']
        maxdepth_in = user_param['MaxDepth']
        eta_in = user_param['eta']
        gamma_in = user_param['gamma']
        min_child_weight_in = user_param['MinChildWeight']
        subsample_in = user_param['SubSample']
        silent_in = user_param['Silent']
        objective_in = user_param['Objective']
        num_round_in = user_param['NumRound']

        
        print('[INFO]TRAIN_INSTANCE_TYPE:', train_instance_type)
        print('[INFO]TRAIN_VOLUME_SIZE:', train_volume_size)
        print('[INFO]TRAIN_INSTANCE_COUNT:', train_instance_count)
   

        create_training_params = \
        {
           "AlgorithmSpecification": {
                "TrainingImage": container_path,
                "TrainingInputMode": "File"
            },
            "RoleArn": SageMakerRole,
            "OutputDataConfig": {
                "S3OutputPath": "s3://{}/{}/output".format(model_artifact_bucket, job_name)
            },
            "ResourceConfig": {
                "InstanceCount": train_instance_count,
                "InstanceType": train_instance_type,
                "VolumeSizeInGB": train_volume_size
            },
            "TrainingJobName": job_name,
            "HyperParameters": {
                "max_depth": maxdepth_in,
                "eta": eta_in,
                "gamma": gamma_in,
                "min_child_weight": min_child_weight_in,
                "objective": objective_in,
                "num_round": num_round_in
            },
            "StoppingCondition": {
             "MaxRuntimeInSeconds": 3600
            },
            "InputDataConfig": [
                {
                    "ChannelName": "train",
                    "DataSource": {
                        "S3DataSource": {
                            "S3DataType": "S3Prefix",
                            "S3Uri": "s3://{}/train".format(data_bucket),
                            "S3DataDistributionType": "FullyReplicated"
                        }
                    },
                    "ContentType": "csv",
                    "CompressionType": "None"
                }
            ],
            "OutputDataConfig": {
                "S3OutputPath": "s3://{}/{}/output".format(model_artifact_bucket, job_name)
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
    
    # S3 Managed Key for Encryption
    S3SSEKey = os.environ['SSEKMSKeyIdIn']

    json_data = json.dumps(event)
    print(json_data)

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                  aws_secret_access_key=artifactCredentials['secretAccessKey'],
                  aws_session_token=artifactCredentials['sessionToken'])
   

    s3 = session.resource("s3")
    object = s3.Object(bucketname, objectKey)
    print(object)
    object.put(Body=json_data, ServerSideEncryption='aws:kms', SSEKMSKeyId=S3SSEKey)
    
    print('[SUCCESS]Job Information Written to S3')

def put_job_success(event):
    
    print('[SUCCESS]Training Job started - kicking off next stage in pipeline...')
    print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])

def put_job_failure(event):
   
    print('[FAILURE]Putting job failure')
    print(event['message'])
    code_pipeline.put_job_failure_result(jobId=event['CodePipeline.job']['id'], failureDetails={'message': event['message'], 'type': 'JobFailed'})
    return event
