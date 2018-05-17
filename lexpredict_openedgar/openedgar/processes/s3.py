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

from config.settings.base import S3_BUCKET
import openedgar.clients.edgar
import openedgar.clients.s3

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)


def is_access_denied_file(remote_path: str, client=None):
    """
    Check if the given file is S3 access denied XML
    :param remote_path:
    :param client:
    :return:
    """
    # Create client if not passed
    buffer = openedgar.clients.s3.get_buffer(remote_path, client)
    if b"<Error><Code>AccessDenied</Code><Message>Access Denied</Message><RequestId>" in buffer:
        return True
    else:
        return False


def is_empty_file(remote_path: str, client=None):
    """
    Check if the given file is empty
    :param remote_path:
    :param client:
    :return:
    """
    # Create client if not passed
    if client is None:
        client = openedgar.clients.s3.get_client()

    # HEAD object
    s3_object = client.head_object(Bucket=S3_BUCKET, Key=remote_path)

    if s3_object["ContentLength"] == 0:
        return True
    else:
        return False


def is_rate_limited_file(remote_path: str, size_only: bool = True, client=None):
    """
    Check if the given file is rate-limited.
    :param remote_path: path to check
    :param size_only: whether to use size alone
    :param client: optional client to re-use
    :return:
    """
    # Create client if not passed
    if client is None:
        client = openedgar.clients.s3.get_client()

    # Perform requested check type
    if size_only:
        # HEAD object
        s3_object = client.head_object(Bucket=S3_BUCKET, Key=remote_path)

        if s3_object["ContentLength"] == 2139:
            return True
        else:
            return False
    else:
        # GET object
        s3_object = client.get_object(Bucket=S3_BUCKET, Key=remote_path)

        buffer = s3_object["Body"].read()
        if b"SEC.gov | Request Rate Threshold Exceeded" in buffer:
            return True
        else:
            return False


def clean_rate_limited_files(cik: int = None, fix: bool = True, client=None):
    """
    Clean any rate limited files on S3, optionally filtering by CIK.
    :param cik: CIK to filter by
    :param fix: whether to fix files by downloading
    :param client: optional S3 client to re-use
    :return:
    """
    # Create client if not passed
    if client is None:
        logger.info("Creating fresh S3 client...")
        client = openedgar.clients.s3.get_client()

    # Track cleaned files
    file_list = []

    # Only handle per-CIK case
    if cik is None:
        # Get list of CIKs under top-level folder
        cik_path_list = openedgar.clients.s3.list_path_folders("edgar/data/", client=client)
    else:
        # Otherwise populate list with single CIK
        cik_path_list = [openedgar.clients.edgar.get_cik_path(cik)]

    logger.info("Checking {0} CIKs for bad rate-limited files...".format(len(cik_path_list)))

    for cik_path in cik_path_list:
        for remote_path in openedgar.clients.s3.list_path(cik_path, client=client):
            # Check if bad
            is_bad = is_rate_limited_file(remote_path, client=client)

            # Track if bad
            if is_bad:
                logger.info("Found bad file: {0}".format(remote_path))
                file_list.append(remote_path)

                # Fix if requested
                if fix:
                    logger.info("Fixing file: {0}".format(remote_path))

                    # Ensure path is correct
                    if not remote_path.strip("/").startswith("Archives/"):
                        edgar_url = "/Archives/{0}".format(remote_path.strip("/"))
                    else:
                        edgar_url = remote_path

                    # Get buffer from EDGAR
                    buffer, _ = openedgar.clients.edgar.get_buffer(edgar_url)

                    # Replace bad remote path on S3
                    openedgar.clients.s3.put_buffer(remote_path, buffer, client)

                    # Log fix
                    logger.info("Replaced {0} with new {1}-byte file...".format(remote_path, len(buffer)))

    logger.info("Located {0} bad files...".format(len(file_list)))
    return file_list


