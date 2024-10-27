import json
import boto3
import urllib3


def get_secret(region_name, secret_name):
    client = boto3.client("secretsmanager", region_name=region_name)
    print("secret_name", secret_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        if "SecretString" in response:
            secret = response["SecretString"]
        else:
            secret = response["SecretBinary"]
        secret_dict = json.loads(secret)
        return secret_dict
    except Exception as e:
        print(f"Error retrieving secret: {e}")
        raise e


def load_access_control_policy(url):
    http = urllib3.PoolManager()
    response = http.request("GET", url)
    if response.status == 200:
        print("Access Control Policy loaded")
        return json.loads(response.data.decode("utf-8"))
    else:
        return {}
