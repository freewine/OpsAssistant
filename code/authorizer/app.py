import json, os


def lambda_handler(event, context):
    # print(event)
    auth_token =  os.environ["AUTH_TOKEN"]

    try:
        if (event["authorizationToken"] == 'Bearer ' + auth_token):
            print('allowed')
            response = generatePolicy(event['type'], 'Allow', event['methodArn'])
            return response
        else:
            print('denied')
            response = generatePolicy(event['type'], 'Deny', event['methodArn'])
            return response
    except BaseException:
        print('denied')
        response = generatePolicy(event['type'], 'Deny', event['methodArn'])
        return response

def generatePolicy(principalId, effect, resource):
    authResponse = {}
    authResponse['principalId'] = principalId
    if (effect and resource):
        policyDocument = {}
        policyDocument['Version'] = '2012-10-17'
        policyDocument['Statement'] = []
        statementOne = {}
        statementOne['Action'] = 'execute-api:Invoke'
        statementOne['Effect'] = effect
        statementOne['Resource'] = '*'
        policyDocument['Statement'] = [statementOne]
        authResponse['policyDocument'] = policyDocument
    authResponse['context'] = {
        "stringKey": "stringval",
        "numberKey": 123,
        "booleanKey": True
    }
    return authResponse