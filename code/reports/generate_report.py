import boto3
import time
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from botocore.exceptions import ClientError

query_num = 1000

region = 'us-east-1'#'us-west-2' #
logs_client = boto3.client('logs', region_name=region)
bedrock_client = boto3.client('bedrock-runtime', region_name=region)
ddb_client = boto3.client('dynamodb', region_name=region)

# 日志组
log_group_name = 'aws-waf-logs-game2048'
# 模型id
model_id = "anthropic.claude-3-haiku-20240307-v1:0"
# ddb表, 读写容量按需
waf_daily_report_table_name = 'ops_assist_waf_daily_reports'
waf_weekly_report_table_name = 'ops_assist_waf_weekly_reports'
waf_monthly_report_table_name = 'ops_assist_waf_monthly_reports'

time_range = 'daily'
# time_range = 'weekly'
# time_range = 'monthly'


def lambda_handler(event, context):
    print(f"event: {event}")
    time_range = event["time_range"]
    waf_report(time_range)

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

def waf_report(time_range):
    # 获取当前日期，格式%Y-%m-%d %H:%M:%S
    current_date = datetime.now()
    if time_range == 'daily': # 前一天起止时间
        start_date = current_date - timedelta(days=1)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        waf_report_table_name = waf_daily_report_table_name
    elif time_range == 'weekly':
        start_of_this_week = current_date - timedelta(days=current_date.weekday())
        end_of_this_week = start_of_this_week + timedelta(days=6)
        # 前一周起止时间
        start_date = start_of_this_week - timedelta(days=7)
        end_date = end_of_this_week - timedelta(days=7)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        waf_report_table_name = waf_weekly_report_table_name
    elif time_range == 'monthly':
        # 计算上个月的第一天
        first_day_of_this_month = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)      
        start_date = first_day_of_this_month - relativedelta(months=1)
        # 计算上个月的最后一天
        end_date = first_day_of_this_month - relativedelta(microseconds=1)
        waf_report_table_name = waf_monthly_report_table_name
    else:
        print('time_range error')
        return None
        
    print('start_date: %s, end_date: %s' %(start_date, end_date))

    # 设置初始查询起始时间
    start_query_time = int(start_date.timestamp()) * 1000
    end_query_time = int(end_date.timestamp()) * 1000
    print('start_query_time: %d, end_query_time: %d' %(start_query_time, end_query_time))

    index=1
    last_timestamp = 0 # 最后一条记录的时间戳
    total_reports = []
    while True:
        # 执行查询
        print('***********************************************************************')
        print('query %d, start_query_time: %d' %(index,start_query_time))
        response = logs_client.start_query(
            logGroupName=log_group_name,
            startTime=start_query_time,
            endTime=end_query_time,
            queryString='fields @timestamp, @message | sort @timestamp asc',
            limit=query_num
        )
        # print('response: %s' %(response))
        
        # 获取查询结果
        while True:
            # 需要sleep一会，不然马上get_query_results会没有结果
            time.sleep(1)
            query_id = response['queryId']
            logs = logs_client.get_query_results(
                queryId=query_id
            )
            # 检查状态
            status = logs['status']
            # print('status: %s' %(status))
            if status in ['Complete', 'Failed', 'Cancelled', 'Timeout', 'Unknown']:
                break
            
        # status == Complete, 处理查询结果
        if logs['results']:    
            results = []
            for log in logs['results']:
                result = json.loads(log[1]['value'])
                last_timestamp = result['timestamp']
                # result['timestamp'] = log[0]['value']
                results.append(result)
                # print('date: %s' %(log[0]['value']))
                # print('result: %s' %(result))
            # print('results: %s' %(results))
            print('query %d complete, try to call claude' %index)

            response = generate_conversation(bedrock_client, model_id, str(results))
            if response:
                report = response['message']['content'][0]['text']
                # print(report)
                if(report):
                    total_reports.append(report)
                    print('add report %d to total reports' %index)
        else:
            # print('end')
            break  
        
        # 更新下一次查询的起始时间, start_query函数的startTime是包含在查询范围内的，所以下一次start_query_time加1
        start_query_time = last_timestamp + 1
        index += 1

    date_str = start_date.strftime('%Y-%m-%d')
    save_report(ddb_client, waf_report_table_name, date_str, ', '.join(total_reports))

# bedrock claude3 converse API
def generate_conversation(bedrock_client, model_id, content):
    system_text = "你是一名安全顾问, 根据所给的日志, 仔细分析, 进行总结. 首先描述整体的安全态势, 然后根据攻击种类进行日志分析和分类统计, 需要区分正常访问和攻击行为, 注意不要过分解读。不管message的语言类型, 只用简体中文回答。"
    system_prompts = [{"text" : system_text}]

    # Inference parameters to use.
    temperature = 0.5
    top_k = 200

    #Base inference parameters to use.
    inference_config = {"temperature": temperature}
    # Additional inference parameters to use.
    additional_model_fields = {"top_k": top_k}

   
    messages = [{
        "role": "user",
        "content": [{"text": content}]
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
    else:
        print(f"Finished generating text by using converse API with model {model_id}.")
        return response['output']

#ddb
def save_report(ddb_client, table_name, start_date, report):
        # 构造要插入的项目
    item = {
        'start_date': {'S': start_date},
        'report': {'S': report}
    }

    # 发送PutItem请求
    response = ddb_client.put_item(
        TableName = table_name,
        Item = item
    )

    # 检查响应
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        # print(f'已将消息 "{report}" 插入表 {table_name}')
        print(f'已将报告插入表 {table_name} ')
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
        
# if __name__ == "__main__":
#     waf_report(time_range)