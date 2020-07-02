# Enable self service capability for data scientists and integrate with automated MLOps.
End to end machine learning using multiple AWS accounts across multiple environments.


## Overview
[ABSTRACT]

TODO

## Terminology

Few terms to get familiar with before we get started with lab provisioning:

**Tools Account** - An AWS account managed by a centralized IT team, who are responsible for deploying the ML models to production through MLOps code pipeline.

**DataScience Account** - An AWS account used by Data Scientists where they could provision Amazon Sagemaker notebook instance, train ML models, and submit once approved.

**Stage Account** - An AWS account where the code pipeline automatically deploys to and validates the ML models.
**Production Account** - An AWS account where the production applications run. MLOps code pipeline from this lab can be extended to 

**Note:** For this lab, we are are only using Tools, DataScience and Stage accounts. The MLOps pipeline can however be extended to auto-deploy the models to Production environment.

The figure below shows the architecture you will build using this lab.  

![ee-login](images/MLOps_CrossAccount_Architecture.jpg) 

## Steps Involved

**Step-1:** Prepare the Lab environment 
* Configure Service Catalog Product/Portfolio in the Tools Account and share it with a Spoke account (DataScience Account for this lab).
* Configure a Service Catalog Product/Portfolio and other networking resources in the DataScience account and allow access to Data Scientists user/role.
* Configure the stage accounts [Steps]
* Configure MLOps Pipeline in the Tools Account [Steps]

**Step-2:** Data scientists request AWS resources 
* Log in to the DataScience AWS account
* Go to AWS Service Catalog and launch the Sagemaker Notebook instance
* Use the Outputs from AWS Service Catalog and continue with remaining work.

**Step-3:** Data scientists build/train the ML models and submit the final Model.
* Steps to start a notebook
* Steps to build/train the ML model
* Steps to submit the Model to S3 bucket in Tools account

### Step-1 : Prepare the Lab environment

In this section, we will deploy the AWS Service Catalog portfolio in Tools account and share it with the DataScience account, allow Data Scientists to launch Service Catalog resources, and setups the ML Codepiepline. For this lab, we will use CloudFormation to create all the required resources.  

Make a note the AWS Account IDs for the Tools, Datascience and Stage accounts provided to you.  You will use these in the steps below.

**PLEASE READ:** Service Catalog is a regional service. Please make sure that you use the same region for the three accounts you work with.  We will create all lab resources in the AWS region : **us-east-1**

#### Clone or download this git repo
1. Clone or download the zip file of this repo.
```
git clone https://github.com/sirimuppala/cross-account-mlops.git
```
2. If you downloaded the zip, unzip the file.

#### Configure  Tools Account

##### 1.1 Log in  to your Tools Account

1.1.1 Log in to your assigned **Tools Account** using the  credentials provided by your lab administrator.

##### 1.2  Setup ServiceCatalog

1.2.1 Copy and paste the below link in your web browser of your Tools Account
https://us-east-2.console.aws.amazon.com/cloudformation#/stacks/new?stackName=LabSCToolsAccountSetup&templateURL=https://marketplace-sa-resources.s3.amazonaws.com/scmlops/prepare_tools_account.yaml

* In **Create stack** page, choose **Next**
* In **Specify stack details** page, Type in your *DataScience Account Id* under **SpokeAccountID** 
* In **Configure stack options** page, leave the defaults and choose **Next**
* Scroll down **Review LabSCToolsAccountSetup** page to review the selections and choose **Create stack**
* Wait for the stack to deploy resource completely.
* Choose **Outputs** section and note down the values of `MasterPortfolioId`,  `SagemakerProductID`, and `ToolsAccountID` . You will use this information in the next step.
![Outputs Screenshot](images/ToolsAccount_Outputs.png)

1.2.2 Go to Service Catalog Console - https://us-east-2.console.aws.amazon.com/servicecatalog/

* Choose **Portfolios** and **Data Scientists - Sample Portfolio**
* Choose **Actions** --> **Share(1)** to list the accounts the portfolio is shared with. PS: No action needed, just verify the portfolio is shared with *SpokeAccountID*.  (**Question: I still had to enter the SpokeAccount ID.  Is that correct??**)

