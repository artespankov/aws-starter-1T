import io
import os
import boto3
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from typing import Any, Dict
from json import dumps
from uuid import uuid4
from botocore.exceptions import ClientError as B3ClientError
from OneTicketLogging import elasticsearch_logger

from icalculator.settings import INVENTORY_SOURCES_BUCKET, JOB_DEFAULT_STATUS
from icalculator.errors import ServiceError, ClientError
from icalculator.core import InventoryCalculator


_dynamodb = boto3.resource('dynamodb')
_lambda_client = boto3.client('lambda')
_s3_client = boto3.client('s3')
_logger = elasticsearch_logger(__name__)


class S3InventoryStorage:
    """Wrapper for S3 storage"""

    def __init__(self, source_url: str):
        self.source_url = source_url
        self._s3 = _s3_client
        self._bucket_name = INVENTORY_SOURCES_BUCKET

    @property
    def key(self):
        return self.source_url.split('/')[-1]

    def file_name(self, path: str) -> str:
        """Generate unique filename string"""
        ext = os.path.splitext(path)[1]
        return f'{str(uuid4())}{ext}'

    def get_file(self, url: str) -> Any:
        """Read file content by given url"""
        try:
            response = urlopen(url)
        except HTTPError as e:
            raise ClientError(f"Error accessing input file by url. Code: {e.code}. Reason: {e.reason}.")
        except URLError as e:
            raise ClientError(f"Error connecting to inventory file server. Reason: {e.reason}.")
        if response.status == 200:
            return response
        else:
            raise ClientError(f"Could not get input file content. Status: {response.status}")

    def full_path(self, key: str) -> str:
        """Generate full path to file on S3 (incl. base url and bucket name)"""
        return f's3://{self._bucket_name}/{key}'

    def put_object(self) -> str:
        """Save file as an object into S3 storage"""
        key = self.file_name(self.source_url)
        self._s3.upload_fileobj(self.get_file(self.source_url), self._bucket_name, key)
        return self.full_path(key)

    def get_content(self):
        file_obj = self._s3.get_object(Bucket=self._bucket_name, Key=self.key)
        body = file_obj['Body']
        content = body.read().decode('utf-8')
        return io.StringIO(content)


class DynamoDBTable:
    """
    Wrapper for DynamoDB Table instance. Provides the basic API to manage in-db objects: CRU-actions
    """

    def __init__(self, table_name: str):
        self._table = _dynamodb.Table(table_name)

    def get(self, **kwargs):
        response = self._table.get_item(**kwargs)
        return response.get("Item", {})

    def create(self, **kwargs):
        self._table.put_item(**kwargs)

    def update(self, **kwargs):
        self._table.update_item(**kwargs)

    @property
    def table(self):
        return self._table


def add_job(table: Any, file_location: str) -> str:
    """Put new job into DynamoDB Table"""
    job_id = str(uuid4())
    table.create(
        Item={
            "job_id": job_id,
            "file_location": file_location,
            "job_status": JOB_DEFAULT_STATUS,
            "total_value": None
        },
        ReturnValues='NONE')
    return job_id


def get_job(table: Any, job_id: str) -> Dict:
    """ Get job details by it's id from DynamoDB Table"""
    job_details = table.get(Key={"job_id": job_id})
    return job_details


def update_job(table: Any, job_details: Dict):
    table.update(
        Key={"job_id": job_details.get('id')},
        ExpressionAttributeNames={
            "#JS": "job_status",
            "#TV": "total_value"
        },
        ExpressionAttributeValues={
            ":js": job_details.get("status"),
            ":tv": dumps(job_details.get("value"))
        },
        UpdateExpression='SET #JS = :js, #TV = :tv')


def calculate_inventory(job_details: Dict) -> int:
    inventory_calculator = InventoryCalculator(job_details.get('file_location'))
    total_value = inventory_calculator.calculate()
    return total_value


def invoke_async_worker(payload, handler):
    """Invoke lambda function"""
    _logger.info(f"Invoking {handler} async with payload {payload}")
    try:
        _lambda_client.invoke(
            FunctionName=handler,
            Payload=dumps(payload),
            InvocationType="Event")
    except B3ClientError as exc:
        raise ServiceError(f"{handler} invocation failed: {exc}")
