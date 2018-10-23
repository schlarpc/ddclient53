import base64
import json
import os

import boto3


def is_authorized(event):
    provided_authz = event.get("headers", {}).get("Authorization", "")
    auth_pair = "{}:{}".format(
        os.environ["DDCLIENT_USERNAME"], os.environ["DDCLIENT_PASSWORD"]
    )
    desired_authz = "Basic {}".format(
        base64.b64encode(auth_pair.encode("utf-8")).decode("utf-8")
    )
    if provided_authz == desired_authz:
        return True
    return False


def get_record_pair(event):
    hostname = event.get("queryStringParameters", {}).get("hostname", "")
    ip = event.get("queryStringParameters", {}).get("myip", "")
    if not hostname or not ip:
        raise ValueError("Bad request")
    hostname = hostname.rstrip(".") + "."
    return hostname, ip


def handler(event, context):
    status = 403
    if is_authorized(event):
        hostname, ip = get_record_pair(event)
        print("Request authorized for", hostname, ip)
        status = 200
        boto3.client("route53").change_resource_record_sets(
            HostedZoneId=os.environ["HOSTED_ZONE_ID"],
            ChangeBatch={
                "Changes": [
                    {
                        "Action": "UPSERT",
                        "ResourceRecordSet": {
                            "Name": hostname,
                            "Type": "A",
                            "TTL": 300,
                            "ResourceRecords": [{"Value": ip}],
                        },
                    }
                ]
            },
        )
    return {"body": "", "statusCode": status, "headers": {"Content-Type": "text/plain"}}
