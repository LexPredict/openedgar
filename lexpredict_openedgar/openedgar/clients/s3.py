"""
MIT License

Copyright (c) 2018 ContraxSuite, LLC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# Libraries
import logging

# Packages
import boto3
import botocore.exceptions

# Project
import zlib

from typing import Union

from config.settings.base import S3_ACCESS_KEY, S3_BUCKET, S3_COMPRESSION_LEVEL, S3_SECRET_KEY

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)


class S3Client:

    def __init__(self):
        logger.info("Initialized S3 client")

    def get_resource(self):
        """
        Get S3 resource.
        :return: returns boto3 S3 resource object
        """
        # Create S3 resource
        s3 = boto3.resource('s3', aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY)
        return s3

    def get_client(self):
        """
        Get S3 client.
        :return: returns boto3 S3 client object
        """
        # Create S3 client
        client = boto3.client('s3', aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY)
        return client

    def get_bucket(self):
        """
        Get S3 bucket
        :return: returns boto3 S3 bucket resource
        """
        # Get bucket
        s3 = boto3.resource('s3', aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY)
        bucket = s3.Bucket(S3_BUCKET)
        return bucket

    def path_exists(self, path: str, client=None):
        """
        Check if an S3 path exists
        :param path:
        :param client:
        :return: true if S3 object exists, else false
        """
        # Create S3 client if not already passed
        if client is None:
            client = self.get_client()

        try:
            client.head_object(Bucket=S3_BUCKET, Key=path)
            return True
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            else:
                logger.error("Unable to check if path {0} exists: {1}".format(path, e))

    def delete_path(self, path: str, client=None):
        """
        Remove a key (non-recursively) from an S3 path.
        :param path:
        :param client:
        :return: true if object deleted successfully, else false
        """
        # Create S3 client if not already passed
        if client is None:
            client = self.get_client()

        try:
            response = client.delete_object(Bucket=S3_BUCKET, Key=path)
            return response["ResponseMetadata"]["HTTPStatusCode"] == 204
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            else:
                logger.error("Unable to delete path {0}: {1}".format(path, e))

    def list_path(self, path: str, client=None):
        """
        List all contents *recursively* under a given path.
        :param path:
        :param client:
        :return: list of objects on path
        """
        # Get client
        if client is None:
            client = self.get_client()

        # Create paginator
        paginator = client.get_paginator('list_objects_v2')

        # Paginate through results
        path_objects = []
        for result in paginator.paginate(Bucket=S3_BUCKET, Delimiter='/', Prefix=path):
            for o in result.get("Contents"):
                path_objects.append(o["Key"])

        return path_objects

    def list_path_folders(self, path: str, client=None, limit: int = None):
        """
        List the "folder" under a given path, where folders are CommonPrefixes using the /
        delimiter under S3 key namespacing.
        :param path: remote path
        :param client: optional s3 client to re-use
        :param limit: maximum number of folders to list
        :return:
        """
        # Get client
        if client is None:
            client = self.get_client()

        # Create paginator and query
        folders = []
        paginator = client.get_paginator('list_objects_v2')
        query = paginator.paginate(Bucket=S3_BUCKET, Prefix=path, Delimiter='/')
        for result in query:
            for prefix in result.get('CommonPrefixes'):
                folders.append(prefix.get('Prefix'))

            # Return limit subset if requested
            if limit is not None:
                if len(folders) > limit:
                    return folders[0:limit]

        return folders

    def get_buffer(self, remote_path: str, client=None, deflate: bool = True):
        """
        Get a file from S3 given a path and optional client.
        :param remote_path: S3 path under bucket
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return: buffer bytes/str
        """
        # Get client
        if client is None:
            client = self.get_client()

        # Get object
        s3_object = client.get_object(Bucket=S3_BUCKET, Key=remote_path)

        # Retrieve body
        buffer = s3_object["Body"].read()

        # Deflate if requested
        if deflate:
            return zlib.decompress(buffer)
        else:
            return buffer

    def get_file(self, remote_path: str, local_path: str, client=None, deflate: bool = True):
        """
        Save a local file from S3 given a path and optional client.
        :param remote_path: S3 path under bucket
        :param local_path: local path to save to
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return:
        """
        # Open and write buffer
        with open(local_path, "wb") as out_file:
            out_file.write(self.get_buffer(remote_path, client, deflate))

    def get_buffer_segment(self, remote_path: str, start_pos: int, end_pos: int, client=None, deflate: bool = True):
        """
        Get a file from S3 given a path and optional client.
        :param remote_path: S3 path under bucket
        :param start_pos:
        :param end_pos:
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return:
        """
        # Retrieve buffer and return subset
        buffer = self.get_buffer(remote_path, client, deflate)
        return buffer[start_pos:end_pos]

    def put_buffer(self, remote_path: str, buffer: Union[str, bytes], client=None, deflate: bool = True):
        """
        Upload a buffer to S3 given a path and optional client.
        :param remote_path: S3 path under bucket
        :param buffer: buffer to upload
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return:
        """
        # Get client
        if client is None:
            client = self.get_client()

        # Ensure we have bytes object
        if isinstance(buffer, str):
            upload_buffer = bytes(buffer, "utf-8")
        elif isinstance(buffer, bytes):
            upload_buffer = buffer
        else:
            raise TypeError("buffer must be bytes or str")

        if deflate:
            upload_buffer = zlib.compress(upload_buffer, S3_COMPRESSION_LEVEL)

        # Upload
        response = client.put_object(Bucket=S3_BUCKET, Key=remote_path, Body=upload_buffer)
        return True if response["ResponseMetadata"]["HTTPStatusCode"] == 200 else False

    def put_file(self, remote_path: str, local_path: str, client=None, deflate: bool = True):
        """
        Save a local file from S3 given a path and optional client.
        :param remote_path: S3 path under bucket
        :param local_path: local path to save to
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return:
        """
        with open(local_path, "rb") as in_file:
            self.put_buffer(remote_path, in_file.read(), client, deflate)
