import boto3
import array
from array import *
import csv
import botocore
import itertools
import math
from time import gmtime, strftime
from boto3.session import Session
import json

sagemaker = boto3.client('sagemaker')
code_pipeline = boto3.client('codepipeline')

# ARN of IAM role Amazon SageMaker can assume to access model artifacts and docker image for deployment
SageMakerRole = os.environ['SageMakerExecutionRole']
SSEKMSKeyIdIn = os.environ['SSEKMSKeyIdIn']


#use json to send data to model and get back the prediction.
JSON_CONTENT_TYPE = "text/csv"

def lambda_handler(event, context):
    try:
        
        # Read In CodePipeline Data 
        #    - Previous Event Step Information = Resources created in the previous step (Ex. Hosting Endpoint)
        #    - User Parameters: This function accepts the following User Parameters from CodePipeline
        #         { "env": "Dev", "s3bucket": "amlops-data", "s3key": "cleansed-data/validation/iris.csv" }
        #             where: 
        #                  env = Environment, Valid Values (Dev, Test) 
        #                  s3bucket = Name of bucket with evaluation data
        #                  s3key = S3 Prefix/Key for bucket object
           
        
        previousStepEvent = read_job_info(event)
        endpointName = previousStepEvent['endpoint']

        evalText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        test_info = json.loads(evalText)
            
        environment = test_info["env"]
        print("Environment is:", environment)
        bucket = test_info["s3bucket"]
        key = test_info["s3key"]
        
        print("Test Info:"+ environment + " S3 Data Bucket: " + bucket + " S3 Prefix/Key: " + key)
         
        if environment == 'Dev':
            print('[START] Smoke Test')
            dev_eval = evaluate_model(bucket,key,endpointName)
            print('[SUCCESS] Smoke Test Complete')
            write_job_info_s3(event)
            put_job_success(event)
        
        elif environment == 'Test':
            print('[START] Full Test')
            test_eval = evaluate_model(bucket,key,endpointName)
            print('[SUCCESS] Full Test Complete')
            write_job_info_s3(event)
            put_job_success(event)
    
    except Exception as e:
        print(e)
        print('Unable to successfully invoke endpoint')
        event['message'] = str(e)
        put_job_failure(event)

    return event 

#Get test/validation data
def evaluate_model(bucket, key, endpointName):
    # Get the object from the event and show its content type
    
    s3 = boto3.resource('s3')
    
    download_path='/tmp/tmp.csv'

    try:
        #Use sagemaker runtime to make predictions after getting data
        runtime_client = boto3.client('runtime.sagemaker')

        response = s3.Bucket(bucket).download_file(key, download_path)
    
        csv_data = csv.reader(open(download_path, newline=''))
        
        inferences_processed = len(list(csv.reader(open(download_path, newline=''))))
        inference_count = inferences_processed
        print("Number of predictions on input:", inferences_processed)
        
        EndpointInput=endpointName

        print ("Endpoint Version:", endpointName)
        
        Accurate_Positive_Prediction = 0
        Inaccurate_Positive_Prediction = 0
        Accurate_Negative_Prediction = 0
        Inaccurate_Negative_Prediction = 0
        
        
        for row in csv_data:
            
            print("Row to format is:", row)
            # Example: ['setosa', '5.0', '3.5', '1.3', '0.3']
            
            # Convert to String          
            formatted_input=csv_formatbody(row)
            print("Formatted Input", formatted_input)
            
            # Convert to Bytes
            invoke_endpoint_body= bytes(formatted_input,'utf-8')
            print("invoke_endpoint_body", invoke_endpoint_body)
            
            response = runtime_client.invoke_endpoint(
                Accept=JSON_CONTENT_TYPE,
                ContentType="text/csv",
                Body=invoke_endpoint_body,
                EndpointName=EndpointInput
                )
            #Response body will be of type "<botocore.response.StreamingBody>"
            #Convert this into string and json for understandable results
            print("InvokeEndpoint Response:", response)
            #Check for successful return code (200)
            return_code = response['ResponseMetadata']['HTTPStatusCode']
            print("InvokeEndpoint return_code:", return_code)
            
            print('Our result for this payload is: {}'.format(response['Body'].read().decode('ascii')))
            
            if return_code != 200:
                event['message'] = str(return_code)
                print("[FAIL] Smoke Test")
                put_job_failure(event)
                return 'failed'
            elif return_code == 200:
                print('All Predictions Processed')
    
    except botocore.exceptions.ClientError as e:
        print(e)
        print('Unable to get predictions')
        event['message'] = str(e)
        put_job_failure(e)
        
    return return_code
            
    
#Format Body of inference to match input expected by algorithm
def csv_formatbody(row):
    #print("Row to Format is..", row)
    #Need to convert csv data in from:
    #   ['setosa', '5.0', '3.5', '1.3', '0.3']
    #  TO: 
    #   b'setosa,5.0,3.5,1.3,0.3'
    
    string_row=','.join(str(e) for e in row)
    #print("String representative of row is..", string_row)
    #print ("json body is : ", json.dumps(string_row))
    
    return string_row
    
def write_job_info_s3(event):
    
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
    object.put(Body=json_data, ServerSideEncryption='aws:kms', KMSKeyIdSSE=KMSKeyIdSSEIn)

def read_job_info(event):

    #tmp_file = tempfile.NamedTemporaryFile()
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
    
    print("Previous Job Info Read...")
    return item

def put_job_success(event):
    #print('Putting job success')
    print("[PASS] Smoke Test")
    #print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])
  
def put_job_failure(event):
    
    print('Putting job failure')
    print(event['message'])
    event['successful_inferences'] = 'Inferences Successfully Passed Test'
    code_pipeline.put_job_failure_result(jobId=event['CodePipeline.job']['id'], failureDetails={'message': event['message'], 'type': 'JobFailed'})