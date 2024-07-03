import boto3
import json, os
from datetime import datetime
from dateutil import tz

# Set up the GuardDuty client
guardduty = boto3.client('guardduty')

# Specify the detector ID
detector_id = os.environ["DETECTOR_ID"]

def lambda_handler(event, context):
    print(event)

    parameters = json.loads(event["body"])
    start_time_str = parameters['start_time']
    end_time_str = parameters['end_time']

    # 将字符串转换为 datetime 对象
    start_time_obj = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
    end_time_obj = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())

    
    finding_ids = []

    # Create a reusable Paginator
    paginator = guardduty.get_paginator('list_findings')

    # Create a PageIterator from the Paginator
    page_iterator = paginator.paginate(
        DetectorId = detector_id,
        FindingCriteria = {
            'Criterion': {
                'updatedAt': {
                    'Gte': int(start_time_obj.timestamp() * 1000),
                    'Lte': int(end_time_obj.timestamp() * 1000)
                },
                'severity': {
                    'Gte': 0
                },
            }
        },
        SortCriteria={
            'AttributeName': 'severity',
            'OrderBy': 'DESC'
        }
    )

    for page in page_iterator:
        print(page)
        finding_ids += page['FindingIds']

    # Get the details of the finding
    finding_details = guardduty.get_findings(
        DetectorId=detector_id,
        FindingIds=finding_ids
    )

    # print(finding_details['Findings'])

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'Results': finding_details['Findings']
        }, default=json_dumps)
    }

def json_dumps(o):
    if isinstance(o, datetime):
        return None
    else:
        return o.__dict__