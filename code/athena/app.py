import boto3
import json, os, time
from botocore.exceptions import ClientError

# Set up the inspector client
athena_client = boto3.client('athena')
bedrock_client = boto3.client('bedrock-runtime')
# 模型id
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

workgroup = os.environ["ATHENA_WORKGROUP"]

def lambda_handler(event, context):
    # print(event)

    parameters = json.loads(event["body"])
    query = parameters['query']
    query_type = parameters['query_type'] or "RAW"

    if(query_type == "RAW"):
        query_sql_json = text2sql(query)
        print(query_sql_json)
        query_sql = json.loads(query_sql_json).get('SQL')
    else:
        query_sql = query

    print(query_sql)

    query_execution_result = athena_client.start_query_execution(
        QueryString=query_sql,
        QueryExecutionContext={
            'Database': 'amazon_cl_centralized',
            'Catalog': 'AwsDataCatalog'
        },
        ResultReuseConfiguration={
            'ResultReuseByAgeConfiguration': {
                'Enabled': True,
                'MaxAgeInMinutes': 60
            }
        },
        WorkGroup=workgroup
    )

    print(query_execution_result)
    query_id = query_execution_result['QueryExecutionId']

    # get query status
    while True:
        query_execution = athena_client.get_query_execution(
            QueryExecutionId=query_id
        )
        query_status = query_execution['QueryExecution']['Status']['State']
        print(query_status)
        if query_status in ['QUEUED', 'RUNNING']:
            print(f"The query status '{query_status}' is not finished.")
            time.sleep(0.01)
        else:
            print(f"The query status '{query_status}' is finished.")
            break

    results = []

    # Create a reusable Paginator
    # get_query_results only loads the first 1000 rows
    paginator = athena_client.get_paginator('get_query_results')

    # Create a PageIterator from the Paginator
    page_iterator = paginator.paginate(
        PaginationConfig={
            # Limits the maximum number of total returned items returned while paginating. See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/paginators.html
            'MaxItems': 100
        },
        QueryExecutionId=query_id
    )

    for page in page_iterator:
        results += page['ResultSet']['Rows']

    # print(results)

    return {
        "statusCode": 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        "body": json.dumps({
            "Results": results
        })
    }

def text2sql(query):

    # Open the file in read mode
    with open('vpc_flow_logs.prompt', 'r') as file:
        # Read the entire contents of the file
        vpc_flow_logs_prompt = file.read()

    system_prompts = [{"text" : vpc_flow_logs_prompt}]

    # Inference parameters to use.
    temperature = 0

    #Base inference parameters to use.
    inference_config = {"temperature": temperature}

   
    messages = [{
        "role": "user",
        "content": [{"text": query}]
    },
    ]

    try:
        # Send the message.
        response = bedrock_client.converse(
            modelId=model_id,
            messages=messages,
            system=system_prompts,
            inferenceConfig=inference_config
            #toolConfig=tool_config
        )

        # print(response['output'])
        # print(response['usage'])
        print(f"Finished generating text by using converse API with model {model_id}.")
        return response['output']['message']['content'][0]['text']
    except ClientError as err:
        message = err.response['Error']['Message']
        print(f"A client error occured: {message}")
        return "False"