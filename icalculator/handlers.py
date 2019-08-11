from typing import Dict, Any

from OneTicketLogging import elasticsearch_logger
from icalculator.settings import SUCCESS_STATUS, FAILED_STATUS, JOBS_TABLE, WORKER_CALCULATE_FUNCTION, \
    JOB_DEFAULT_STATUS
from icalculator.utils import DynamoDBTable, add_job, get_job, update_job, \
    invoke_async_worker, calculate_inventory, S3InventoryStorage
from icalculator.errors import ServiceError, ClientError


_logger = elasticsearch_logger(__name__)


def check_results(event: Dict[str, Any], _: Any) -> Dict:
    """
    Handle request for the current state of inventory processing job
    :param event: input parameters (incl. job_id - id of target job)
    :param _: lambda handler's context
    :return:
    """
    try:
        job = event["job_id"]
    except KeyError:
        raise ClientError(message='Wrong input - `job_id` parameter must be set explicitly.')

    try:
        table = DynamoDBTable(table_name=JOBS_TABLE)
        job_details = get_job(table=table, job_id=job)
    except Exception as e:
        raise ServiceError(message=f'Unable to get job details : {e}')

    if not job_details:
        raise ClientError(message=f'Wrong input - Job with given `job_id` does not exists.')

    return {
        "job_status": job_details.get("job_status"),
        "total_value": job_details.get("total_value")
    }


def upload_inventory(event: Dict[str, Any], _: Any) -> Dict:
    """
    Handle url to TSV file with inventory items and create new async job
    :param event: input parameters, (incl. file_url - link to file that contains inventory items info)
    :param _: lambda handler's context
    :return:
    """

    try:
        url = event["file_url"]
    except KeyError:
        raise ClientError(message='Wrong input - `file_url` parameter must be set explicitly.')
    if not url:
        raise ClientError(message='Wrong input - `file_url` value cannot be empty.')

    try:
        storage = S3InventoryStorage(source_url=url)
        s3_url = storage.put_object()
    except Exception as e:
        raise ServiceError(message=f'File transfer to S3 : {e}')

    try:
        jobs_table = DynamoDBTable(table_name=JOBS_TABLE)
        job_id = add_job(table=jobs_table, file_location=s3_url)
    except Exception as e:
        raise ServiceError(message=f'Initialize and put new job to DB : {e}')

    try:
        event["job_id"] = job_id
        invoke_async_worker(event, WORKER_CALCULATE_FUNCTION)
        return {
            "job_status": JOB_DEFAULT_STATUS,
            "message": "New process inventory job was successfully created.",
            "job_id": job_id
        }
    except Exception as e:
        raise ServiceError(message=f'Failed to create new job: {e}')


def calculate(event: Dict[str, Any], _: Any):
    """
    Calculate inventory value for given job.
    :param event: input parameters (incl. job_id - id of target job)
    :param _: lambda handler's context
    :return:
    """
    operation_status = SUCCESS_STATUS
    result = None

    try:
        job = event["job_id"]
    except KeyError:
        raise ClientError(message='Wrong input - `job_id` parameter must be set explicitly.')

    table = DynamoDBTable(table_name=JOBS_TABLE)
    job_details = get_job(table=table, job_id=job)
    if not job_details:
        raise ClientError(message=f'Wrong input - Job with given `job_id` does not exists.')

    try:
        result = calculate_inventory(job_details)
    except Exception as e:
        operation_status = FAILED_STATUS
        raise ServiceError(message=f'Exception on inventory calculations with status {FAILED_STATUS}: {e}')
    finally:
        update_job(table=table,
                   job_details={"id": job,
                                "status": operation_status,
                                "value": result})



