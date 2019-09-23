# 2. MLOps: Bring-Your-Own-Algorithm

In this section of the workshop, we will focus on building a pipeline using a model trained on SageMaker bringing your own container/algorithm. 

Applying DevOps practices to Machine Learning (ML) workloads is a fundamental practice to ensure models are deployed using a reliable and consistent process as well as to increase overall quality.   DevOps is not about automating the deployment of a model.  DevOps is about applying practices such as Continuous Integration(CI) and Continuous Delivery(CD) to the model development lifecycle.  CI/CD relies on automation; however, automation alone is not synonymous with DevOps or CI/CD.  

In this lab, you will create a deployment pipeline utilizing AWS Development Services and SageMaker to demonstrate how CI/CD practices can be applied to machine learning workloads.  There is no one-size-fits-all model for creating a pipeline; however, the same general concepts explored in this lab can be applied and extended across various services or tooling to meet the same end result.  

In this lab, the use case we will focus on will be bring-your-own-algorithm for training and deploying on SageMaker.  We will combine this use case with implementing a base reference MLOps pipeline.

-----

## Workshop Contents

For this portion of the workshop, we will be building the following pipeline:  



-------
## Prerequisite

1) AWS Account & Administrator Access
2) Please use North Virginia, **us-east-1** for this workshop


------

## Lab Overview

This lab is based on the [scikit_bring_your_own](https://github.com/awslabs/amazon-sagemaker-examples/blob/master/advanced_functionality/scikit_bring_your_own/scikit_bring_your_own.ipynb) SageMaker example notebook.  Please reference the notebook for detailed description on the use case as well as the custom code for training, inference, and creating the docker container for use with SageMaker.  Although Amazon SageMaker now has native integrations for [Scikit](https://aws.amazon.com/blogs/machine-learning/amazon-sagemaker-adds-scikit-learn-support/), this notebook example does not rely on those integrations so is representative of any BYO* use case.  

Using the same code (with some minor modifications) from the SageMaker example notebook, we will package the code into a source control repository, [AWS CodeCommit](https://aws.amazon.com/codecommit/), for version control.  We will setup a pipeline to trigger automatic training and deployment when changes are made to the code.  In the lab we will utilize [AWS Development Services](https://aws.amazon.com/products/developer-tools/); however, the capabilities performed by these services can also be substituted with existing tooling where applicable.  

This lab will walk you through the steps required to:

• Setup a base pipeline responsible for orchestration of workflow to build and deploy custom ML models to target environments

•	Create logic, in this case Lambda functions, to execute the necessary steps within the orchestrated pipeline required to build, train, and host ML models in an end-to-end pipeline

The same [extensions noted](../1-Built-In-Algorithm/README.md) in the Built-In-Algorithm can be applied to a base pipeline similar to this to continue to mature the pipeline.  

For this lab, we will use the steps outlined in this document combined with two [CloudFormation](https://aws.amazon.com/cloudformation/) templates to create your pipeline.   CloudFormation is an AWS service that allows you to model your entire infrastructure using YAML/JSON templates.   The use of CloudFormation is included not only for  simplicity in lab setup but also to demonstrate the capabilities and benefits of Infrastructure-as-Code(IAC) and Configuration-as-Code(CAC).  We will also utilize SageMaker Notebook Instances as our lab environment to ensure a consistent experience.

## **IMPORTANT:  There are steps in the lab that assume you are using N.Virginia (us-east-1).  Please use us-east-1 for this workshop** 

---

## Step 1: Workshop Preparation 

In this step, you will launch a CloudFormation template using the file 01.CF-MLOps-BYO-Lab-Prep.yml provided as part of workshop materials.  This CloudFormation template accepts a single input parameter, **your-initials**,  that will be used to setup base components including:

-	**CodeCommit Repository:** CodeCommit repository that will act as our source code repository containing assets required for building our custom docker image.

-	**S3 Bucket for Lambda Function Code:** S3 bucket that we will use to stage Lambda function code that will be deployed by a secondary CloudFormation template executed in a later step.

-  **SageMaker Notebook Instance:**  We will use a SageMaker Notebook Instance as a local development environment to ensure a consistent lab environment experience. 

### Steps:

To launch the setup of the resources above using CloudFormation:

1) Download this git repository by either cloning the repository or downloading the *zip

2) Login to the [AWS Console](https://https://console.aws.amazon.com/) and enter your credentials

3) Under **Services**, select [CloudFormation](https://console.aws.amazon.com/cloudformation)

4) Click **Create Stack** buttton

5) Under **Select Template**:
    * Click radio button next to 'Upload a template to Amazon S3', then click **Browse...**

    * From the local repository cloned to your machine in step 1, select the file called ./2-Bring-Your-Own/01.CF-MLOps-BYO-Lab-Prep.yml

    * Click **Open**

