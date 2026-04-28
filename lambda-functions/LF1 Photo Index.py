import json #small edit to commit
import boto3
import requests
from requests_aws4auth import AWS4Auth

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    
    try:
        # 1. Extract Details from the Proxy Event
        path_params = event.get('pathParameters', {})
        image_name = path_params.get('item', 'image.jpg')
        
        # Extract custom labels from headers (checking both common casings)
        headers = event.get('headers', {})
        custom_labels_str = headers.get('x-amz-meta-customLabels', '') or headers.get('x-amz-meta-customlabels', '')
        custom_labels = [l.strip().lower() for l in custom_labels_str.split(',')] if custom_labels_str else []

        # 2. AWS Service Configuration
        bucket = "bjk-photo-storage"
        region = 'us-east-1'
        
        # 3. Rekognition: Detect Labels
        rek = boto3.client('rekognition')
        rek_response = rek.detect_labels(
            Image={'S3Object': {'Bucket': bucket, 'Name': image_name}},
            MaxLabels=10
        )
        detected_labels = [label['Name'].lower() for label in rek_response['Labels']]
        
        # Combine Rekognition labels with user's custom labels
        all_labels = list(set(detected_labels + custom_labels))

        # 4. OpenSearch: Index the Document
        host = 'https://search-photo-search-engine-kfs7brbjtb5fbzte5w2b2p6y2q.aos.us-east-1.on.aws'
        service = 'es'
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

        document = {
            "objectKey": image_name,
            "bucket": bucket,
            "createdTimestamp": "2026-04-27T12:00:00",
            "labels": all_labels
        }

        url = f"{host}/photos/_doc/{image_name}"
        requests.put(url, auth=awsauth, json=document, headers={"Content-Type": "application/json"})

        # 5. SUCCESS RESPONSE
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,PUT',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-amz-meta-customLabels'
            },
            'body': json.dumps({"message": "Successfully indexed", "labels": all_labels})
        }

    except Exception as e:
        print(f"LF1 Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': { 'Access-Control-Allow-Origin': '*' },
            'body': json.dumps({"error": str(e)})
        }
