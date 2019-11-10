# cSpell:words cloudinary, botocore, boto, uploader, vendored
"""
   This code fits AWS Lambda to fire on S3 events notifications
   Please see documentation and latest release at https://github.com/yuval-cloudinary/ftp2cld
   Make sure to set the s3 bucket to accept Cloudinary GetObject requests, and to fire event notifications
"""
import random
from botocore.vendored import requests
from os.path import splitext
from os import environ
import cloudinary
from cloudinary.uploader import upload, destroy
import logging
import urllib.parse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def optional_environ(env_var):
    """
    Return environment variable, or empty string if the variable was not defined
    """
    if env_var in environ:
        return environ[env_var]
    return ""


def skip_reload_same_etag(resource_type, cld_type, cld_public_id, event_etag):
    """
    Identify an attempt to re-upload an object with identical content
    Make sure to read all the gotchas in the README.md before enabling it
    """
    # using cache busting to avoid ETAG caching for short-cycle regret
    url = "{}/{}/{}/v{}/{}".format(
        environ["cld_delivery_url"], resource_type, cld_type, random.randint(2, 9999999999), cld_public_id)
    head_result = requests.head(url)
    return head_result.status_code < 400 and "etag" in head_result.headers and ((""" + event_etag + """) == head_result.headers["etag"])


def helper_get_resource_type_from_extension(extension):
    """
    Calculates the resource_type, to support accurate public_id, which
    in turn, is required for deletion and for searching.
    Searching is required in order to get the cld_type (we do not assume 'upload')
    """
    resource_type = "raw"
    # spell-checker: disable
    image_extentions = ["ai", "gif", "webp", "bmp", "djvu", "ps", "ept", "eps", "eps3", "flif", "heif", "heic", "ico", "jpg",
                        "jpe", "jpeg", "jp2", "wdp", "jxr", "hdp", "pdf", "png", "psb", "psd", "arw", "cr2", "svg", "tga",
                        "tif", "tiff", "indd", "idml"]
    video_extentions = ["3g2", "3gp", "avi", "flv", "m2ts", "mov", "mkv", "mp4", "mpeg",
                           "ogv", "webm", "wmv", "aac", "aif", "aiff", "amr", "flac", "m4a", "mp3", "ts", "ogg", "wav"]
    # spell-checker:enable
    if (extension in image_extentions):
        resource_type = "image"
    elif (extension in video_extentions):
        resource_type = "video"
    return resource_type


def helper_search_cld_type(key, resource_type, cld_public_id):
    """
    Calculate mandatory cld properties that identifies the object mapping
    """
    cld_type = "upload"
    file_not_found = True
    result = cloudinary.Search().expression(
        "resource_type:" + resource_type + " AND public_id=" + cld_public_id) \
        .max_results('1') \
        .execute()
    file_not_found = True
    if "resources" in result and len(result['resources']) == 1 and result['resources'][0]['public_id'] == cld_public_id:
            cld_type = result["resources"][0]["type"]
            file_not_found = False
    return cld_type, file_not_found


def upload_file(bucket_name, key, cld_public_id, resource_type, cld_type, event_size):
    """
    A wrapper for the SDK upload method
    """
    status_code, status_msg = 500, "upload_file failed"
    try:
        if event_size < 100000000:
            upload_result = cloudinary.uploader.upload(
                's3://' + bucket_name + '/' + urllib.parse.unquote_plus(key),
                public_id=cld_public_id,
                resource_type=resource_type,
                type=cld_type,
                notification_url=optional_environ("notification_url"))
        else:
            upload_result = cloudinary.uploader.upload_large(
                's3://' + bucket_name + '/' + urllib.parse.unquote_plus(key),
                public_id=cld_public_id,
                resource_type=resource_type,
                type=cld_type,
                notification_url=optional_environ("notification_url"))
        # etags can behave differently on different encryption storage types and multi-part uploads, thus not a viable solution
        if "bytes" in upload_result and upload_result["bytes"] == event_size:
            status_code, status_msg = 200, "OK"
        else:
            status_code, status_msg = 500, "Upload to cld failed"
    except Exception as e:
        if isinstance(e.args[0], int) and e.args[0] == 2:
            status_code, status_msg = 404, "File not found on S3"
        elif isinstance(e.args[0], str) and e.args[0].endswith('Access Denied'):
            status_code, status_msg = 401, "Access denied on S3"
        else:
            status_code, status_msg = 500, "Upload_file has failed"
            logger.error(e)
    return status_code, status_msg