6) Under **Specify Stack Details**, enter: 

   * **Stack Name**: MLOps-BYO-WorkshopSetup 

   *  **UniqueID**: Enter *yourinitials* in lower case (Example: jdd)
   
      **IMPORTANT: Use a 3-character initial as shown above**

   ![BYO Workshop Setup](images/CF-LabSetup-1-BYO.png)

7) Click **Next**

8) Under **Options**, leave all defaults and click '**Next**'

9) Under **Review**, scroll to the bottom and check the checkbox acknowledging that CloudFormation might create IAM resources and custom names, then click **Create**

![BYO Workshop Setup](images/CF-LabSetup-2-BYO.png)

10) You will be returned to the CloudFormation console and will see your stack status '**CREATE_IN_PROGRESS**'

11) After a few minutes, you will see your stack Status change to '**CREATE_COMPLETE**'.  You're encouraged to go explore the resources created as part of this initial setup. 


---

## Step 3: Upload Lambda Functions to S3

In this step, you will need to upload pre-packaged Lambda functions to S3.  These Lambda functions will be used at various stages in our MLOps pipeline.  Because we will be using CloudFormation and the [AWS Serverless Application Model (SAM)](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html) to deploy the Lambda functions into our accounts, they must be uploaded be packaged and uploaded to S3 prior to executing our next CloudFormation template.  

The descriptions of each Lambda function are included below:

-	**MLOps-BYO-TrainModel.py.zip:**  This Lambda function is responsible for executing a function that will accept various user parameters from code pipeline (ex. ECR Repository, ECR Image Version, S3 Cleansed Training Data Bucket) and use that information to then setup a training job and train a custom model using SageMaker
-	**MLOps-BYO-GetStatus.py.zip:** This Lambda function is responsible for checking back in on the status of the previous Lambda function.  Because Lambda has an execution time limit, this function ensures that the status of the previous function is accurately capture before moving on to the next stage in the pipeline
-	**MLOps-BYO-DeployModel.py.zip:** This Lambda function is responsible for executing a function that will accept various user parameters from code pipeline (ex. target deployment environment) and use that information to then setup a Configuration Endpoint and Endpoint for hosting the trained model using SageMaker
-	**MLOps-BYO-EvaluateModel.py.zip:** This Lambda function is responsible for running predictions against the trained model by accepting an environment identifier as well as an S3 bucket with sample payload as input from code pipeline.  

### Steps:

1. Download the contents of this git repository to your local machine by either cloning the repository or downloading the zip file.

2. From the AWS console, go to **Services** and select **S3**

3. Find and click on your bucket created in the previous step (mlops-lambda-code-*yourinitials-randomgeneratedID*)

     Example: mlops-lambda-code-jdd-9d055090

     **WARNING:** Make sure you are using the correct bucket that was created by the CloudFormation template with the naming standard above.

4. Click **Upload** in the upper left corner to uploaded pre-packaged lambda functions to your bucket

    * Click **Add files** and select all 4 lambda functions from the 2-Bring-Your-Own/lambda-code/MLOps-BYO*.zip directory in this repository that were download/cloned to your local laptop in step #1

    * Click **Next**

    * Accept defaults on remaining prompts selecting **Next** each time until hitting **Upload** on the final screen

