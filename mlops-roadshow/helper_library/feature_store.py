import boto3


sagemaker_client = boto3.client('sagemaker')
boto_session = boto3.Session()
featurestore_runtime = boto_session.client(service_name='sagemaker-featurestore-runtime')


def _record_to_dict(rec, feature_types):
    tmp_dict = {}
    for f in rec:
        feature_name = f['FeatureName']
        string_feature_val = f['ValueAsString']
        feature_type = feature_types[feature_name]
        
        if feature_type == 'Integral':
            tmp_dict[f['FeatureName']] = int(string_feature_val)
        elif feature_type == 'Fractional':
            tmp_dict[f['FeatureName']] = float(string_feature_val)
        else:
            tmp_dict[f['FeatureName']] = string_feature_val

    return tmp_dict


def get_feature_definitions(fg_name):
    fgdescription = sagemaker_client.describe_feature_group(FeatureGroupName=fg_name)    
    return fgdescription 

def get_online_feature_group_records(fg_name, id_value_list):
    feature_defs = get_feature_definitions(fg_name)['FeatureDefinitions']
    feature_types = {}
    feature_names = []
    for fd in feature_defs:
        feature_names.append(fd['FeatureName'])
        feature_types[fd['FeatureName']] = fd['FeatureType']
        
    results = []
    
    identifiers = []
    ids_list = []
    for curr_id in id_value_list:
        record_identifier_value = str(curr_id)
        ids_list.append(record_identifier_value)
    
    identifiers.append({'FeatureGroupName': fg_name,
                        'RecordIdentifiersValueAsString': ids_list,
                        'FeatureNames': feature_names})
        
    resp = featurestore_runtime.batch_get_record(Identifiers=identifiers)
    
    for rec_dict in resp['Records']:
        results.append(_record_to_dict(rec_dict['Record'], feature_types))

    return results

def get_number_of_products_in_feature_set(dict):
    record_count = 0
    for i in enumerate(dict):
        record_count += 1
    return record_count