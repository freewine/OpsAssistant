import json, os
import boto3
from datetime import datetime, timedelta
from dateutil import tz

# 创建 CloudWatch Logs 客户端
logs_client = boto3.client('logs', region_name='us-east-1')

# 指定 WAF 日志组名称和日志流名称前缀
log_group_name =  os.environ["WAF_LOG_GROUP"]
log_stream_name_prefix = 'cloudfront_WafDemo_'

def lambda_handler(event, context):
    print(f"event: {event}")
    parameters = json.loads(event["body"])
    
    # 从事件对象中获取 begin_date 和 end_date 参数
    # start_time_str = next((item['value'] for item in parameters if item['name'] == 'begin_date'), '2023-06-11 00:00:00')
    # end_time_str = next((item['value'] for item in parameters if item['name'] == 'end_date'), '2023-06-12 00:00:00')
    
    start_time_str = parameters['start_time']
    end_time_str = parameters['end_time']

    # 将字符串转换为 datetime 对象
    start_time_obj = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
    end_time_obj = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())

    log_streams = logs_client.describe_log_streams(
        logGroupName=log_group_name,
        logStreamNamePrefix=log_stream_name_prefix,
        #orderBy='lastEventTimestamp',
        descending=True
    )['logStreams']
    
    rt_event = []

    break_lable = False
    for log_stream in log_streams:
        if break_lable:
            break
        log_stream_name = log_stream['logStreamName']
        response = logs_client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
            startTime=int(start_time_obj.timestamp() * 1000),
            endTime=int(end_time_obj.timestamp() * 1000)
        )
        
        print(response)
        
        for item in response['events']:
            print(item)

            # TODO: write code...
            print(item['message'])
            json_msg = json.loads(item['message'])
            s_length = len(repr(rt_event))
            print(f"Logs length: {s_length}")
            if s_length > 10 * 1024:
                break_lable = True
                break
            rt_event.append(json_msg['httpRequest'])

    return {
        "statusCode": 200,
        "body": {
            "Findings": json.dumps(rt_event) # "{}".format(rt_event)
        }
    }