import os
import boto3
from botocore.exceptions import NoCredentialsError

# Retrieve AWS credentials from environment variables
AWS_ACCESS_KEY_ID = os.environ.get('AWS_KEY')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET')
AWS_S3_BUCKET_NAME = os.environ.get('AWS_BUCKET')

print("Access Key:", AWS_ACCESS_KEY_ID)
print("Secret Key:", AWS_SECRET_ACCESS_KEY)
print("Bucket Name:", AWS_S3_BUCKET_NAME)


# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    # Uncomment and set your bucket's region if necessary
    region_name='us-east-1'
)

# Function to upload a file to an S3 bucket
def upload_file(file_name, bucket, object_name=None):
    try:
        response = s3_client.upload_file(file_name, bucket, object_name or file_name)
        print("File uploaded successfully")
        return response
    except NoCredentialsError:
        print("Credentials not available")
        return None

# Create a test file
test_file_name = 'test_file.txt'
with open(test_file_name, 'w') as file:
    file.write('This is a test file for AWS S3 upload.')

# Upload the test file
upload_file(test_file_name, AWS_S3_BUCKET_NAME, 'test_upload/' + test_file_name)

# Clean up: remove the test file from your local system if desired
os.remove(test_file_name)