def clean_empty_files(cik: int = None, fix: bool = True, client=None):
    """
    Clean any empty files on S3, optionally filtering by CIK.
    :param cik: CIK to filter by
    :param fix: whether to fix files by downloading
    :param client: optional S3 client to re-use
    :return:
    """
    # Create client if not passed
    if client is None:
        logger.info("Creating fresh S3 client...")
        client = openedgar.clients.s3.get_client()

    # Track cleaned files
    file_list = []

    # Only handle per-CIK case
    if cik is None:
        # Get list of CIKs under top-level folder
        cik_path_list = openedgar.clients.s3.list_path_folders("edgar/data/", client=client)
    else:
        # Otherwise populate list with single CIK
        cik_path_list = [openedgar.clients.edgar.get_cik_path(cik)]

    logger.info("Checking {0} CIKs for bad zero-byte files...".format(len(cik_path_list)))

    for cik_path in cik_path_list:
        for remote_path in openedgar.clients.s3.list_path(cik_path, client=client):
            # Check if bad
            is_bad = is_empty_file(remote_path, client=client)

            # Track if bad
            if is_bad:
                logger.info("Found bad file: {0}".format(remote_path))
                file_list.append(remote_path)

                # Fix if requested
                if fix:
                    logger.info("Fixing file: {0}".format(remote_path))

                    # Ensure path is correct
                    if not remote_path.strip("/").startswith("Archives/"):
                        edgar_url = "/Archives/{0}".format(remote_path.strip("/"))
                    else:
                        edgar_url = remote_path

                    # Get buffer from EDGAR
                    buffer, _ = openedgar.clients.edgar.get_buffer(edgar_url)

                    # Replace bad remote path on S3
                    if len(buffer) > 0:
                        openedgar.clients.s3.put_buffer(remote_path, buffer, client)

                        # Log fix
                        logger.info("Replaced {0} with new {1}-byte file...".format(remote_path, len(buffer)))
                    else:
                        # Log error
                        logger.error("Unable to locate non-zero length replacement for {0}".format(remote_path))

    logger.info("Located {0} bad files...".format(len(file_list)))
    return file_list


def clean_access_denied_files(cik: int = None, fix: bool = True, client=None):
    """
    Clean any files on S3 that record an S3 Access Denied response, optionally filtering by CIK.
    :param cik: CIK to filter by
    :param fix: whether to fix files by downloading
    :param client: optional S3 client to re-use
    :return:
    """
    # Create client if not passed
    if client is None:
        logger.info("Creating fresh S3 client...")
        client = openedgar.clients.s3.get_client()

    # Track cleaned files
    file_list = []

    # Only handle per-CIK case
    if cik is None:
        # Get list of CIKs under top-level folder
        cik_path_list = openedgar.clients.s3.list_path_folders("edgar/data/", client=client)
    else:
        # Otherwise populate list with single CIK
        cik_path_list = [openedgar.clients.edgar.get_cik_path(cik)]

    logger.info("Checking {0} CIKs for bad access denied files...".format(len(cik_path_list)))

    for cik_path in cik_path_list:
        for remote_path in openedgar.clients.s3.list_path(cik_path, client=client):
            # Check if bad
            is_bad = is_access_denied_file(remote_path, client=client)

            # Track if bad
            if is_bad:
                logger.info("Found bad file: {0}".format(remote_path))
                file_list.append(remote_path)

                # Fix if requested
                if fix:
                    logger.info("Removing file: {0}".format(remote_path))

                    # Replace bad remote path on S3
                    success = openedgar.clients.s3.delete_path(remote_path, client)

                    # Log fix
                    if success:
                        logger.info("Deleted {0}...".format(remote_path))
                    else:
                        logger.error("Unable to delete {0}...".format(remote_path))
            else:
                logger.info("No issues found with {0}".format(remote_path))

    logger.info("Located {0} bad files...".format(len(file_list)))
    return file_list
