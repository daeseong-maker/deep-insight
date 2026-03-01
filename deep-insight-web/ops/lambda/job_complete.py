"""
Lambda handler: Deep Insight Job Complete

Triggered by S3 PUT event when token_usage.json is uploaded at:
  s3://{bucket}/deep-insight/fargate_sessions/{session_id}/output/token_usage.json

Logic:
  1. Extract session_id from S3 key path
  2. Read token_usage.json for execution stats
  3. List artifacts for output file list
  4. Find DynamoDB record via SessionIdIndex GSI
  5. Idempotency guard: skip if already Success
  6. Update DynamoDB record with Success status and stats
  7. Publish SNS notification

Environment variables:
  DYNAMODB_TABLE_NAME: DynamoDB table name (e.g., deep-insight-jobs)
  SNS_TOPIC_ARN: SNS topic ARN for notifications
"""

import json
import logging
import os
import time
from urllib.parse import unquote_plus

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")


def handler(event, context):
    """Process S3 PUT event for token_usage.json upload."""
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        logger.info(f"Processing: s3://{bucket}/{key}")

        try:
            _process_job_complete(bucket, key)
        except Exception as e:
            logger.error(f"Failed to process {key}: {e}", exc_info=True)

    return {"statusCode": 200, "body": "OK"}


def _process_job_complete(bucket: str, key: str):
    """Process a single token_usage.json upload event."""

    # Step 1: Extract session_id from S3 key path
    # Key format: deep-insight/fargate_sessions/{session_id}/output/token_usage.json
    parts = key.split("/")
    try:
        session_idx = parts.index("fargate_sessions") + 1
        session_id = parts[session_idx]
    except (ValueError, IndexError):
        logger.error(f"Cannot extract session_id from key: {key}")
        return

    logger.info(f"Session ID: {session_id}")

    s3 = boto3.client("s3")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)

    # Step 2: Read token_usage.json
    token_data = _read_token_usage(s3, bucket, key)
    if not token_data:
        return

    # Step 3: List artifacts
    artifacts = _list_artifacts(s3, bucket, session_id)

    # Step 4: Find DynamoDB record via SessionIdIndex GSI
    job_record = _find_job_by_session_id(table, session_id)
    if not job_record:
        logger.warning(f"No DynamoDB record found for session_id={session_id}")
        return

    job_id = job_record["job_id"]
    logger.info(f"Found job_id={job_id} for session_id={session_id}")

    # Step 5: Idempotency guard
    if job_record.get("status") == "Success":
        logger.info(f"Job {job_id} already marked Success — skipping")
        return

    # Step 6: Update DynamoDB record
    ended_at = int(time.time())
    started_at = job_record.get("started_at", ended_at)
    elapsed_seconds = ended_at - started_at

    summary = token_data.get("summary", {})
    total_tokens = summary.get("total_tokens", 0)
    input_tokens = summary.get("total_input_tokens", 0)
    output_tokens = summary.get("total_output_tokens", 0)
    cache_read = summary.get("cache_read_input_tokens", 0)
    cache_write = summary.get("cache_write_input_tokens", 0)
    cache_hit_rate = round((cache_read / input_tokens * 100), 1) if input_tokens > 0 else 0

    # Find report file (prefer .docx over .txt)
    report_filename = ""
    report_path = ""
    txt_fallback = ""
    for f in artifacts:
        if f.endswith(".docx"):
            report_filename = f
            break
        if f.endswith(".txt") and not txt_fallback:
            txt_fallback = f
    if not report_filename:
        report_filename = txt_fallback
    if report_filename:
        report_path = f"deep-insight/fargate_sessions/{session_id}/artifacts/{report_filename}"

    table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=(
            "SET #s = :status, ended_at = :ended, elapsed_seconds = :elapsed, "
            "total_tokens = :tokens, input_tokens = :inp, output_tokens = :out, "
            "cache_read_input_tokens = :cread, cache_creation_input_tokens = :cwrite, "
            "cache_hit_rate = :cache, "
            "report_path = :rpath, report_filename = :rname, output_files = :files"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": "Success",
            ":ended": ended_at,
            ":elapsed": elapsed_seconds,
            ":tokens": total_tokens,
            ":inp": input_tokens,
            ":out": output_tokens,
            ":cread": cache_read,
            ":cwrite": cache_write,
            ":cache": int(cache_hit_rate),
            ":rpath": report_path,
            ":rname": report_filename,
            ":files": artifacts,
        },
    )
    logger.info(f"DynamoDB updated: job_id={job_id}, status=Success, elapsed={elapsed_seconds}s")

    # Step 7: Publish SNS notification
    _publish_notification(job_id, job_record, elapsed_seconds, total_tokens, cache_hit_rate, report_filename)


def _read_token_usage(s3, bucket: str, key: str) -> dict:
    """Read and parse token_usage.json from S3."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to read token_usage.json: {e}")
        return {}


def _list_artifacts(s3, bucket: str, session_id: str) -> list:
    """List artifact filenames for a session."""
    prefix = f"deep-insight/fargate_sessions/{session_id}/artifacts/"
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        filenames = []
        for obj in response.get("Contents", []):
            name = obj["Key"].removeprefix(prefix)
            if name:
                filenames.append(name)
        return filenames
    except Exception as e:
        logger.error(f"Failed to list artifacts: {e}")
        return []


def _find_job_by_session_id(table, session_id: str) -> dict:
    """Query SessionIdIndex GSI to find the job record by session_id."""
    try:
        response = table.query(
            IndexName="SessionIdIndex",
            KeyConditionExpression="session_id = :sid",
            ExpressionAttributeValues={":sid": session_id},
        )
        items = response.get("Items", [])
        if not items:
            return {}

        # GSI is KEYS_ONLY — need to get the full record
        job_id = items[0]["job_id"]
        result = table.get_item(Key={"job_id": job_id})
        return result.get("Item", {})
    except Exception as e:
        logger.error(f"Failed to query SessionIdIndex: {e}")
        return {}


def _publish_notification(job_id: str, job_record: dict, elapsed_seconds: int,
                          total_tokens: int, cache_hit_rate: float, report_filename: str):
    """Publish job completion notification to SNS topic."""
    if not SNS_TOPIC_ARN:
        return

    user_query = job_record.get("user_query", "")[:100]
    message = (
        "Deep Insight Job Completed\n"
        "\n"
        f"Job ID: {job_id}\n"
        f"Status: Success\n"
        f"Query: {user_query}\n"
        f"Duration: {elapsed_seconds}s\n"
        f"Tokens: {total_tokens:,}\n"
        f"Cache Hit: {cache_hit_rate}%\n"
        f"Report: {report_filename}\n"
    )

    try:
        sns = boto3.client("sns")
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="Deep Insight Job Completed",
            Message=message,
        )
        logger.info(f"SNS notification sent for job_id={job_id}")
    except Exception as e:
        logger.error(f"Failed to publish SNS notification: {e}")
