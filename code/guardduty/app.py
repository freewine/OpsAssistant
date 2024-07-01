import boto3
import json, os
from datetime import datetime
from dateutil import tz

# Set up the GuardDuty client
guardduty = boto3.client('guardduty')

# Specify the detector ID
detector_id = os.environ["DETECTOR_ID"]

def list_guardduty_findings(start_time, end_time, max_results=50, next_token=None):
    """
    Lists Amazon GuardDuty findings within a specified time range in a paginated way.
    
    Args:
        detector_id (str): The ID of the GuardDuty detector.
        max_results (int, optional): The maximum number of findings to return per page. Default is 50.
        next_token (str, optional): The pagination token to use to retrieve the next page of results.
    
    Returns:
        dict: A dictionary containing the list of finding IDs and the next pagination token.
    """
    # List the GuardDuty findings within the time range
    response = guardduty.list_findings(
        DetectorId = detector_id,
        MaxResults=max_results,
        NextToken=next_token,
        FindingCriteria = {
            'Criterion': {
                'updatedAt': {
                    'Gte': int(start_time.timestamp() * 1000),
                    'Lte': int(end_time.timestamp() * 1000)
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

    return response

def lambda_handler(event, context):
    print(event)

    parameters = json.loads(event["body"])
    start_time_str = parameters['start_time']
    end_time_str = parameters['end_time']

    # 将字符串转换为 datetime 对象
    start_time_obj = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
    end_time_obj = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())

    
    next_token = ''
    finding_ids = []

    while True:
        # List the GuardDuty findings within the time range
        response = list_guardduty_findings(start_time_obj, end_time_obj, next_token = next_token)
        finding_ids += response['FindingIds']
        next_token = response['NextToken']
        
        if not next_token:
            break

    # Get the details of the finding
    finding_details = guardduty.get_findings(
        DetectorId=detector_id,
        FindingIds=finding_ids
    )

    # print(finding_details['Findings'])

    return {
        'statusCode': 200,
        'body': json.dumps({
            'Results': finding_details['Findings']
        }, default=json_dumps)
    }

def json_dumps(o):
    if isinstance(o, datetime):
        return None
    else:
        return o.__dict__