def delete_file(key, resource_type, cld_type, cld_public_id):
    """
    A wrapper for the SDK destroy method
    """
    status_code, status_msg = 500, "delete_file failed"
    destroy_result = destroy(public_id=cld_public_id,
                             resource_type=resource_type,
                             type=cld_type,
                             invalidate=True)
    if destroy_result['result'] == "not found":
        # We should not arrive here usually, as there is a prelimnary search
        status_code, status_msg = 404, "File not found on Cloudinary while trying to delete"
    elif destroy_result['result'] == "ok":
        status_code, status_msg = 200, "OK"
    return status_code, status_msg


def sync_file(s3_event_type, bucket_name, key, s3_event_body):
    """
    Logic to convert the s3 notification into a decision between
    two cld actions: Upload or Delete object
    """
    status_code, status_msg = 405, "Event was skipped"
    create_flag = \
        (s3_event_type[0] == "ObjectCreated" and s3_event_type[1] != "Post") or \
        (s3_event_type[0] ==
            "ObjectRestore" and s3_event_type[1] == "Completed")
    delete_flag = \
        optional_environ("upload_only_mode").lower() != "true" and \
        s3_event_type[0] == "ObjectRemoved"
             # and s3_event_type[1] == "DeleteMarker")
    # map s3 location to cld location
    splitext_key = splitext(key)
    cld_public_id = urllib.parse.unquote_plus(splitext_key[0].replace(
        environ["s3_sync_root"], environ["cld_sync_root"], 1))
    resource_type = helper_get_resource_type_from_extension(splitext_key[1][1:])
    if resource_type == 'raw':
        cld_public_id += splitext_key[1]
    cld_type, file_not_found = helper_search_cld_type(key, resource_type, cld_public_id)
    logger.info(bucket_name + ", " + cld_public_id +
                ", create = " + str(int(create_flag)) + ", delete = " + str(int(delete_flag)))
    if create_flag:
        if optional_environ("skip_reload_same_etag").lower() == "true" and \
                skip_reload_same_etag(resource_type, cld_type, cld_public_id, s3_event_body["object"]["eTag"]):
            status_code, status_msg = 304, "same eTag"
        if status_code != 304:
            status_code, status_msg = upload_file(
                bucket_name, key, cld_public_id, resource_type, cld_type, s3_event_body["object"]["size"])
    elif delete_flag:
        if file_not_found:
            status_code, status_msg = 404, "File not found on Cloudinary"
        else:
            status_code, status_msg = delete_file(key, resource_type, cld_type, cld_public_id)
    return status_code, status_msg


def lambda_handler(event, context):
    """
    This is the entry point and need to be specified in the Lambda configuration.
    It runs sanity tests and validations before starting to sync.
    """
    status_code, status_msg = 405, "Event was skipped"
    try:
        s3_event_type = event["Records"][0]["eventName"].split(":")
        s3_event_body = event["Records"][0]["s3"]
        bucket_name = s3_event_body["bucket"]["name"]
        if bucket_name.find('.') > -1:
            raise Exception('Bucket name with period is not supported')
        key = s3_event_body["object"]["key"]
        if (urllib.parse.unquote_plus(key).startswith(environ["s3_sync_root"])):
            status_code, status_msg = sync_file(
                s3_event_type, bucket_name, key, s3_event_body)
        else:
            status_code, status_msg = 403, "Forbidden - S3 event came from external folder to the configured s3_sync_root"
    except Exception as e:
        if isinstance(e.args[0], str) and e.args[0] == 'Bucket name with period is not supported':
            status_code, status_msg = 501, e.args[0]
        else:
            status_code, status_msg = 500, "Invalid S3 event"
            logger.error(e)
    logger.info('Returned: ' + str(status_code) + ', ' + status_msg)
    return {
        "statusCode": status_code,
        "body": status_msg
    }
