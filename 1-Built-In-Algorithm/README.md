# 1. MLOps: Built-In-Algorithm

In this section of the workshop, we will focus on building a pipeline using a model trained using an Amazon SageMaker built-in algorithm.  

## Workshop Contents

For this portion of the workshop, we will be building the following pipeline:  

![Built-In-Algorithm Pipeline](../images/bia-architecture.png)


-------
## Prerequisite

1) AWS Account & Administrator Access

--------
## Workshop Setup

First, we will execute a Cloud Formation template to do some initial setup of our environment including creating: 

1) **[AWS CodeCommit](https://aws.amazon.com/codecommit/) Repositories:** AWS CodeCommit repositories that will store our:

     - **Training Config:** configuration code used for training the model (ex. hyperparameters)
    - **Pipeline Lambda Code:** code that we will use for training and deploying our model using Amazon SageMaker
    - **Inference Lambda Code:** code that we will use for evaluation of the model by running predictions against our hosted model 
    *Note: These repositories would alternatively be created in GitHub as an alternative to AWS CodeCommit*

2) **[S3 Data Bucket](https://aws.amazon.com/s3/)** that will store:
    - **Training & Validation Data:** For this workshop we are making the assumption that there is an analytics pipeline sitting in front of our ML pipeline that performs the necessary data transformations and engineering as discovered during data science development lifecycles. This bucket will have versioning enabled. 

3) **S3 Bucket for [Lambda Functions:](https://aws.amazon.com/lambda/)** that will store:

    - **Lambda Pipeline Functions:** Lambda function code that will be used in a later step to build an end-to-end ML pipeline within CodePipeline 

### CloudFormation - Workshop Setup

To launch the setup of the resources above using CloudFormation, use the following link to launch the CloudFormation stack:

[![Launch Stack](https://github.com/seigenbrode/amazon-sagemaker-mlops/blob/master/images/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=ImmersionLab1&templateURL=https://s3-us-west-1.amazonaws.com/amazon-sagemaker-mlops/built-in-algo/builtin-algo-prep.yaml)

1) Under **Stack Details** specify: 

 * **Stack Name**: Recognizable name such as 'MLOps-BuiltIn-Algorithm-WorkshopSetup'

 *  **SuffixID**: Enter *your-initials* [lower case only]

2) Under **Configure stack options**, leave all defaults and click '**Next**'

3) Under **Review**, scroll to the bottom and click '**Create stack'

4) You will be returned to the CloudFormation console and will see your stack status '**CREATE_IN_PROGRESS**'

5) After a few mimutes, you should see your stack Status change to '**CREATE_COMPLETE**'.  You're encouraged to go explore the resources created as part of this initial setup. 


--------
## Lambda Function Upload 