##### 1.3  Setup MLOps Pipeline

1.3.1 Create a CloudFormation stack to prepare lambda functions to be used by MLOps pipeline

* a. In **Create stack** page, choose **Upload a template file**, Choose file : `tools-account/pipeline/PrepPipeline.yml`; Click **Next**
* b. In **Specify stack details** page, type in `MLOpsPipelinePrep` for Stack Name.
* c. In **Configure stack options** page, leave the defaults and choose **Next**
* d. Scroll down **Review** page to review the selections and choose **Create stack**

This step will create an S3 bucket with name "mlops-bia-lambda-functions-XXXXXXXXXXXX" where the X's represent the AWS Account ID.

1.3.2 From the S3 console, upload lambda zip files from the downloaded git repo code to the S3 bucket created "mlops-bia-lambda-functions-XXXXXXXXXXXX"
* a. Upload tools-account/lambda-code/MLOps-BIA-DeployModel.py.zip
* b. Upload tools-account/lambda-code/MLOps-BIA-GetStatus.py.zip
* c. Upload tools-account/lambda-code/MLOps-BIA-EvaluateModel.py.zip

1.3.3 Create a CloudFormation stack to setup the MLOps Code Pipeline
* a. In **Create stack** page, choose **Upload a template file**, Choose file : `tools-account/pipeline/BuildPipeline.yml`; Click **Next**
* b. In **Specify stack details** page, type in `MLOpsPipeline` for Stack Name.
* c. In **Configure stack options** page, type in 'DataScienceAccountID', 'StageAccountID', an UniqueID  and click **Next**
* d. Scroll down **Review** page to review the selections, select checkbox to acknowledge that IAM resources will be created. Click  **Create stack**
 

#### Configure DataScience  Account

1.4 Log in to your assigned **DataScience Account** using the *Lab Administrator* credentials provided.

##### 1.5 Setup ServiceCatalog
 
1.5.1 Copy and paste the below link in your web browser
https://us-east-2.console.aws.amazon.com/cloudformation#/stacks/new?stackName=LabDSAccountSCSetup&templateURL=https://marketplace-sa-resources.s3.amazonaws.com/scmlops/prepare_datascientist_account.yaml

* a. In **Create stack** page, choose **Next**
* b. Enter the **MasterPortfolioId**, **SagemakerProductID** and **ToolsAccountID** you noted in Step 1.2.1 and choose **Next**.
* c. In **Configure stack options** page, leave the defaults and choose **Next**
* d. Scroll down **Review LabDSAccountSCSetup** page and select **I acknowledge that AWS CloudFormation might create IAM resources** option and choose **Create stack**
* f. Check in the **Outputs** tab, and note down the **SwitchRoleLink** role. You will use the URL link value to switch role as DataScientist in Step-2 below.
![Outputs Screenshot](images/DS-PrepStackOutput.png)

##### 1.7 Configure Stage Account

1.7.1 Log in to your assigned **Stage Account** using the *Lab Administrator* credentials provided.

1.7.2 Create a CloudFormation stack 
* a. In **Create stack** page, choose "Upload a template file", Choose file : stage-account/CreateResources.yml; Click **Next**
* b. In **Specify stack details** page, type in "StageResources" for Stack Name.
* c. In **Configure stack options** page,  type in 'ToolsAccountID' and choose **Next**
* d. Scroll down **Review** page to review the selections and click  **Create stack**


### Step-2 : Data scientists request for AWS resources

In this section, you will login in as a **Data Scientist** and launch a Secure Sagemaker Notebook from the self-service portal powered by AWS Service Catalog.

#### Launch a Sagemaker notebook in Data Scientists account
2.1. Log in to the **Data Scientists** account using the same *Lab Administrator* credentials as you used in step 1.4

2.2. Switch to **DataScientist** role, using the URL you copied in Step 1.5.1(f)
![Outputs Screenshot](images/DS-SwitchRole.png)

