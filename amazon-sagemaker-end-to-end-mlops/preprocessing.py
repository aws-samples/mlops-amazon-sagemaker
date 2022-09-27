import argparse
import os

import numpy as np
import pandas as pd

# Helper method
def process(df):
    # Add two new indicators
    df["no_previous_contact"] = (df["pdays"] == 999).astype(int)
    df["not_working"] = df["job"].isin(["student", "retired", "unemployed"]).astype(int)
    columns = list(df.columns)
    
    toremove = ["emp.var.rate", "cons.price.idx", "cons.conf.idx", "euribor3m", "nr.employed"]
    columns = [x for x in columns if x not in toremove]
    
    # Keeping only columns that we need
    df = df[columns]
    
    # One hot encode
    df=pd.get_dummies(df)
    df = pd.concat([df['y_yes'], df.drop(['y_no', 'y_yes'], axis=1)], axis=1)
    df = df.sample(frac=1).reset_index(drop=True)
    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", type=str, default="/opt/ml/processing")
    args, _ = parser.parse_known_args()
    
    base_dir = args.input_path

    df = pd.read_csv(
        f"{base_dir}/input/bank-additional-full.csv",
        header=0
    )
    
    # Call the helper method
    df = process(df)
    
    train, validation, test = np.split(df, [int(.7*len(df)), int(.85*len(df))])

    train.to_csv(f"{base_dir}/train/train.csv", header=False, index=False)
    validation.to_csv(f"{base_dir}/validation/validation.csv", header=False, index=False)
    test.to_csv(f"{base_dir}/test/test.csv", header=False, index=False)
