import boto3
import os
import csv
import botocore
from time import gmtime, strftime
from boto3.session import Session
import json

sagemaker = boto3.client('sagemaker')
code_pipeline = boto3.client('codepipeline')

#use json to send data to model and get back the prediction.
JSON_CONTENT_TYPE = "text/csv"

def lambda_handler(event, context):
    try:
        
        # Read In CodePipeline Data 
        #    - Previous Event Step Information = Resources created in the previous step (Ex. Hosting Endpoint)
        #    - User Parameters: This function accepts the following User Parameters from CodePipeline
        #         { "env": "Dev"}
        #             where: 
        #                  env = Environment, Valid Values (Dev, Test) 

        
        previousStepEvent = read_job_info(event)
        endpointName = previousStepEvent['endpoint']

        evalText = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        test_info = json.loads(evalText)
            
        environment = test_info["env"]
        print("[INFO]ENVIRONMENT:", environment)
        
        # Environment variable containing S3 bucket for data used for validation and/or smoke test
        data_bucket = os.environ['S3DataBucket']
        print("[INFO]DATA_BUCKET:", data_bucket)
                
        if environment == 'Dev':
            print('[INFO]Start Smoke Test')
            key = 'smoketest/smoketest.csv'
            dev_eval = evaluate_model(data_bucket,key,endpointName)
            print('[SUCCESS]Smoke Test Complete')
            write_job_info_s3(event)
            put_job_success(event)
        
        elif environment == 'Test':
            print('[INFO]Start Full Test')
            key = 'validation/validation.csv'
            test_eval = evaluate_model(data_bucket,key,endpointName)
            print('[SUCCESS] Full Test Complete')
            write_job_info_s3(event)
            put_job_success(event)
    
    except Exception as e:
        print("e",e)
        print('[ERROR]Unable to successfully invoke endpoint')
        event['message'] = str(e)
        put_job_failure(event)

    return event 

#Get test/validation data
def evaluate_model(data_bucket, key, endpointName):
    # Get the object from the event and show its content type
    
    s3 = boto3.resource('s3')
    
    download_path='/tmp/tmp.csv'

    try:
        #Use sagemaker runtime to make predictions after getting data
        runtime_client = boto3.client('runtime.sagemaker')

        response = s3.Bucket(data_bucket).download_file(key, download_path)

        csv_data = csv.reader(open(download_path, newline=''))
        
        inferences_input = len(list(csv.reader(open(download_path, newline=''))))
        inference_count = inferences_input
        print("[INFO]Number of predictions on input:", inferences_input)
        
        EndpointInput=endpointName

        print ("[INFO]Endpoint Version:", endpointName)
        
        inferences_processed = 0 
        
        
        for row in csv_data:
            
            
            print("[INFO]Row to format is:", row)
            # Example: ['setosa', '5.0', '3.5', '1.3', '0.3']
            
            # Convert to String          
            formatted_input=csv_formatbody(row)
            print("[INFO]Formatted Input:", formatted_input)
            
            # Convert to Bytes
            invoke_endpoint_body= bytes(formatted_input,'utf-8')
            print("[INFO]invoke_endpoint_body:", invoke_endpoint_body)
            
            response = runtime_client.invoke_endpoint(
                Accept=JSON_CONTENT_TYPE,
                ContentType="text/csv",
                Body=invoke_endpoint_body,
                EndpointName=EndpointInput
                )
            #Response body will be of type "<botocore.response.StreamingBody>"
            #Convert this into string and json for understandable results
            #Check for successful return code (200)
            return_code = response['ResponseMetadata']['HTTPStatusCode']
            print("[INFO]InvokeEndpoint return_code:", return_code)
            
            print('[INFO]Our result for this payload is: {}'.format(response['Body'].read().decode('ascii')))
            
            if return_code != 200:
                event['message'] = str(return_code)
                print("[FAIL] Invoke Endpoint did not return 200 code")
                put_job_failure(event)
                return 'failed'
            elif return_code == 200:
                inferences_processed = inferences_processed + 1
                inference_count = inference_count - 1 
                print('[INFO]Prediction Processed:', inferences_processed)
                print('[INFO]Prediction Remaining on Input:', inference_count)
                
            if inference_count==0:
                return
                
    except botocore.exceptions.ClientError as e:
           print(e)
           print('[FAIL]Unable to get predictions')
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
       
    return string_row
    
def write_job_info_s3(event):
    
    objectKey = event['CodePipeline.job']['data']['outputArtifacts'][0]['location']['s3Location']['objectKey']

    bucketname = event['CodePipeline.job']['data']['outputArtifacts'][0]['location']['s3Location']['bucketName']

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    artifactName = event['CodePipeline.job']['data']['outputArtifacts'][0]['name']

    json_data = json.dumps(event)
    
    print(json_data)
    
    # S3 Managed Key for Encryption
    S3SSEKey = os.environ['SSEKMSKeyIdIn']

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                  aws_secret_access_key=artifactCredentials['secretAccessKey'],
                  aws_session_token=artifactCredentials['sessionToken'])
   

    s3 = session.resource("s3")
    object = s3.Object(bucketname, objectKey + '/event.json')
    object = s3.Object(bucketname, objectKey)
    print(object)
    object.put(Body=json_data, ServerSideEncryption='aws:kms', SSEKMSKeyId=S3SSEKey)

def read_job_info(event):

    objectKey = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']
    bucketname = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']

    artifactCredentials = event['CodePipeline.job']['data']['artifactCredentials']

    session = Session(aws_access_key_id=artifactCredentials['accessKeyId'],
                  aws_secret_access_key=artifactCredentials['secretAccessKey'],
                  aws_session_token=artifactCredentials['sessionToken'])
   
 
    s3 = session.resource('s3')

    obj = s3.Object(bucketname,objectKey)
    
    item = json.loads(obj.get()['Body'].read().decode('utf-8'))
    
    print("[INFO]Previous CodePipeline Job Info Sucessfully Read:", item)
    return item

def put_job_success(event):
    print("[PASS] Smoke Test")
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])
  
def put_job_failure(event):
    
    print('[ERROR]Putting job failure')
    print(event['message'])
    event['successful_inferences'] = 'Inferences Successfully Passed Test'
    code_pipeline.put_job_failure_result(jobId=event['CodePipeline.job']['id'], failureDetails={'message': event['message'], 'type': 'JobFailed'})