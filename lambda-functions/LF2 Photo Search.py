import json
import boto3
import requests
from requests_aws4auth import AWS4Auth

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    
    try:
        # 1. Extract Query from API Gateway Proxy Event
        q_params = event.get('queryStringParameters') or {}
        user_query = q_params.get('q', '')

        # If search is empty, return an empty results list immediately
        if not user_query:
            return build_response(200, [])

        # 2. Lex V2: Disambiguate Labels
        lex = boto3.client('lexv2-runtime')
        
        lex_response = lex.recognize_text(
            botId='GD5JPZCKID', 
            botAliasId='TSTALIASID',
            localeId='en_US',
            sessionId='search_session',
            text=user_query
        )

        # Extract interpreted values from Lex slots
        slots = lex_response.get('sessionState', {}).get('intent', {}).get('slots', {})
        search_labels = []
        for slot in slots.values():
            if slot and slot.get('value') and 'interpretedValue' in slot['value']:
                search_labels.append(slot['value']['interpretedValue'].lower())

        # If Lex didn't find any slots, try searching the raw query word
        if not search_labels:
            search_labels.append(user_query.lower())

        # 3. OpenSearch: Query Configuration
        host = 'https://search-photo-search-engine-kfs7brbjtb5fbzte5w2b2p6y2q.aos.us-east-1.on.aws' 
        region = 'us-east-1'
        service = 'es'
        
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key, 
            credentials.secret_key, 
            region, 
            service, 
            session_token=credentials.token
        )

        results = []
        # Use a set to prevent duplicate photos in results
        seen_keys = set()

        for label in search_labels:
            # Clean the label for the URL
            label = label.replace(" ", "+")
            url = f"{host}/photos/_search?q=labels:{label}"
            
            try:
                os_response = requests.get(url, auth=awsauth, timeout=5)
                os_response.raise_for_status() # Check for 4xx or 5xx errors from OpenSearch
                resp_data = os_response.json()
                
                if 'hits' in resp_data:
                    for hit in resp_data['hits']['hits']:
                        source = hit['_source']
                        object_key = source['objectKey']
                        
                        if object_key not in seen_keys:
                            results.append({
                                "url": f"https://{source['bucket']}.s3.amazonaws.com/{object_key}",
                                "labels": source['labels']
                            })
                            seen_keys.add(object_key)
            except Exception as os_err:
                print(f"Error querying label '{label}': {str(os_err)}")
                continue

        return build_response(200, results)

    except Exception as e:
        print(f"LF2 General Error: {str(e)}")
        # Even on error, we return the CORS headers so the browser can read the message
        return build_response(500, {"error": str(e)})

def build_response(status, data):
    """
    Standardizes the response format for API Gateway Lambda Proxy Integration.
    Ensures CORS headers are present and body is correctly stringified.
    """
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,GET',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
        },
        'body': json.dumps(data if status == 500 else {"results": data}),
        'isBase64Encoded': False
    }
