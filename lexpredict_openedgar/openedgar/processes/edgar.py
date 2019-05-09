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
from typing import Iterable
import logging
import os
# Project
import openedgar.clients.edgar
from config.settings.base import DOWNLOAD_PATH
from openedgar.clients.adl import ADLClient
from openedgar.clients.s3 import S3Client
from openedgar.clients.local import LocalClient
import openedgar.clients.local
import openedgar.parsers.edgar
from openedgar.models import FilingDocument, SearchQueryTerm, SearchQuery, FilingIndex
from openedgar.tasks import process_filing_index, search_filing_document_sha1

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)


def download_filing_index_data(year: int = None, quarter: int = None, month: int = None):
    """
    Download all filing index data.
    :param month:
    :param quarter:
    :param year:
    :return:
    """
    # Get filing index list
    if year is not None:
        if month is not None:
            filing_index_list = openedgar.clients.edgar.list_index_by_month(year, month)
        elif quarter is not None:
            filing_index_list = openedgar.clients.edgar.list_index_by_quarter(year, quarter)
        else:
            filing_index_list = openedgar.clients.edgar.list_index_by_year(year)
    else:
        filing_index_list = openedgar.clients.edgar.list_index()

    path_list = []
    configured_client = os.environ["CLIENT_TYPE"]
    logger.info("Configured client is: {}".format(configured_client))
    path_prefix = str()

    if configured_client is None or configured_client == "S3":
        # Create S3 client
        download_client = S3Client()
    elif configured_client == "ADL":
        download_client = ADLClient()
    else:
        download_client = LocalClient()
    path_prefix = DOWNLOAD_PATH

    # Now iterate through list to check if already on S3
    for filing_index_path in filing_index_list:
        # Cleanup path
        if filing_index_path.startswith("/Archives/"):
            file_path = os.path.join(path_prefix, filing_index_path[len("/Archives/"):])
        else:
            file_path = os.path.join(path_prefix, filing_index_path)

        # Check if exists in database
        try:
            filing_index = FilingIndex.objects.get(edgar_url=filing_index_path)
            is_processed = filing_index.is_processed
            logger.debug("Index {0} already exists in DB.".format(filing_index_path))
        except FilingIndex.DoesNotExist:
            is_processed = False
            logger.debug("Index {0} does not exist in DB.".format(filing_index_path))

        # Check if exists; download and upload to S3 if missing
        if not download_client.path_exists(file_path):
            # Download
            buffer, _ = openedgar.clients.edgar.get_buffer(filing_index_path)

            # Upload
            download_client.put_buffer(file_path, buffer)

            logger.debug("Retrieved {0} and uploaded to S3.".format(filing_index_path))
            path_list.append((file_path, True, is_processed))
        else:
            logger.debug("Index {0} already exists on S3.".format(filing_index_path))
            path_list.append((file_path, False, is_processed))

    # Return list of updates
    return path_list


def process_all_filing_index(year: int = None, quarter: int = None, month: int = None,
                             form_type_list: Iterable[str] = None, new_only: bool = False,
                             store_raw: bool = True, store_text: bool = True, store_processed: bool = True):
    """
    Process all filing index data.
    :type year: optional year to process
    :param form_type_list:
    :param new_only:
    :param store_raw:
    :param store_text:
    :param store_processed:
    :return:
    """
    # Get the list of file paths
    file_path_list = download_filing_index_data(year, quarter, month)

    client_type = os.environ["CLIENT_TYPE"] or "S3"

    # Process each file
    for s3_path, _, is_processed in file_path_list:
        # Skip if only processing new files and this one is old
        if new_only and not is_processed:
            logger.info("Processing filing index for {0}...".format(s3_path))
            _ = process_filing_index.delay(client_type, s3_path, form_type_list=form_type_list, store_raw=store_raw,
                                           store_text=store_text, store_processed=store_processed)
        elif not new_only:
            logger.info("Processing filing index for {0}...".format(s3_path))
            _ = process_filing_index.delay(client_type, s3_path, form_type_list=form_type_list, store_raw=store_raw,
                                           store_text=store_text, store_processed=store_processed)
        else:
            logger.info("Skipping process_filing_index for {0}...".format(s3_path))


def search_filing_documents(term_list: Iterable[str], form_type_list: Iterable[str] = None, sequence: int = None,
                            case_sensitive: bool = False,
                            token_search: bool = False, stem_search: bool = False):
    """
    Search a filing document by sha1 hash.
    :param term_list: list of terms
    :param form_type_list:
    :param sequence:
    :param case_sensitive:
    :param token_search:
    :param stem_search:
    :return:
    """

    # Create query object
    search_query = SearchQuery()
    search_query.form_type = ";".join(form_type_list)
    search_query.save()

    # Create terms
    # search_term_list = []
    for term in term_list:
        search_term = SearchQueryTerm()
        search_term.search_query = search_query
        search_term.term = term
        search_term.save()
    # SearchQueryTerm.objects.bulk_create(search_term_list)

    # Get doc list to search
    document_list = FilingDocument.objects
    if form_type_list is not None:
        document_list = document_list.filter(filing__form_type__in=form_type_list)
    if sequence is not None:
        document_list = document_list.filter(sequence=sequence)

    # Create distributed search tasks
    n = 0
    for document in document_list.all():
        search_filing_document_sha1.delay(document.sha1, term_list, search_query.id, document.id,
                                          case_sensitive=case_sensitive, token_search=token_search,
                                          stem_search=stem_search)
        n += 1

    logger.debug("Searching {0} documents for {1} terms...".format(n, len(term_list)))


def export_filing_document_search(search_query_id: int, output_file_path: str):
    """
    Export a filing document search to a CSV file.
    :param search_query_id:
    :param output_file_path:
    :return:
    """
    # Local imports
    import django.db
    import pandas

    # Create query string
    query_string = """SELECT f.accession_number, f.date_filed, f.company_id, ci.name, ci.sic, ci.state_location, 
f.form_type, fd.sequence, fd.description, fd.sha1, sqt.term, sqr.count
FROM sec_edgar_searchqueryresult sqr
JOIN sec_edgar_searchqueryterm sqt ON sqt.id = sqr.term_id
JOIN sec_edgar_filingdocument fd ON fd.id = sqr.filing_document_id
JOIN sec_edgar_filing f ON f.id = fd.filing_id
JOIN sec_edgar_companyinfo ci ON ci.company_id = f.company_id AND ci.date = f.date_filed 
WHERE sqr.search_query_id = {0}
ORDER BY f.date_filed, f.company_id
""".format(search_query_id)
    query_df = pandas.read_sql(query_string, django.db.connection)
    query_df.to_csv(output_file_path, encoding="utf-8", index=False)
