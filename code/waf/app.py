import json
import os
import time
import boto3
from datetime import datetime, timedelta
from dateutil import tz

# Get WAF log group name from environment variables
log_group_name = os.environ["WAF_LOG_GROUP"]
waf_log_region = os.environ["WAF_LOG_REGION"] or 'us-east-1'

# Create CloudWatch Logs client
logs_client = boto3.client('logs', region_name=waf_log_region)

def get_query_results(query_id):
    """Helper function to get query results"""
    while True:
        response = logs_client.get_query_results(queryId=query_id)
        if response['status'] in ['Complete', 'Failed', 'Cancelled', 'Timeout', 'Unknown']:
            break
        time.sleep(0.01)
    return response

def execute_query(start_time, end_time, query_string):
    """Execute CloudWatch Logs Insights query and return results"""
    query_result = logs_client.start_query(
        logGroupName=log_group_name,
        startTime=int(start_time.timestamp() * 1000),
        endTime=int(end_time.timestamp() * 1000),
        queryString=query_string
    )
    return get_query_results(query_result['queryId'])

def get_raw_logs(start_time, end_time, limit=200):
    """Get top IP addresses by request count"""
    query = f"""
    fields @timestamp, @message | sort @timestamp desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_top_ip_addresses(start_time, end_time, limit=100):
    """Get top IP addresses by request count"""
    query = f"""
    fields httpRequest.clientIp
    | stats count(*) as requestCount by httpRequest.clientIp
    | sort requestCount desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_top_countries(start_time, end_time, limit=100):
    """Get top countries by request count"""
    query = f"""
    fields httpRequest.country
    | stats count(*) as requestCount by httpRequest.country
    | sort requestCount desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_top_hosts(start_time, end_time, limit=100):
    """Get top hosts by request count"""
    query = f"""
    fields @timestamp, @message
    | parse @message '{{"name":"Host","value":"*"}}' as host
    | stats count(*) as requestCount by host
    | sort requestCount desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_top_terminatingRuleIds(start_time, end_time, limit=100):
    """Get top terminatingRuleIds by request count"""
    query = f"""
    fields terminatingRuleId
    | stats count(*) as requestCount by terminatingRuleId
    | sort requestCount desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_XSS_or_SQL_injection_rule_matches(start_time, end_time, limit=100):
    """Find patterns that triggered XSS or SQL injection"""
    query = f"""
    fields @timestamp
    | parse @message ',"terminatingRuleMatchDetails":[*],' as terminatingRuleMatchData
    | filter (terminatingRuleMatchData like /XSS/ or terminatingRuleMatchData like /SQL/)
    | display @timestamp, httpRequest.clientIp, httpRequest.country, terminatingRuleMatchData, httpRequest.requestId
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_top_user_agents(start_time, end_time, limit=100):
    """Get top User-Agents"""
    query = f"""
    fields @timestamp, @message
    | parse @message '{{"name":"User-Agent","value":"*"}}' as userAgent
    | stats count(*) as requestCount by userAgent
    | sort requestCount desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_top_counted_user_agents(start_time, end_time, limit=100):
    """Get top User-Agents for counted requests"""
    query = f"""
    fields @timestamp, @message
    | parse @message '{{"name":"User-Agent","value":"*"}}' as userAgent
    | parse @message ',"nonTerminatingMatchingRules":[{{"ruleId":"*","action":"*"' as rule, action
    | filter action = "COUNT"
    | stats count(*) as requestCount by userAgent
    | sort requestCount desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_invalid_captchas(start_time, end_time, limit=100):
    """Get requests with invalid captchas"""
    query = f"""
    fields @timestamp, httpRequest.clientIp, httpRequest.requestId, captchaResponse.failureReason, @message
    | filter captchaResponse.failureReason ='TOKEN_MISSING'
    | sort @timestamp desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def get_blocked_requests(start_time, end_time, limit=100):
    """Get blocked requests with details"""
    query = f"""
    fields @timestamp, httpRequest.clientIp, httpRequest.uri, terminatingRuleId, terminatingRuleMatchDetails
    | filter action = "BLOCK"
    | sort @timestamp desc
    | limit {limit}
    """
    return execute_query(start_time, end_time, query)

def format_results(response):
    # print(response)
    """Format query results into a consistent structure"""
    if not response.get('results'):
        return []
    
    results = []
    for result in response['results']:
        formatted = {}
        for field in result:
            formatted[field['field']] = field['value']
        results.append(formatted)
    return results

def lambda_handler(event, context):
    try:
        print(f"event: {event}")
        parameters = json.loads(event["body"])

        # Validate required parameters
        required_fields = ['start_time', 'end_time', 'analysis_type']
        for field in required_fields:
            if field not in parameters:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": f"Missing required field: {field}"})
                }

        # Parse timestamps
        try:
            start_time = datetime.strptime(parameters['start_time'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
            end_time = datetime.strptime(parameters['end_time'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
        except ValueError as e:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid datetime format: {str(e)}"})
            }

        # Execute requested analysis
        analysis_type = parameters['analysis_type'] or 'raw'
        limit = parameters.get('limit', 200)

        analysis_functions = {
            'raw': lambda: get_raw_logs(start_time, end_time, min(limit, 200)), 
            'top_ip': lambda: get_top_ip_addresses(start_time, end_time, limit),
            'top_country': lambda: get_top_countries(start_time, end_time, limit),
            'top_host': lambda: get_top_hosts(start_time, end_time, limit),
            'top_terminatingRuleId': lambda: get_top_terminatingRuleIds(start_time, end_time, limit),
            'XSS_or_SQL_injection': lambda: get_XSS_or_SQL_injection_rule_matches(start_time, end_time, limit),
            'top_user_agent': lambda: get_top_user_agents(start_time, end_time, limit),
            'top_counted_user_agent': lambda: get_top_counted_user_agents(start_time, end_time, limit),
            'invalid_captcha': lambda: get_invalid_captchas(start_time, end_time, limit),
            'blocked_request': lambda: get_blocked_requests(start_time, end_time, limit)
        }

        if analysis_type not in analysis_functions:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": f"Invalid analysis_type. Must be one of: {', '.join(analysis_functions.keys())}"
                })
            }

        response = analysis_functions[analysis_type]()
        results = format_results(response)

        return {
            "statusCode": 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            "body": json.dumps({
                "analysis_type": analysis_type,
                "start_time": parameters['start_time'],
                "end_time": parameters['end_time'],
                "results": results,
                "result_count": len(results)
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "details": str(e)
            })
        }