You should now see all of your packaged lambda functions stored as object inside your S3 buckets. The CloudFormation template we launch next will pull the objects from this bucket, using SAM, and deploy them to as functions in the [AWS Lambda Service](https://aws.amazon.com/lambda/).   

![Lambda Functions](images/S3-Lambda-Upload-BYO.png)

---

## Step 4: Build the Base MLOps Pipeline

In this step, you will launch a CloudFormation template using the file 02.CF-MLOps-BYO-BuildPipeline.yml provided as part of workshop materials to build out the pipeline we will be using to train and deploy our models.  This CloudFormation template accepts 4 input parameters that will be used to setup base components including:

**IAM Roles:**

-	**SageMaker Execution Role:**  This role will be utilized with our Lambda function code to establish a trusted relationship between a Lambda function and SageMaker.  The role gets created in the CloudFormation template as well as passed as a Environment Variable to the Lambda Function
-	**Lambda Execution Role:** This role will be utilized by all of the Lambda functions created in this lab.  The role provides access to AWS services access by the Lambda functions including S3, SageMaker, CloudWatch, CodePipeline, ECR
-	**CodeBuildRole:** This role will be utilized by CodeBuild to setup a trusted relationship for AWS services include CodeCommit and ECR.

**Pipeline Resources:** 
- **Lambda Functions:**  Lambda functions utilizing the packaged code uploaded to S3 in the above step.  The Lambda function definitions include the code packaged above as well as specifications related to the Lambda function runtime and configuration. 

- **CodeBuild Job:** CodeBuild job that we will utilize to pull code from CodeCommit and build a Docker image that will be stored in ECR

- **Elastic Container Registry (ECR):** Setup a new Elastic Container Registry that will be used source control for docker image 
	
- **S3 Bucket Model Artifacts:** Setup a versioned S3 bucket for model artifacts

- **CodePipeline Pipeline:**  Set up a CodePipeline that utilizes resources built in the CloudFormation template to create and end-to-end pipeline that we will use to build,train,and deploy mode to target environments



### Steps:

1) Login to the [AWS Console](https://https://console.aws.amazon.com/) and enter your credentials

2) Under **Services**, select [CloudFormation](https://console.aws.amazon.com/cloudformation)

3) Click **Create Stack** buttton

4) Under **Select Template**:
    * Click radio button next to 'Upload a template to Amazon S3', then click **Browse...**

    * From the local repository cloned to your machine in step 1, select the file called ./2-Bring-Your-Own/02.CF-MLOps-BYO-BuildPipeline.yml

    * Click **Open**

    * Click **Next**

3. Under **Specify Stack Details**, enter: 

   * **Stack Name**: MLOps-BYO-BuildPipeline

   * **LambdaFunctionsBucket**: Enter the name of the existing S3 bucket that contains the lambda code we uploaded in the previous step 

       (i.e. mlops-lambda-code-*yourinitials-uniqueid*) 

   *  **RepositoryBranch**: master
   *  **UniqueID**: Enter *yourinitials* in lower case (Example: jdd)
   
      **IMPORTANT: Use a 3-character initial as shown above**

   ![BYO Build Pipeline](images/CF-BuildPipeline-1-BYO.png)

4. Click **Next**

5. Under **Options**, leave all defaults and click **Next**

6. Under **Review**, scroll to the bottom and check the checkbox acknowledging that CloudFormation might create IAM resources and custom names, then click **Create**

7. You will be returned to the CloudFormation console and will see your stack status '**CREATE_IN_PROGRESS**'

8. After a few minutes, you will see your stack Status change to '**CREATE_COMPLETE**'.  You're encouraged to go explore the resources created as part of this initial setup. 


**NOTE: CodePipeline will automatically kickoff after this step; however, since we have not yet added data to the S3 bucket - it will error on the initial kickoff which is expected. Adding data to the S3 bucket is executed in Step 4 below. **

---

