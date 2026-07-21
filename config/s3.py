import aioboto3
import uuid
from fastapi import UploadFile

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
        
        file_content = await file.read()
        await s3.put_object(Bucket=BUCKET_NAME, Key=object_key, Body=file_content)
        
    return object_key