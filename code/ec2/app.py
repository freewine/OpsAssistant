from build_query_engine import query_engine
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log(message):
    logger.info(message)

def lambda_handler(event, context):
    """
    Get response RAG or Query
    """

    log(event)
    
    parameters = json.loads(event["body"])
    user_input = parameters["query"]
    api_path = event["path"]

    # Only allow one str, to mitigate mixed prompt injection
    if isinstance(user_input, str):
        log(f"Question {user_input}")
        if api_path == "/tools/ec2":
            response = query_engine.query(user_input)

            log("Sql query:")
            log(response.metadata["sql_query"].replace("\n", " "))
            log(f"Provided response: {response.response}")
            output = {
                "source": response.metadata["sql_query"],
                "answer": response.response,
            }
        elif api_path == "/uc1":
            output = {
                "source": "Doc retrieval",
                "answer": "Getting info from knowledgebase.",
            }
        else:
            output = {
                "source": "Not Found",
                "answer": "I don't know enough to answer this question, please try to clarify you quesiton.",
            }
    else:
        output = {
            "source": "Not Found",
            "answer": "Please ask questions one by one.",
        }
    
    return {
        'statusCode': 200,
        'body': {
            'Source': output["source"],
            'Result': output["answer"]
        }
    }