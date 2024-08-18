import boto3
import json, os
from datetime import datetime
from dateutil import tz

# Set up the inspector client
inspector_client = boto3.client('inspector2')

def lambda_handler(event, context):
    print(event)

    parameters = json.loads(event["body"])
    start_time_str = parameters['start_time']
    end_time_str = parameters['end_time']
    severity = parameters.get('severity', 'UNTRIAGED')

    severity_comparison = 'EQUALS'
    if(severity == 'UNTRIAGED'):
        severity_comparison = 'NOT_EQUALS'

    # 将字符串转换为 datetime 对象
    start_time_obj = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
    end_time_obj = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())

    finding_results = []

    # Create a reusable Paginator
    paginator = inspector_client.get_paginator('list_findings')

    # Create a PageIterator from the Paginator
    page_iterator = paginator.paginate(
        PaginationConfig={
            # Limits the maximum number of total returned items returned while paginating. See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/paginators.html
            'MaxItems': 500
        },
        filterCriteria={
            # 'awsAccountId': [
            #     {
            #         'comparison': 'EQUALS',
            #         'value': '012345678901'
            #     }
            # ],
            'updatedAt': [
                {
                    'endInclusive': end_time_obj,
                    'startInclusive': start_time_obj
                }
            ],
            'severity': [
                {
                    'comparison': severity_comparison,
                    'value': severity
                }
            ],
            'findingStatus': [
                {
                    'comparison': 'EQUALS',
                    'value': 'ACTIVE'
                },
            ],
            # 'findingType': [
            #     {
            #         'comparison': 'EQUALS',
            #         'value': 'PACKAGE_VULNERABILITY'
            #     },
            # ],
        },
        sortCriteria={
            'field': 'SEVERITY',
            'sortOrder': 'DESC'
        } 
    )

    for page in page_iterator:
        # print(page['ResponseMetadata']['findings'])
        finding_results += page['findings']

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'Results': finding_results
        }, default=json_dumps)
    }

def json_dumps(o):
    if isinstance(o, datetime):
        return None
    else:
        return o.__dict__