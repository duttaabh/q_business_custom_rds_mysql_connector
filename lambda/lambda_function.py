import os
import json
import logging
import base64
import datetime
import pymysql
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_client = boto3.client('secretsmanager')
q_client = boto3.client('qbusiness')

# Environment variables (set these in Lambda configuration)
SECRET_ARN = os.environ['SECRET_ARN']              # ARN of Secrets Manager secret with username/password
DB_HOST = os.environ['DB_HOST']                     # Aurora MySQL endpoint
DB_NAME = os.environ['DB_NAME']                     # Database name
DB_PORT = int(os.environ.get('DB_PORT', '3306'))    # Port, default 3306
Q_APPLICATION_ID = os.environ['Q_APPLICATION_ID']  # Amazon Q Business Application ID
Q_INDEX_ID = os.environ['Q_INDEX_ID']               # Amazon Q Business Index ID
Q_DATA_SOURCE_ID = os.environ['Q_DATA_SOURCE_ID']  # Q Business Data Source ID

def get_db_credentials():
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_ARN)
        secret = json.loads(response['SecretString'])
        if 'username' not in secret or 'password' not in secret:
            raise ValueError("Secret must contain 'username' and 'password'")
        return secret['username'], secret['password']
    except ClientError as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise e

def to_iso8601(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            # Try parsing common timestamp format
            parsed = datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
            return parsed.isoformat() + 'Z'
        except (ValueError, TypeError):
            return dt  # fallback to original string
    if isinstance(dt, datetime.datetime):
        return dt.isoformat() + 'Z'
    if isinstance(dt, datetime.date):
        return dt.isoformat()
    return str(dt)

def fetch_users(username, password):
    conn = None
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=username,
            password=password,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, username, email, first_name, last_name, date_of_birth,
                       is_active, created_at, updated_at
                FROM user_base
                WHERE is_active = 1
            """)
            users = cursor.fetchall()
            logger.info(f"Fetched {len(users)} active users from DB.")
            return users
    except pymysql.MySQLError as e:
        logger.error(f"DB error: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def to_q_document(user):
    # Prepare content as a base64-encoded blob
    text_content = (
        f"Username: {user['username']}\n"
        f"Email: {user['email']}\n"
        f"First Name: {user.get('first_name') or ''}\n"
        f"Last Name: {user.get('last_name') or ''}\n"
        f"Date of Birth: {user.get('date_of_birth') or ''}\n"
        f"Active: {'Yes' if user['is_active'] else 'No'}\n"
        f"Created At: {user['created_at']}\n"
        f"Updated At: {user['updated_at']}\n"
    )
    encoded_blob = base64.b64encode(text_content.encode('utf-8')).decode('utf-8')
    content = {"blob": encoded_blob}

    attributes = [
        {"name": "username", "value": {"stringValue": user['username']}},
        {"name": "email", "value": {"stringValue": user['email']}},
        {"name": "is_active", "value": {"longValue": int(user['is_active'])}},
        {"name": "created_at", "value": {"dateValue": to_iso8601(user['created_at'])}},
        {"name": "updated_at", "value": {"dateValue": to_iso8601(user['updated_at'])}},
    ]

    if user.get('first_name'):
        attributes.append({"name": "first_name", "value": {"stringValue": user['first_name']}})
    if user.get('last_name'):
        attributes.append({"name": "last_name", "value": {"stringValue": user['last_name']}})
    if user.get('date_of_birth'):
        attributes.append({"name": "date_of_birth", "value": {"dateValue": to_iso8601(user['date_of_birth'])}})

    title = f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip() or user['username']

    return {
        "id": str(user['user_id']),
        "title": title,
        "content": content,
        "attributes": attributes
    }

def push_users_to_q(users, sync_job_id=None):
    documents = [to_q_document(u) for u in users]
    total_docs = len(documents)
    logger.info(f"Uploading {total_docs} documents to Amazon Q Business.")

    batch_size = 100
    failed_docs = []

    for i in range(0, total_docs, batch_size):
        batch = documents[i:i+batch_size]
        params = {
            "applicationId": Q_APPLICATION_ID,
            "indexId": Q_INDEX_ID,
            "documents": batch
        }
        if sync_job_id:
            params["dataSourceSyncId"] = sync_job_id

        try:
            resp = q_client.batch_put_document(**params)
            if resp.get('failedDocuments'):
                logger.warning(f"Failed documents in batch starting at {i}: {resp['failedDocuments']}")
                failed_docs.extend(resp['failedDocuments'])
            else:
                logger.info(f"Batch starting at {i} uploaded successfully.")
        except ClientError as e:
            logger.error(f"Error uploading batch starting at {i}: {str(e)}")
            raise

    return {"total": total_docs, "failedDocuments": failed_docs}

def lambda_handler(event, context):
    logger.info("Lambda sync started.")

    try:
        # Start sync job
        try:
            start_resp = q_client.start_data_source_sync_job(
                applicationId=Q_APPLICATION_ID,
                indexId=Q_INDEX_ID,
                dataSourceId=Q_DATA_SOURCE_ID
            )
            sync_job_id = start_resp.get('executionId')
            logger.info(f"Started sync job with execution ID: {sync_job_id}")
        except ClientError as e:
            logger.warning(f"Cannot start sync job, continuing without: {str(e)}")
            sync_job_id = None

        username, password = get_db_credentials()
        users = fetch_users(username, password)

        if not users:
            logger.info("No active users to sync.")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No data to sync."})
            }

        push_result = push_users_to_q(users, sync_job_id)

        # Stop sync job
        if sync_job_id:
            try:
                q_client.stop_data_source_sync_job(
                    applicationId=Q_APPLICATION_ID,
                    indexId=Q_INDEX_ID,
                    dataSourceId=Q_DATA_SOURCE_ID,
                    executionId=sync_job_id
                )
                logger.info(f"Stopped sync job {sync_job_id}")
            except ClientError as e:
                logger.warning(f"Unable to stop sync job: {str(e)}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "User data sync complete.",
                "records_synced": push_result['total'],
                "failed_documents": push_result['failedDocuments'],
                "sync_job_id": sync_job_id
            })
        }

    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
