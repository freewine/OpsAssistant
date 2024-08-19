import boto3
import json

# Initialize the Bedrock client
bedrock_client = boto3.client('bedrock-agent-runtime')

def lambda_handler(event, context):
    print(event)

    parameters = json.loads(event["body"])
    # Get the knowledge base ID and query from the event
    knowledge_base_id = 'DWYNXMOTOM'
    query = parameters['query']

    # Call the Retrieve API to get relevant information from the knowledge base
    response = bedrock_client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery = {
            'text': query
        },
        retrievalConfiguration={
            'vectorSearchConfiguration': {
                'numberOfResults': 5,
                # 'overrideSearchType': 'HYBRID'
            }
        }
    )

    # Extract the retrieved results from the response
    retrieval_results = response['retrievalResults']

    # Return the retrieved results
    return {
        'statusCode': 200,
        'body': json.dumps({
            'retrievalResults': retrieval_results
        })
    }