## Step 5: Trigger Pipeline Executions

In this step, you will execute several activities within a SageMaker Notebook Instance to:
   
   1. **Simulate Analytics Pipeline Activities**: Push S3 training and validation data to the S3 data bucket (i.e. mlops-data-*yourinitials-uniqueid*)

   2. **Commit training/inference code to CodeCommit**: Using code from this public git repository (./model-code), commit code to the CodeCommit repository to trigger an execution of the CodePipeline.
   
### Steps:

1. Login to the [AWS Console](https://https://console.aws.amazon.com/) and enter your credentials

2. Select **Services** from the top menu, and choose **Amazon SageMaker** 

3. Click on **Notebook Instances**

4. You should see a notebook instance, created by the CloudFormation template, called **MLOps-BYO-Notebook-*yourinitials***.  Click **Open Jupyter**

5. From within your Jupyter notebook, click the **New** dropdown in the top right, then select **Terminal** 

![Notebook Instance Terminal](images/SM-Notebook-Instance-1.png)


6. This will bring up terminal access to prepare files to commit to our code repository.  In the first CloudFormation template executed, 01.CF-MLOps-BYO-Lab-Prep.yml, we setup a SageMaker Notebook Instance with a [Lifecycle Configuration](https://docs.aws.amazon.com/sagemaker/latest/dg/notebook-lifecycle-config.html) to install files on the notebook instance at startup. The notebook instance was also setup with integration to a CodeCommit repository also setup in the same CloudFormation template. 

    *Run the following commands in the terminal* 

         cp -R /home/ec2-user/SageMaker/byo-staging/* /home/ec2-user/SageMaker/mlops-codecommit-byo/


7. Go back to your notebook instance, and click on the 'mlops-codecommit-byo' file under **Files**.  You should now see several files (shown below) which we will use for lab activities.  Within that same folder is a notebook we will be using for the remainder of the workshop called **03.MLOps-BYO-LabNotebook.ipynb**.  

![SM Notebook](images/SM-Notebook-Instance-2.png)

8. Click on that notebook, and it will bring you into your Jupyter Notebook instance environment.  

![SM Notebook2](images/SM-Notebook-Instance-3.png)

9. The remainder of the workshop will be conducted inside the Jupyter Notebook instance.  If you are not familiar with working inside notebook instance environments, the main items you will need to know for this workshop are below: 

   * To execute the current code cell, you can click **Run** on the top menu or Shift + Enter

   * **IMPORTANT: EXECUTE THE CELLS IN ORDER, WAITING FOR THE PREVIOUS TO SUCCESSFULLY COMPLETE BEFORE EXECUTING THE NEXT**.   A cell has completed execution when there is a number in the bracked next to the cell as shown below.   If the cell is still executing, you will see [*]


---

## Step 6: Clean-Up

In addition to the steps for clean-up noted in your notebook instance, please execute the following clean-up steps.  Note: These steps can be automated and/or done programmatically but doing manual clean to enforce what was created during the workshop. 

1. Login to the [AWS Console](https://https://console.aws.amazon.com/) and enter your credentials   

2. Select **Services** from the top menu, and choose **Amazon SageMaker**

   **Notebook Instance**
   * Go to **Notebook Instances** on the left hand menu, select your notebook instance by selecting the radio button next to it.

   *  Select **Actions** and then **Stop** from the dropdown list

   **Endpoints**
   * Go to **Inference / Endpoints** on the left hand menu, click the radio button next to each endpoint. 

   * Select **Actions** and then **Delete**, then confirm delete hitting the **Delete** button. 

3. Select **Services** from the top menu, and choose **S3**

    * Delete all S3 buckets created for this workshop with the following naming convention: 
      - mlops-*
    
    * Click the box next to each bucket and click **Delete** -> confirm deletion
       
       

4. Select **Services** from the top menu, and choose **CloudFormation**

   * For the two stacks that were created in this workshop (MLOps-*), click the checkbox next to the stack.  Select **Actions** , then **Delete Stack**
