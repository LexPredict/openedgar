# Libraries
import logging
from typing import Union
import adal

from msrestazure.azure_active_directory import AADTokenCredentials
from azure.datalake.store import core, lib, multithread
from config.settings.base import ADL_ACCOUNT, ADL_TENANT, ADL_CID, ADL_SECRET

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

authority_host_uri = 'https://login.microsoftonline.com'
authority_uri = authority_host_uri + '/' + ADL_TENANT
RESOURCE = 'https://management.core.windows.net/'

adlCreds = lib.auth(tenant_id=ADL_TENANT,
                    client_secret=ADL_SECRET,
                    client_id=ADL_CID,
                    resource=RESOURCE)

context = adal.AuthenticationContext(authority_uri, api_version=None)
mgmt_token = context.acquire_token_with_client_credentials(RESOURCE, ADL_CID, ADL_SECRET)
armCreds = AADTokenCredentials(mgmt_token, ADL_CID, resource=RESOURCE)

## Create a filesystem client object
adlsFileSystemClient = core.AzureDLFileSystem(adlCreds, store_name=ADL_ACCOUNT)


class ADLClient:

    def __init__(self):
        logger.info("Initialized AKS client")

    def path_exists(self, path: str, client=None):
        """
        Check if an AKS path exists
        :param path:
        :return: true if AKS object exists, else false
        """

        return adlsFileSystemClient.exists(path)

    def get_buffer(self, remote_path: str, client=None, deflate: bool = True):
        """
        Get a file from S3 given a path and optional client.
        :param remote_path: S3 path under bucket
        :param client: optional client to re-use
        :param deflate: whether to automatically zlib deflate contents
        :return: buffer bytes/str
        """

        with adlsFileSystemClient.open(remote_path, blocksize=2 ** 20) as f:
            return f.read()

    def get_file(self, remote_path: str, local_path: str, client=None, deflate: bool = True):
        """
        Save a local file from AKS given a path and optional client.
        :param remote_path: AKS path under bucket
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

        import tempfile

        temp = tempfile.NamedTemporaryFile(mode='w+b')

        try:
            # Ensure we have bytes object
            if isinstance(buffer, str):
                upload_buffer = bytes(buffer, "utf-8")
            elif isinstance(buffer, bytes):
                upload_buffer = buffer

            temp.write(upload_buffer)

            multithread.ADLUploader(adlsFileSystemClient, lpath=temp.name, rpath=remote_path, nthreads=64,
                                    overwrite=True, buffersize=4194304, blocksize=4194304)
        finally:
            temp.close()

    def put_file(self, remote_path: str, local_path: str):
        """
        Save a local file from AKS.
        :param remote_path: AKS remote path
        :param local_path: local path to save to
        :return:
        """
        multithread.ADLUploader(adlsFileSystemClient, lpath=local_path, rpath=remote_path, nthreads=64, overwrite=True,
                                buffersize=4194304, blocksize=4194304)
