# Ensure latest version of SageMaker
import os
os.system("pip install -U sagemaker")

import argparse
import numpy as np
import os
import boto3
import pandas as pd
import re
import joblib
import sys
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
import logging
from io import StringIO
# Experiments
from sagemaker.session import Session
from sagemaker.experiments.run import load_run

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))


def parse_args():
    '''
    Parse arguments.
    '''
    parser = argparse.ArgumentParser()
    
    try:
        from sagemaker_training import environment
        env = environment.Environment()
        parser.add_argument('--n_jobs', type=int, default=env.num_cpus)
    except:
        parser.add_argument('--n_jobs', type=int, default=4)


    # hyperparameters sent by the client are passed as command-line arguments to the script
    parser.add_argument('--max_depth', type=int, default=10)
    parser.add_argument('--n_estimators', type=int, default=120)
    
    # read target col
    parser.add_argument('--target_col', type=str, default='price')

    # data directories
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN'))
    parser.add_argument('--validation', type=str, default=os.environ.get('SM_CHANNEL_VALIDATION'))

    # model directory: we will use the default set by SageMaker, /opt/ml/model
    parser.add_argument('--model_dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    
    # parse region
    parser.add_argument('--region', type=str, default='us-west-2')

    return parser.parse_known_args()


def load_dataset(path, target_col):
    '''
    Load dataset.
    '''
    if 'train' in path:
        df_train = pd.read_csv(os.path.join(path, 'train.csv'))
        try:
            x_train = df_train.drop(columns=[target_col])
        except:
            # Assuming first column is target so drop it
            x_train = df_train.drop(df_train.columns[0], axis=1)
        try:
            y_train = df_train[target]
        except:
            y_train = df_train[df_train.columns[0]]
        logger.info(f'x train: {x_train.shape}, y train: {y_train.shape}')
        return x_train, y_train
    else:
        df_validation = pd.read_csv(os.path.join(path, 'validation.csv'))
        try:
            x_validation = df_validation.drop(columns=[target_col])
        except:
            # Assuming first column is target so drop it
            x_validation = df_validation.drop(df_validation.columns[0], axis=1)
        try:
            y_validation = df_validation[target_col]
        except:
            y_validation = df_validation[df_validation.columns[0]]
        logger.info(f'x validation: {x_validation.shape}, y validation: {y_validation.shape}')
        return x_validation, y_validation


def input_fn(request_body, request_content_type):    
    '''
    Parse CSV input and convert to numpy array.
    '''
    if request_content_type == 'text/csv':
        df = pd.read_csv(StringIO(request_body))
        if df.shape[0] == 0:
            df = pd.read_csv(StringIO(request_body), header=None)
        if len(df.columns) == 9: # dataframe contains target
            df = df.iloc[: , :-1] # drop last column
        return df
    

def model_fn(model_dir):
    '''
    Deserialized and return fitted model

    Note that this should have the same name as the serialized model in the main method
    '''
    clf = joblib.load(os.path.join(model_dir, 'model.joblib'))
    return clf


def predict_fn(data, model):
    return model.predict(data)


def start(args):
    '''
    Train a Random Forest Regressor
    '''
    print('Training mode')

    X_train, y_train = load_dataset(args.train, args.target_col)
    X_validation, y_validation = load_dataset(args.validation, args.target_col)

    hyperparameters = {
        'max_depth': args.max_depth,
        'verbose': 1,  # Show all logs
        'n_jobs': args.n_jobs,
        'n_estimators': args.n_estimators,
    }
    print('Training the classifier')
    model = RandomForestRegressor()
    model.set_params(**hyperparameters)
    model.fit(X_train, y_train)
    r_squared = model.score(X_validation, y_validation)
    print('r-squared: {}'.format(r_squared))
    mse = mean_squared_error(y_validation, model.predict(X_validation))
    print('MSE: {}'.format(mse))
    joblib.dump(model, os.path.join(args.model_dir, 'model.joblib'))
    
    # Track experiment
    session = Session(boto3.session.Session(region_name=args.region))
    local_testing = False
    try:
        load_run(sagemaker_session=session)
    except:
        local_testing = True
    if not local_testing: # Track experiment if using SageMaker Training
        with load_run(sagemaker_session=session) as run:
            run.log_metric('r-squared', r_squared)
            run.log_metric('mse', mse)


if __name__ == '__main__':

    args, _ = parse_args()

    start(args)
