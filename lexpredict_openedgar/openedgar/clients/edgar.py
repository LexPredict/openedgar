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
import urllib.parse
import time

# Packages
import dateutil.parser
import lxml.html
import requests

# Project
from typing import Union

from config.settings.base import HTTP_SEC_HOST, HTTP_FAIL_SLEEP, HTTP_SEC_INDEX_PATH, HTTP_SLEEP_DEFAULT

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)


def get_buffer(remote_path: str, base_path: str = HTTP_SEC_HOST):
    """
    Retrieve a remote path to memory.
    :param remote_path: remote path on EDGAR to retrieve
    :param base_path: base path to prepend if not default EDGAR path
    :return: file_buffer, last_modified_date
    """
    # Log entrance
    logger.info("Retrieving remote path {0} to memory".format(remote_path))

    # Build URL
    remote_uri = urllib.parse.urljoin(base_path, remote_path.lstrip("/"))

    # Try to retrieve the file
    complete = False
    failures = 0
    file_buffer = None
    last_modified_date = None

    while not complete:
        try:
            with requests.Session() as s:
                r = s.get(remote_uri)
                if 'Last-Modified' in r.headers:
                    try:
                        last_modified_date = dateutil.parser.parse(r.headers['Last-Modified']).date()
                    except Exception as e:  # pylint: disable=broad-except
                        logger.error("Unable to update last modified date for {0}: {1}".format(remote_path, e))

                file_buffer = r.content
                complete = True

                # Sleep if set gt0
                if HTTP_SLEEP_DEFAULT > 0:
                    time.sleep(HTTP_SLEEP_DEFAULT)
        except Exception as e:  # pylint: disable=broad-except
            # Handle and sleep
            if failures < len(HTTP_FAIL_SLEEP):
                logger.warning("File {0}, failure {1}: {2}".format(remote_path, failures, e))
                time.sleep(HTTP_FAIL_SLEEP[failures])
                failures += 1
            else:
                logger.error("File {0}, failure {1}: {2}".format(remote_path, failures, e))
                return file_buffer, last_modified_date

    if b"SEC.gov | Request Rate Threshold Exceeded" in file_buffer:
        raise RuntimeError("Exceeded SEC request rate threshold; invalid data retrieved")
    elif b"SEC.gov | File Not Found Error Alert (404)" in file_buffer:
        raise RuntimeError("HTTP 404 for requested path")
    elif b"<Error><Code>AccessDenied</Code><Message>Access Denied</Message><RequestId>" in file_buffer:
        raise RuntimeError("Access denied accessing path")

    # Log successful exit
    if complete:
        logger.info("Successfully retrieved file {0}; {1} bytes".format(remote_path, len(file_buffer)))

    return file_buffer, last_modified_date


def list_path(remote_path: str):
    """
    List a path on the EDGAR data store.
    :param remote_path: URL path to list
    :return:
    """
    # Log entrance
    logger.info("Retrieving directory listing from {0}".format(remote_path))
    remote_buffer, _ = get_buffer(remote_path)

    # Parse the index listing
    if remote_buffer is None:
        logger.warning("list_path for {0} was passed None buffer".format(remote_path))
        return []

    # Parse buffer to HTML
    html_doc = lxml.html.fromstring(remote_buffer)

    try:
        # Find links in directory listing
        link_list = html_doc.get_element_by_id("main-content").xpath(".//a")
        good_link_list = [l for l in link_list if "Parent Directory" not in
                          lxml.html.tostring(l, method="text", encoding="utf-8").decode("utf-8")]
        good_url_list = []

        # Populate new URL list
        for l in good_link_list:
            # Get raw HREF
            href = l.attrib["href"]
            if href.startswith("/"):
                good_url_list.append(href)
            else:
                good_url_list.append("/".join(s for s in [remote_path, href.lstrip("/")]))
    except KeyError as e:
        logger.error("Unable to find main-content tag in {0}; {1}".format(remote_path, e))
        return None

    # Log
    logger.info("Successfully retrieved {0} links from {1}".format(len(good_url_list), remote_path))
    return good_url_list


def list_index_by_year(year: int):
    """
    Get list of index files for a given year.
    :param year: filing year to retrieve
    :return:
    """
    # Log entrance
    logger.info("Locating form index list for {0}".format(year))

    # Form index list
    year = str(year)
    form_index_list = []

    # Get year directory list
    year_index_uri = urllib.parse.urljoin(HTTP_SEC_INDEX_PATH, str(year) + "/")
    year_root_list = list_path(year_index_uri)
    print(year_root_list)

    # Get quarters
    quarter_list = [f for f in year_root_list if "/QTR" in f]

    # Iterate over quarters
    for quarter in quarter_list:
        quarter_root_list = list_path(quarter)
        form_index_list.extend([q for q in quarter_root_list if "/form." in q.lower()])

    # Cleanup double /
    for i in range(len(form_index_list)):
        form_index_list[i] = form_index_list[i].replace("//", "/")

    # Log exit
    logger.info("Successfully located {0} form index files for {1}".format(len(form_index_list), year))

    # Return
    return form_index_list


