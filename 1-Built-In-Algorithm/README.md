# 1. MLOps: Built-In-Algorithm

In this section of the workshop, we will focus on building a pipeline using a model trained using an Amazon SageMaker built-in algorithm, XGBoost.  For the purposes of this workshop, we will utilize an existing Amazon SageMaker example notebook, [xgboost_customer_churn](https://github.com/awslabs/amazon-sagemaker-examples/tree/master/introduction_to_applying_machine_learning/xgboost_customer_churn), in terms of the data and the model being built.   The dataset we use is publicly available and was mentioned in the book Discovering Knowledge in Data by Daniel T. Larose. It is attributed by the author to the University of California Irvine Repository of Machine Learning Datasets.

Take a few minutes to review the notebook to understand what we are going to build and deploy. 

## Workshop Contents

For this portion of the workshop, we will be building the following pipeline:  

![Built-In-Algorithm Pipeline](../images/bia-architecture.png)


-------
## Prerequisite

1) AWS Account & Administrator Access

----
## Lab Overview

This lab will utilize an existing SageMaker algorithm, xgboost, to train a model and deploy it to various environments for validation using a pipeline created in [AWS CodePipeline](https://aws.amazon.com/codepipeline/).  The pipeline will be setup to trigger based on new training data and/or manual execution of the pipeline. 

--------
## Step 1: Workshop Preparation

First, we will execute a Cloud Formation template to do some initial setup of our environment including creating: 

1) **[AWS CodeCommit](https://aws.amazon.com/codecommit/) Repositories:** AWS CodeCommit repositories that will store our:

     - **Training Config:** configuration code used for training the model (ex. hyperparameters)
    - **Pipeline Lambda Code:** code that we will use for training and deploying our model using Amazon SageMaker
    - **Inference Lambda Code:** code that we will use for evaluation of the model by running predictions against our hosted model 
    *Note: These repositories would alternatively be created in GitHub as an alternative to AWS CodeCommit* 

2) **S3 Bucket for [Lambda Functions:](https://aws.amazon.com/lambda/)** that will store:

    - **Lambda Pipeline Functions:** Lambda function code that will be used in a later step to build an end-to-end ML pipeline within CodePipeline 

### Steps:

To launch the setup of the resources above using CloudFormation, use the following link to launch the CloudFormation stack:

[![Launch Stack](../images/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=ImmersionLab1&templateURL=https://s3-us-east-1.amazonaws.com/amazon-sagemaker-devops-with-ml/master/builtin-algo-prep.yaml)

1) Under **Stack Details** specify: 

     * **Stack Name**: Recognizable name such as 'MLOps-BIA-WorkshopSetup'

     *  **UniqueID**: Enter *yourinitials* in lower case only [Example: jdd]

2) Under **Configure stack options**, leave all defaults and click '**Next**'

3) Under **Review**, scroll to the bottom and check the checkbox acknowledging that CloudFormation might create IAM resourcxes and custom names, then click **Create**

4) You will be returned to the CloudFormation console and will see your stack status '**CREATE_IN_PROGRESS**'

5) After a few mimutes, you should see your stack Status change to '**CREATE_COMPLETE**'.  You're encouraged to go explore the resources created as part of this initial setup. 


--------
## Step 2: Lambda Function Upload 

In this step, you will need to upload pre-packaged Lambda functions to S3. These Lambda functions will be used at various stages in our MLOps pipeline. Because we will be using CloudFormation and the AWS Serverless Application Model (SAM) to deploy the Lambda functions into our accounts, they must be uploaded be packaged and uploaded to S3 prior to executing our next CloudFormation template.


**Steps:**

1. From the AWS Console, click on **Services**, then S3 on the top menu.  

2. Find and click on your bucket created in the previous step (mlops-bia-lambda-code-*yourinitials-randomid*) 

3. In the upper left hand corner, click **Upload**

4. Click ‘Add Files’, upload the following files that were provided as part of the class lab materials in the [**/lambda-code**](./lambda-code) folder:

 - **MLOps-BIA-TrainModel.py.zip:**  This Lambda function is responsible for executing a function that will accept various user parameters from code pipeline (ex. type of compute, volume size, number of training instances, algorithm name) and use that information to then setup a training job and train a model using SageMaker

  - **MLOps-BIA-GetStatus.py.zip:** This Lambda function is responsible for checking back in on the status of the previous Lambda function.  Because Lambda has an execution time limit, this function ensures that the status of the previous function is accurately capture before moving on to the next stage in the pipeline

 - **MLOps-BIA-DeployModel.py.zip:** This Lambda function is responsible for executing a function that will accept various user parameters from code pipeline (ex. target deployment environment) and use that information to then setup a Configuration Endpoint and Endpoint for hosting the trained model using SageMaker

  -	**MLOps-BIA-EvaluateModel.py.zip:** This Lambda function is responsible for running predictions against the trained model by accepting an environment identifier as well as an S3 bucket with sample payload as input from code pipeline.  

5. After selecting the files above from your local system, click ‘**Next**’

6. For (2) Select Permissions & (3) Set Properties,  accept default values and click ‘**Next**’

7. For (4) Review, review the settings and click ‘**Upload**

8. Validate that you now see all files successfully uploaded to your S3 bucket, then continue to the next step.

--------
## Step 3: Create Pipeline Environment

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

*  **S3 Data Bucket** 
    - **Training & Validation Data:** For this workshop we are making the assumption that there is an analytics pipeline sitting in front of our ML pipeline that performs the necessary data transformations and engineering as discovered during data science development lifecycles. This bucket will have versioning enabled.

**Steps:**

To launch the setup of the above resources using CloudFormation, use the following link to launch the CloudFormation stack 

[![Launch Stack](../images/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=ImmersionLab1&templateURL=https://s3-us-east-1.amazonaws.com/amazon-sagemaker-devops-with-ml/master/builtin-algo-buildpipeline.yaml)

1. Under **Specify stack details:**
   *	**Stack name:** MLOps-BIA-BuildPipeline
 
2. Under **Parameters** this is where we will specify input parameters that will be used by CloudFormation when building out resources.
   
   * **LambdaFunctionsBucket:** Enter the name of the existing S3 bucket that contains the lambda code we uploaded in the previous step

           (i.e. mlops-lambda-code-yourinitials-uniqueid)

   * **RepositoryBranch:** master

   * **UniqueID:** Enter yourinitials in lower case (Example: jdd)
  

3. Under **Configure stack options:**

   * Accept all defaults and click ‘**Next**’

4.	Review your settings, scroll down and click the checkbox at the bottom of the screen agknowledging that you want CloudFormation to create the IAM roles identified in the CloudFormation template.  Click **Create**.

5. You will be returned to the CloudFormation console and will see your stack status **'CREATE_IN_PROGRESS'**

6. After a few minutes, you will see your stack Status change to **'CREATE_COMPLETE'**. You're encouraged to go explore the resources created as part of this initial setup.


---

## Step 4: Clean-Up

In addition to the steps for clean-up noted in your notebook instance, please execute the following clean-up steps:
1. Login to the [AWS Console](https://https://console.aws.amazon.com/) and enter your credentials

2. Select **Services** from the top menu, and choose **Amazon SageMaker**

   * Go to **Notebook Instances**, select your notebook instance by selecting the radio button next to it.

   * Select **Actions** and then **Stop** from the dropdown list

3. Select **Services** from the top menu, and choose **CloudFormation**

3. For the two stacks that were created in this workshop (MLOps-*), click the checkbox next to the stack.  Select **Actions** , then **Delete Stack**
