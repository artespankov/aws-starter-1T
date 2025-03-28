from os import getenv

IS_PROD = getenv('ENV_TYPE', 'dev') == 'prod'

INPUT_FILE_URL = 'https://etix-pdf-dev.s3.amazonaws.com/9147_10832__0-10-5_7-5-2019.txt'

SUCCESS_STATUS = "SUCCESS"
FAILED_STATUS = "FAILED"
# ERROR_STATUS = "ERROR"


JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_SUCCEED = "SUCCEED"
JOB_STATUS_FAILED = "FAILED"

JOB_DEFAULT_STATUS = JOB_STATUS_RUNNING


INVENTORY_SOURCES_BUCKET = getenv('INVENTORY_SOURCE_BUCKET', '')
JOBS_TABLE = getenv('JOBS_TABLE', '')

WORKER_CALCULATE_FUNCTION = getenv('WORKER_CALCULATE_FUNCTION')
