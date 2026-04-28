import json
import boto3
import requests
from requests_aws4auth import AWS4Auth

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    
    # 1. Extract the search query from the API Gateway Proxy event
    query_params = event.get('queryStringParameters', {})
    user_query = query_params.get('q', '') if query_params else ''
    
    if not user_query:
        return build_response(400, {'message': 'No query provided'})

    try:
        # 2. Configuration for OpenSearch
        host = 'https://search-photo-search-engine-kfs7brbjtb5fbzte5w2b2p6y2q.aos.us-east-1.on.aws'
        region = 'us-east-1'
        service = 'es'
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

        # 3. Search OpenSearch for the label
        url = f"{host}/photos/_search"
        query = {
            "query": {
                "match": {
                    "labels": user_query
                }
            }
        }

        r = requests.get(url, auth=awsauth, json=query)
        r.raise_for_status()
        response_data = r.json()
        
        # 4. Parse results
        hits = response_data.get('hits', {}).get('hits', [])
        results = []
        for hit in hits:
            source = hit.get('_source', {})
            results.append({
                "url": f"https://{source.get('bucket')}.s3.amazonaws.com/{source.get('objectKey')}",
                "labels": source.get('labels', [])
            })

        return build_response(200, results)

    except Exception as e:
        print(f"LF2 Error: {str(e)}")
        return build_response(500, {"error": str(e)})

def build_response(status_code, body):
    """Helper to ensure Proxy Integration responses are consistent."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(body)
    }