2.3. Under **Find services**, search for and choose **Service Catalog**  

2.4. Now you will see a "Amazon Secure Sagemaker" product under **Products list**. 
![SC Login Screen for Data Scientists](images/DS-ScProduct.png)
**PS:** If you don't see a product in your page, ensure you were able to switch the role properly and also in correct region. You can get this information from the ***top-right corner*** of the page.

* Click on the product. Click **LAUNCH PRODUCT** button

* Under **Product version** page, enter a name for your service catalog product and choose **NEXT**

* Select **SagemakerInstance** notebook instance size (small for the purposes of this lab) and select a team name **TeamName**

* In TagOptions page, select a **Value** from drop-down for tag **cost-center** and choose **NEXT**

* Leave defaults in **Notifications** page and choose **NEXT**

* Under **Review** page, review all the options selected and choose **LAUNCH**

* On sucessful completion of the SC product launch, the Data scientist can get the notebook access information on **Outputs** page of the provisioned product (as shown below).
![SC Outputs](images/DS-ProvisionedProduct.png)

* Make note of the BucketName value in the outputs.  You will use this in Step 3.

* Click on **SageMakerNoteBookURL** to open the Notebook interface on the console. Alternatively, Click on **SageMakerNoteBookTerminalURL** to open the Terminal.

You are now accessing the SageMaker notebook instance you self-provisioned as a datascientist.


### Step-3 : Data scientists build/train the ML models. Once ready submit the ML model to kick off MLOps

In this step, you will build an XGBoost model in SageMaker notebook instance provisioned in Step 2.  Once the model is validated and ready to be handed over to IT, you will transfer the model along with test data to IT Tools account.

3.1 Open the "xgboost_abalone.ipynb" in Jupyter. Steps to follow in this step are documented in the "xgboost_abalone.ipynb" itself.  Please read through the narration and execute each cell.   


#### Walkthrough  of the Codepipeline

In the last cell of "xgboost_abalone.ipynb" you transfer the ML model along with test data to **Tools** account, which automatically  kicks off the MLOps pipeline.  

3.2 Login to the **Tools** account.  
3.3 Search for and navigate to "CodePipeline".  
3.4 Click on the pipeline with name starting with "MLOpsPipeline-CodePipeline"
3.5 The pipeline shows multiple stages : Source, DeployModels-Tools, DeployModels-Stage.
3.6 The Source stage was triggered when you copied the model to the Tools S3 bucket.
3.7 The pipeline automatically deploys and validates the model in Tools account and then deploys and validates the model in StageAccount.

While this pipeline is limited to deploying and validating the model in two accounts, this can be extended to more accounts / envrionments, for eg., performance, non-prod and production.


## Conclusion

TODO


## Clean Up (Optional)
Once you are done with the lab, delete the resources created to avoid unnecessary costs.  Please delete the resources in the order specified.

* Stage Account
    1. Empty the S3 bucket with name starting with "mlops-bia-data-model" 
    2. Delete the CloudFormation Stack with name "StageResources"
    3. Delete the Amazon SageMaker Resources - Model, Endpoint Configuration, Endpoint.
    
* DataScience Account
    1. If not already logged in with the "DataScientist" role, login using DataScientist Role.  Terminate the provisioned SageMaker product.
    
    2. Login with the administrator credentials (originally provided by the lab administrator)
        2.1 Delete the CloudFormation stack with name "LabDSAccountSCSetup"
        
*  Tools Account
    1. Delete the CloudFormation Stack with name "LabSCToolsAccountSetup"
    2. Empty the S3 bucket with name starting with "mlops-bia-data-model-" 
    3. Empty the S3 bucket with name stating with "mlops-bia-codepipeline-artifacts"
    4. Empty the S3 bucket with name stating with "mlops-bia-lambda-code-"
    5. Delete the CloudFormation Stack with name "MLOpsPipeline". Wait till the stack is deleted.
    6. Delete the CloudFormation Stack with name "MLOpsPipelinePrep" 


