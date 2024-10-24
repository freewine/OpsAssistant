import boto3
import json, os
import uuid
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from botocore.exceptions import ClientError
from dateutil import tz

bedrock_client = boto3.client('bedrock-runtime')
ddb_client = boto3.client('dynamodb')
sns_client = boto3.client('sns')
lambda_client = boto3.client('lambda')

# 读取环境变量
sns_topic_arn = os.environ.get('SNS_TOPICS_ARN')
# 模型id
model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"

# ddb表, 读写容量按需
report_table_name = 'SecurityReportsTable'

def lambda_handler(event, context):
    print(f"event: {event}")
    # daily, weekly, monthly
    report_period = event.get("report_period", 'daily')
    # waf, guardduty, inspector, IoT device defender
    security_services = event.get("security_service", ['waf'])
    
    result = generate_reports(security_services, report_period)
    
    print(f"Generated reports for services: {security_services}")

    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }

def generate_reports(security_services, report_period):
    # 获取当前日期，格式%Y-%m-%d %H:%M:%S
    current_date = datetime.now(tz=timezone.utc)
    if report_period == 'daily': # 前一天起止时间
        start_date = current_date - timedelta(days=1)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif report_period == 'weekly':
        start_of_this_week = current_date - timedelta(days=current_date.weekday())
        end_of_this_week = start_of_this_week + timedelta(days=6)
        # 前一周起止时间
        start_date = start_of_this_week - timedelta(days=7)
        end_date = end_of_this_week - timedelta(days=7)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif report_period == 'monthly':
        # 计算上个月的第一天
        first_day_of_this_month = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)      
        start_date = first_day_of_this_month - relativedelta(months=1)
        # 计算上个月的最后一天
        end_date = first_day_of_this_month - relativedelta(microseconds=1)
    else:
        print('report_period error')
        return 'report_period error'
        
    date_str = start_date.strftime('%Y-%m-%d')
    print('start_date: %s, end_date: %s' %(start_date.strftime('%Y-%m-%d %H:%M:%S'), end_date.strftime('%Y-%m-%d %H:%M:%S')))

    results = []
    reports = []
    for service in security_services:
        if service == 'waf':
            lambda_arn = os.environ.get('WAF_FUNCTION_ARN')
        elif service == 'guardduty':
            lambda_arn = os.environ.get('GUARDDUTY_FUNCTION_ARN')
        elif service == 'inspector':
            lambda_arn = os.environ.get('INSPECTOR_FUNCTION_ARN')
        elif service == 'iotsecurity':
            lambda_arn = os.environ.get('IOTSECURITY_FUNCTION_ARN')
        else:
            print(f'Unsupported security service: {service}')
            continue
        
        params = {
            "body": json.dumps({
                "start_time": start_date.strftime('%Y-%m-%d %H:%M:%S'),
                "end_time": end_date.strftime('%Y-%m-%d %H:%M:%S')
            })
        }
        
        # Define the parameters for invoking the Lambda function
        invoke_params = {
            'FunctionName': lambda_arn,
            'InvocationType': 'RequestResponse', # Possible values: 'Event'|'RequestResponse'|'DryRun'
            'Payload': json.dumps(params) # JSON payload to pass to the Lambda function
        }

        # Invoke the Lambda function
        response = lambda_client.invoke(**invoke_params)

        # Print the response payload
        payload = json.loads(response['Payload'].read())

        report_response = get_insight(payload.get('body'))
        report = report_response['message']['content'][0]['text']
        reports.append(report)
        save_report(service, report_period, date_str, report)
        send_report(service, report_period, date_str, report)
        results.append(f"{service} report generated and sent")

    # get reports length
    if len(reports) > 1:
        summary = summary_reports(reports)['message']['content'][0]['text']
        send_report("Comprehensive", report_period, date_str, summary)
    else:
        send_report(service, report_period, date_str, report)
    
    return ' | '.join(results)


#  summary all the reports
def summary_reports(reports):
    # Open the file in read mode
    with open('summary-reports.prompt', 'r') as file:
        # Read the entire contents of the file
        template = file.read()

    system_text = template.format(reports=reports)
    system_prompts = [{"text" : system_text}]

    print(system_prompts)

    # Inference parameters to use.
    temperature = 0.5
    top_k = 20

    #Base inference parameters to use.
    inference_config = {"temperature": temperature}
    # Additional inference parameters to use.
    additional_model_fields = {"top_k": top_k}
   
    messages = [{
        "role": "user",
        "content": [{"text": "Generate reposts:"}]
    },
    ]

    try:
        # Send the message.
        response = bedrock_client.converse(
            modelId=model_id,
            messages=messages,
            system=system_prompts,
            inferenceConfig=inference_config,
            additionalModelRequestFields=additional_model_fields,
            #toolConfig=tool_config
        )

        # print(response['output'])
        # print(response['usage'])
    except ClientError as err:
        message = err.response['Error']['Message']
        print(f"A client error occured: {message}")
        return err.response['Error']['Message']
    else:
        print(f"Finished generating text by using converse API with model {model_id}.")
        return response['output']


# bedrock claude3 converse API
def get_insight(logs):
    # Open the file in read mode
    with open('report.prompt', 'r') as file:
        # Read the entire contents of the file
        template = file.read()

    system_text = template.format(logs=logs)
    system_prompts = [{"text" : system_text}]

    # Inference parameters to use.
    temperature = 0.5
    top_k = 20

    #Base inference parameters to use.
    inference_config = {"temperature": temperature}
    # Additional inference parameters to use.
    additional_model_fields = {"top_k": top_k}
   
    messages = [{
        "role": "user",
        "content": [{"text": "Generate reposts:"}]
    },
    ]

    try:
        # Send the message.
        response = bedrock_client.converse(
            modelId=model_id,
            messages=messages,
            system=system_prompts,
            inferenceConfig=inference_config,
            additionalModelRequestFields=additional_model_fields,
            #toolConfig=tool_config
        )

        # print(response['output'])
        # print(response['usage'])
    except ClientError as err:
        message = err.response['Error']['Message']
        print(f"A client error occured: {message}")
        return err.response['Error']['Message']
    else:
        print(f"Finished generating text by using converse API with model {model_id}.")
        return response['output']

#ddb
def save_report(service, report_period, start_date, report):
        # 构造要插入的项目
    item = {
        'id': {'S': str(uuid.uuid4())},
        'security_service': {'S': service},
        'report_period': {'S': report_period},
        'start_date': {'S': start_date},
        'report': {'S': report},
        'timestamp': {'S': datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
    }

    # 发送PutItem请求
    response = ddb_client.put_item(
        TableName = report_table_name,
        Item = item
    )

    # 检查响应
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        # print(f'已将消息 "{report}" 插入表 {table_name}')
        print(f'已将报告插入表 {report_table_name} ')
    else:
        print('插入失败')
        print(response)

def get_report(ddb_client, table_name, start_date):
    try:
        response = ddb_client.get_item(
            TableName=table_name,
            Key={
                'start_date': {'S': start_date}
            }
        )
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        if 'Item' in response:
            return response['Item']['report']['S']
        else:
            return None

def send_report(service, report_period, start_date, report):
    try:
        response = sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=report,
            Subject=f'{service} {report_period} report'.upper()
        )
        print(f"SNS response: {response}")
    except ClientError as e:
        print(f"Error: {e.response['Error']['Message']}")

# if __name__ == "__main__":
#     waf_report(report_period)
