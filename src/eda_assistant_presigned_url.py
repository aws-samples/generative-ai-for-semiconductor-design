import logging
import boto3
import urllib.parse
from botocore.exceptions import ClientError


def parse_s3_uri(s3_uri):
    # Parse the S3 URI
    parsed_uri = urllib.parse.urlparse(s3_uri)

    # Check if the scheme is 's3' (Amazon S3 URI)
    if parsed_uri.scheme == 's3':
        # Split the path into bucket and object name
        bucket_name = parsed_uri.netloc
        object_name = parsed_uri.path.lstrip('/')
        
        return bucket_name, object_name
    else:
        raise ValueError("Not a valid S3 URI")

#expiration 5 min
def create_presigned_url(s3_uri, expiration=300):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """
    bucket_name, object_name = parse_s3_uri(s3_uri)
    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response