If you have not already done so, [clone this git repository](https://help.github.com/en/articles/cloning-a-repository) to download content to your local computer for upload.  In this step we are going to upload Lambda functions in the format expected by the [*AWS Serverless Application Model**](https://aws.amazon.com/serverless/sam/).  These Lambda functions will be deployed in a future step so in this section we are just staging them for deployment. 

**Steps:**

1. From the AWS Console, click on **Services**, then S3 on the top menu.  

2. Find and click on your bucket created in the previous step (mlops-builtinalgo-lambda-code-<your-initials>) 

3. In the upper left hand corner, click **Upload**

4. Click ‘Add Files’, upload the following files that were provided as part of the class lab materials in the [**PipelineLambdaFunctions**](/PipelineLambdaFunctions) folder:

 - **MLOps-BIA-TrainModel.py.zip:**  This Lambda function is responsible for executing a function that will accept various user parameters from code pipeline (ex. ECR Repository, ECR Image Version, S3 Cleansed Training Data Bucket) and use that information to then setup a training job and train a custom model using SageMaker

  - **MLOps-BIA-GetStatus.py.zip:** This Lambda function is responsible for checking back in on the status of the previous Lambda function.  Because Lambda has an execution time limit, this function ensures that the status of the previous function is accurately capture before moving on to the next stage in the pipeline

 - **MLOps-BIA-DeployModel.py.zip:** This Lambda function is responsible for executing a function that will accept various user parameters from code pipeline (ex. target deployment environment) and use that information to then setup a Configuration Endpoint and Endpoint for hosting the trained model using SageMaker

  -	**MLOps-BIA-EvaluateModel.py.zip:** This Lambda function is responsible for running predictions against the trained model by accepting an environment identifier as well as an S3 bucket with sample payload as input from code pipeline.  
5. After selecting the files above from your local system, click ‘**Next**’

6. For (2) Select Permissions & (3) Set Properties,  accept default values and click ‘**Next**’

7. For (4) Review, review the settings and click ‘**Upload**

8. Validate that you now see all files successfully uploaded to your S3 bucket, then continue to the next step.

--------
## Data Upload 

In this step we are going to upload the data we will be using to train and perform validation on our model.  In a full end-to-end solution setup, this data would be put to your S3 bucket by an analytics pipeline and not manually as we are doing here.

**Steps:**

1. From the AWS Console, click on **Services**, then S3 on the top menu.  

2. Find and click on your bucket created in the previous step (mlops-builtinalgo-data-*your-initials*) 

3. Next, we will create three folders:  

   * Click **+ Create folder**, then type in ‘test’ and hit **Save**
   * Click **+ Create folder**, then type in ‘train’ and hit **Save**
   * Click **+ Create folder**, then type in ‘validation’ and hit **Save**

4.	Next, we will upload data to each of the three folders above using the data provided as part of the workshop materials:
     * From within **EACH** folder we just created above, in the upper left hand corner, click **Upload**, and choose the appropriate *csv file for that folder using the files from the [Data Folder](/Data)
     * Following the step above, the data structure in your S3 data bucket should now look like the following: 

            mlops-builtinalgo-data-<your-initials>/
                    |__test
                       |_ test.csv
                    |__train
                       |_train.csv
                    |__validation
                       |_validation.csv

--------
## Create Pipeline Environment

In this step, you will create a CloudFormation template using the file BuildPipeline.yml provided as part of workshop materials.  This CloudFormation template accepts input parameters that will be used to setup base components of our CI/CD pipeline including: 

*  **IAM Roles:**

   - **SageMaker Execution Role:**  This role will be utilized with our Lambda function code to establish a trusted relationship between a Lambda function and SageMaker.  The role gets created in the CloudFormation template as well as passed as a Environment Variable to the Lambda Function

   -	**Lambda Execution Role:** This role will be utilized by all of the Lambda functions created in this lab.  The role provides access to AWS services access by the Lambda functions including S3, SageMaker, CloudWatch, CodePipeline, ECR

   -	**CodeBuildRole:** This role will be utilized by CodeBuild to setup a trusted relationship for AWS services include CodeCommit and ECR.  

   *NOTE: The roles setup in this lab include FullAccess policies for AWS services to avoid complexities and issues in different lab environments.  Best practice includes refining the policies attached to these roles to ensure fine grained access/authorization on specific resources*

*  **Lambda Functions:**

    -	Lambda functions utilizing the packaged code uploaded to S3 in the above step.  The Lambda function definitions include the code packaged above as well as specifications related to the Lambda function runtime and configuration. 

*  **CodePipeline Pipeline**

    - 	Set up a CodePipeline that utilizes resources built in the CloudFormation template to create and end-to-end pipeline that we will use to build,train,and deploy mode to target environments

**Steps:**

To launch the setup of the above resources using CloudFormation, use the following link to launch the CloudFormation stack 

![Launch][(../images/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=ImmersionLab1&templateURL=https://s3-us-west-1.amazonaws.com/amazon-sagemaker-mlops/built-in-algo/builtin-algo-pipeline.yaml)

1. Under **Specify stack details:**
   *	**Stack name:** Enter mlops-pipeline-builtinalgo-your-initials, replacing *your-initials* with your own initials
 
2. Under **Parameters** this is where we will specify input parameters that will be used by CloudFormation when building out resources.
   
   * **SSEKMSKeyId:** Enter the key id for the AWS Managed Key setup in this account for managing S3 encryption.   This will be used to encrypt objects put to S3 within the Lambda functions. To find this:  Go to Services -> KMS -> AWS Managed keys -> aws/s3.   Copy the arn for the key and paste it into the input parameter for Cloudformation.
 
   * **SuffixID:** Replace *Your-Initials* with your own initials (Ex. sde)

	* **TrainUserParameters:** The input provided in this step is utilized as an input to the CodePipeline action for training the model.  The lambda function is setup to accept a number of configurable input variables.  For this example, we will set the variables by replacing the default with a copy & paste of the values below replacing the values highlighted in yellow with your own initials: 

          { "traincompute": "ml.c4.2xlarge", "model-name": "winequality", "container-path": "811284229777.dkr.ecr.us-east-1.amazonaws.com/xgboost:1", "modelartifactout": "mlops-builtinalgo-model-artifacts-your-initials", "resourceidentifier": "your-initials", "databucket": "mlops-builtinalgo-data-your-initials", "hp-num-round": "20", "num-round": "3", "hp-min-child-weight": "6", "hp-subsample": "0.7"}


    * **SmokeTestUserParameters:** The input provided in this step is utilized as an input to the CodePipeline action for invoking the development endpoint against a small set of data to ensure we are able to perform predictions.  The lambda function is setup to accept a number of configurable input variables.  For this example, we will set the variables by replacing the default with a copy & paste of the values below replacing the values highlighted in yellow with your own initials:

          { "env": "Dev", "s3bucket": "mlops-builtinalgo-data-<your-initials>", "s3key": "/validation/validation.csv" }

   * **FullTestUserParameters:** The input provided in this step is utilized as an input to the CodePipeline action for invoking the development endpoint against the portion of raw data reserved as the test dataset for validating predictions against a larger dataset.  For this example, we will set the variables by replacing the default with a copy & paste of the values below replacing the values highlighted in yellow with your own initials:

         { "env": "Test", "s3bucket": "mlops-builtinalgo-data-<your-initials>"}", "s3key": "/test/test.csv" }

  

3. Under **Configure stack options:**

   * Accept all defaults and click ‘**Next**’

4.	Review your settings, scroll down and click the checkbox at the bottom of the screen agknowledging that you want CloudFormation to create the IAM roles identified in the CloudFormation template.  Click **Create stack**.

5. You will be returned to the Stack execution screen where you can monitor the creation of the resources identified in the CloudFormation template. When the stack is complete you will see a message similar to the one below:

6. At this point in the lab, you are welcome to go in to each of the services listed at the beginning of this step to see the resources that were created as part of the CloudFormation.  

--------
## Test the Pipeline

In this section, we will now try to execute the pipeline that was setup in the preceding steps.   

**Steps:**

1. In the upper-right corner of the AWS Management Console, confirm you are in the desired AWS region (e.g., N.Virginia).  Under Services, select **CodePipeline**

2.	From the left menu, select **Pipelines**

3. You should see a pipeline with your initials, click on that pipeline:

4. You will see the pipeline that was created utilizing CloudFormation.  If your pipeline is not already running, we will want to invoke a manual execution of the pipeline to test the Stages and actions setup.  Click **Release Change** in the upper right hand corner:

5. A popup window will come up confirming you would like to continue, click **Release**