def list_index(min_year: int = 1950, max_year: int = 2050):
    """
    Get the list of form index files on SEC HTTP.
    :param min_year: min filing year to begin listing
    :param max_year: max filing year to list
    :return:
    """
    # Log entrance
    logger.info("Retrieving form index list")

    # Retrieve lists
    form_index_list = []
    root_list = list_path(HTTP_SEC_INDEX_PATH)

    # Iterate over all files in root
    for root_file in root_list:
        # Check if it's a year
        try:
            # Try for a year folder
            last_token = root_file.strip("/").split("/")[-1]
            year = int(last_token)
            if year < min_year or year > max_year:
                logger.info("Skipping year {0}".format(root_file))
                continue

            # Parse if it is
            year_form_list = list_index_by_year(year)
            form_index_list.extend(year_form_list)

        except ValueError as e:
            # Else, non-year
            logger.error(e)
            if root_file.startswith("form."):
                form_index_list.append(root_file)

    # Log exit
    logger.info("Successfully located {0} form index files".format(len(form_index_list)))

    # Return
    return form_index_list


def get_company(cik: Union[int, str]):
    """
    Get company information by CIK.
    :param cik: company CIK
    :return:
    """

    # Log entrance
    logger.info("Retrieving company info for CIK={0}".format(cik))

    # Setup company URL
    company_url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={0}".format(cik)

    # Retrieve buffer
    remote_buffer = requests.get(company_url).content

    # Parse buffer to HTML
    html_doc = lxml.html.fromstring(remote_buffer)
    content_div = html_doc.get_element_by_id("contentDiv")
    company_info_div = list(content_div)[1]

    # Extract key fields
    company_data = {}

    try:
        raw_address = lxml.html.tostring(list(company_info_div)[0], method="text",
                                         encoding="utf-8").decode("utf-8")
        mailing_address = " ".join(raw_address.splitlines()[1:]).strip()
        company_data["mailing_address"] = mailing_address
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Unable to parse mailing_address: {0}".format(e))
        company_data["mailing_address"] = None

    try:
        raw_address = lxml.html.tostring(list(company_info_div)[1], method="text",
                                         encoding="utf-8").decode("utf-8")
        business_address = " ".join(raw_address.splitlines()[1:]).strip()
        company_data["business_address"] = business_address
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Unable to parse business_address: {0}".format(e))
        company_data["business_address"] = None

    try:
        company_data["name"] = list(list(company_info_div)[2])[0].text.strip()
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Unable to parse name: {0}".format(e))
        company_data["name"] = None

    try:
        ident_info_p = list(list(company_info_div)[2])[1]
        company_data["sic"] = list(ident_info_p)[1].text
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Unable to parse SIC: {0}".format(e))
        company_data["sic"] = None

    try:
        ident_info_p = list(list(company_info_div)[2])[1]
        company_data["state_location"] = list(ident_info_p)[3].text
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Unable to parse SIC: {0}".format(e))
        company_data["state_location"] = None

    try:
        ident_info_p = list(list(company_info_div)[2])[1]
        company_data["state_incorporation"] = list(ident_info_p)[4].text
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Unable to parse SIC: {0}".format(e))
        company_data["state_incorporation"] = None

    return company_data


def get_cfia_index():
    """
    Get index of CFIA tables from 2006 for SIC/CIK lookup.
    :return:
    """
    # Log entrance
    logger.info("Retrieving CFIA 2006 index values")

    # Retrieve page and parse to HTML
    remote_buffer = requests.get("https://www.sec.gov/divisions/corpfin/organization/cfia.shtml").content
    html_doc = lxml.html.fromstring(remote_buffer)

    # Get index values
    index_values = [a.attrib['href'].split('-').pop()[:-4] for a in html_doc.findall(".//a") if
                    a.attrib['href'].startswith('cfia-')]
    return index_values


def get_cfia_table(index: str):
    """
    Get a table of CFIA 2006 data given an index to lookup.
    :param index: index,  e.g., M or 123
    :return:
    """

    # Log entrance
    logger.info("Retrieving CFIA 2006 CIK/SIC values for index={0}".format(index))

    # Get remote buffer and parse to HTML
    cfia_url = "https://www.sec.gov/divisions/corpfin/organization/cfia-{0}.htm".format(index)
    remote_buffer = requests.get(cfia_url).content
    html_doc = lxml.html.fromstring(remote_buffer)

    # Parse table into list of tuples
    table_element = html_doc.get_element_by_id("cos")
    table_data = []
    for row in table_element.findall(".//tr"):
        table_data.append((list(row)[0].text,
                           list(row)[1].text,
                           list(row)[2].text))

    return table_data


def get_cik_path(cik):
    """
    Get path on EDGAR or S3 for a given CIK.
    :param cik: company CIK
    :return:
    """
    return "edgar/data/{0}/".format(cik)
