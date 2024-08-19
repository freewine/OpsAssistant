import json, os, time
import boto3
from datetime import datetime, timedelta
from dateutil import tz


# 从环境变量获取 WAF 日志组名
log_group_name =  os.environ["WAF_LOG_GROUP"]
waf_log_region =  os.environ["WAF_LOG_REGION"] or 'us-east-1'

# 创建 CloudWatch Logs 客户端
logs_client = boto3.client('logs', region_name=waf_log_region)

def lambda_handler(event, context):
    print(f"event: {event}")
    parameters = json.loads(event["body"])

    start_time_str = parameters['start_time']
    end_time_str = parameters['end_time']

    # 将字符串转换为 datetime 对象
    start_time_obj = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
    end_time_obj = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())

    # Start a query for the log group
    query_result = logs_client.start_query(
        logGroupName=log_group_name,
        startTime=int(start_time_obj.timestamp() * 1000),
        endTime=int(end_time_obj.timestamp() * 1000),
        queryString='fields @timestamp, @message | sort @timestamp desc | limit 500'
    )

    # print(query_result)
    query_id = query_result['queryId']

    while True:
        response = logs_client.get_query_results(
            queryId=query_id
        )
        if response['status'] in ['Complete', 'Failed', 'Cancelled', 'Timeout', 'Unknown']:
            break
        time.sleep(0.1)

    # format results
    results = []
    for log_event in response['results']:
        result = json.loads(log_event[1]['value'])
        result['timestamp'] = log_event[0]['value']
        results.append(result)

    return {
        "statusCode": 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        "body": json.dumps({
            "Results": results
        })
    }