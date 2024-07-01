import boto3
import gzip
import json
from io import BytesIO
from datetime import datetime, timedelta
from dateutil import tz

s3_client = boto3.client('s3')
BUCKET_NAME = 'guardduty-findings-us-west-2-032998046382'

def lambda_handler(event, context):
    print(f"event: {event}")
    agent = event['agent']
    actionGroup = event['actionGroup']
    function = event['function']
    parameters = event.get('parameters', [])

    # 从事件对象中获取 begin_date 和 end_date 参数
    begin_date_str = next((item['value'] for item in parameters if item['name'] == 'start_date'), '2023-04-01 00:00:00')
    end_date_str = next((item['value'] for item in parameters if item['name'] == 'end_date'), '2023-04-02 00:00:00')

    print(f"begin_date_str: {begin_date_str}")
    print(f"end_date_str: {end_date_str}")

    # 将字符串转换为 datetime 对象
    start_date = datetime.strptime(begin_date_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())

    # 假设 generate_date_prefixes 已正确实现
    file_prefixes = generate_date_prefixes(start_date, end_date)

    all_logs = []
    files_processed = 0  # 初始化处理文件的计数器

    for prefix in file_prefixes:
        # 如果已处理20个文件，则终止循环
        if files_processed >= 20:
            break

        # 列出符合日期模式的文件
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            # 检查是否已处理20个文件
            if files_processed >= 3:
                break
            if not obj['Key'].endswith('.gz'):
                print(f"Skipping non-gzip file: {obj['Key']}")
                continue
            file_content = get_gz_file_content(BUCKET_NAME, obj['Key'])
            # 将每个字典转换为JSON字符串并添加到日志列表中
            for log_entry in file_content:
                all_logs.append(log_entry)
            files_processed += 1

    responseBody =  {
        "TEXT": {
            "body": "{}".format(all_logs)
        }
    }

    action_response = {
        'actionGroup': actionGroup,
        'function': function,
        'functionResponse': {
            'responseBody': responseBody
        }

    }
    dummy_function_response = {'response': action_response, 'messageVersion': event['messageVersion']}
    print("Response: {}".format(dummy_function_response))

    return dummy_function_response

def generate_date_prefixes(start_date, end_date):
    """根据开始和结束日期生成S3对象前缀列表"""
    prefixes = []
    current_date = start_date
    while current_date <= end_date:
        prefix = f"_GuardDuty_cn-north-1_{current_date.year}_{current_date.month:02d}_{current_date.day:02d}"
        prefixes.append(prefix)
        current_date += timedelta(days=1)
    return prefixes

def get_gz_file_content(bucket, key):
    """获取并解压S3上的.gz文件，返回解析的json列表"""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    gz_content = gzip.GzipFile(fileobj=BytesIO(response['Body'].read()))

    # 假设日志文件是jsonl格式的（每行一个json对象）
    logs = [json.loads(line) for line in gz_content]
    return logs