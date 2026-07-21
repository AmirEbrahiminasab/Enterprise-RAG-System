import aioboto3
import uuid
from fastapi import UploadFile
from botocore.exceptions import ClientError


MINIO_ENDPOINT = "http://minio:9000"
MINIO_ACCESS_KEY = "dev_user"
MINIO_SECRET_KEY = "dev_password"
BUCKET_NAME = "chat-documents"

async def upload_to_s3(file: UploadFile) -> str:
    session = aioboto3.Session()
    
    object_key = f"{file.filename}-{uuid.uuid4()}"
    
    async with session.client('s3',
                              endpoint_url=MINIO_ENDPOINT,
                              aws_access_key_id=MINIO_ACCESS_KEY,
                              aws_secret_access_key=MINIO_SECRET_KEY) as s3:
        
        try:
            await s3.head_bucket(Bucket=BUCKET_NAME)
        except ClientError as e:
            error_code = str(e.response.get('Error', {}).get('Code', ''))
            status_code = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            
            if error_code == '404' or error_code == 'NoSuchBucket' or status_code == 404:
                await s3.create_bucket(Bucket=BUCKET_NAME)
            else:
                raise e
        
        
        file_content = await file.read()
        await s3.put_object(Bucket=BUCKET_NAME, Key=object_key, Body=file_content)
        
    return object_key

async def read_from_s3(object_key: str):
    session = aioboto3.Session()

    async with session.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    ) as s3:
        response = await s3.get_object(
            Bucket=BUCKET_NAME,
            Key=object_key,
        )

        content = await response["Body"].read()
        return content