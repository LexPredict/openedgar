# Libraries
import logging
import os
import zlib
from typing import Union

from azure.storage.blob import BlockBlobService

from config.settings.base import BLOB_CONNECTION_STRING, BLOB_CONTAINER, S3_COMPRESSION_LEVEL

logger = logging.getLogger(__name__)
# Remove garbage logging from MS
logging.getLogger("azure.storage.common.storageclient").setLevel(logging.ERROR)

if os.environ["CLIENT_TYPE"] == "Blob":
    blob_service = BlockBlobService(connection_string=BLOB_CONNECTION_STRING)
    blob_service.create_container(BLOB_CONTAINER)


class BlobClient:

    def __init__(self):
        logger.info("Initialized Blob client")

    def path_exists(self, path: str, client=None):
        """
        Check if an Blob path exists
        :param path:
        :return: true if Blob object exists, else false
        """
        return blob_service.exists(BLOB_CONTAINER, path)

    def get_buffer(self, remote_path: str, client=None, deflate: bool = True):
        """
        Get a file from Blob  given a path and optional client.
        :param remote_path: Blob path under bucket
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return: buffer bytes/str
        """
        if remote_path[0] == '/':
            remote_path = remote_path[1:]
        buffer = blob_service.get_blob_to_bytes(BLOB_CONTAINER, remote_path).content
        if deflate:
            return zlib.decompress(buffer)
        else:
            return buffer

    def get_file(self, remote_path: str, local_path: str, client=None, deflate: bool = True):
        """
        Save a local file from Blob given a path and optional client.
        :param remote_path: Blob path under bucket
        :param local_path: local path to save to
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return:
        """
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

    def put_buffer(self, remote_path: str, buffer: Union[str, bytes], client=None, deflate: bool = True,
                   write_bytes=True):
        """
        Upload a buffer to AKS given a path.
        :param remote_path: AKS path
        :param buffer: buffer to upload
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return:
        """
        # Ensure we have bytes object
        if isinstance(buffer, str):
            upload_buffer = bytes(buffer, "utf-8")
        else:
            upload_buffer = buffer
        if remote_path[0] == '/':
            remote_path = remote_path[1:]
        if deflate:
            upload_buffer = zlib.compress(upload_buffer, S3_COMPRESSION_LEVEL)
        blob_service.create_blob_from_bytes(BLOB_CONTAINER, remote_path, upload_buffer)

    def put_file(self, remote_path: str, local_path: str, client=None, deflate: bool = True):
        """
        Save a local file from AKS.
        :param remote_path: AKS remote path
        :param local_path: local path to save to
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return:
        """
        with open(local_path, "rb") as in_file:
            self.put_buffer(remote_path, in_file.read(), client, deflate)
