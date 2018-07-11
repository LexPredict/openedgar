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
import datetime
import hashlib
import logging
import tempfile
import os
import pathlib
from typing import Iterable, Union

# Packages
import dateutil.parser
import django.db.utils
from celery import shared_task

# Project
from config.settings.base import S3_DOCUMENT_PATH
from openedgar.clients.s3 import S3Client
from openedgar.clients.local import LocalClient
import openedgar.clients.edgar
import openedgar.parsers.edgar
from openedgar.models import Filing, CompanyInfo, Company, FilingDocument, SearchQuery, SearchQueryTerm, \
    SearchQueryResult, FilingIndex

# LexNLP imports
import lexnlp.nlp.en.tokens

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)


def create_filing_documents(documents, filing, store_raw: bool = True, store_text: bool = True):
    """
    Create filing document records given a list of documents
    and a filing record.
    :param documents: list of documents from parse_filing
    :param filing: Filing record
    :param store_raw: whether to store raw contents
    :param store_text: whether to store text contents
    :return:
    """
    # Get client if we're using S3
    if store_raw or store_text:
        client = openedgar.clients.s3.get_client()
    else:
        client = None

    # Iterate through documents
    document_records = []
    for document in documents:
        # Create DB object
        filing_doc = FilingDocument()
        filing_doc.filing = filing
        filing_doc.type = document["type"]
        filing_doc.sequence = document["sequence"]
        filing_doc.file_name = document["file_name"]
        filing_doc.content_type = document["content_type"]
        filing_doc.description = document["description"]
        filing_doc.sha1 = document["sha1"]
        filing_doc.start_pos = document["start_pos"]
        filing_doc.end_pos = document["end_pos"]
        filing_doc.is_processed = True
        filing_doc.is_error = len(document["content"]) > 0
        document_records.append(filing_doc)

        # Upload raw to S3 if requested
        if store_raw and len(document["content"]) > 0:
            raw_s3_path = pathlib.Path(S3_DOCUMENT_PATH, "raw", document["sha1"]).as_posix()
            if not openedgar.clients.s3.path_exists(raw_s3_path):
                openedgar.clients.s3.put_buffer(raw_s3_path, document["content"], client)
                logger.info("Uploaded raw file for filing={0}, sequence={1}, sha1={2}"
                            .format(filing, document["sequence"], document["sha1"]))
            else:
                logger.info("Raw file for filing={0}, sequence={1}, sha1={2} already exists on S3"
                            .format(filing, document["sequence"], document["sha1"]))

        # Upload text to S3 if requested
        if store_text and document["content_text"] is not None:
            text_s3_path = pathlib.Path(S3_DOCUMENT_PATH, "text", document["sha1"]).as_posix()
            if not openedgar.clients.s3.path_exists(text_s3_path):
                openedgar.clients.s3.put_buffer(text_s3_path, document["content_text"], client)
                logger.info("Uploaded text contents for filing={0}, sequence={1}, sha1={2}"
                            .format(filing, document["sequence"], document["sha1"]))
            else:
                logger.info("Text contents for filing={0}, sequence={1}, sha1={2} already exists on S3"
                            .format(filing, document["sequence"], document["sha1"]))

    # Create in bulk
    FilingDocument.objects.bulk_create(document_records)
    return len(document_records)


def create_filing_error(row, filing_path: str):
    """
    Create a Filing error record from an index row.
    :param row:
    :param filing_path:
    :return:
    """
    # Get vars
    cik = row["CIK"]
    company_name = row["Company Name"]
    form_type = row["Form Type"]

    try:
        date_filed = dateutil.parser.parse(str(row["Date Filed"])).date()
    except ValueError:
        date_filed = None
    except IndexError:
        date_filed = None

    # Create empty error filing record
    filing = Filing()
    filing.form_type = form_type
    filing.date_filed = date_filed
    filing.s3_path = filing_path
    filing.is_error = True
    filing.is_processed = False

    # Get company info
    try:
        company = Company.objects.get(cik=cik)

        try:
            _ = CompanyInfo.objects.get(company=company, date=date_filed)
        except CompanyInfo.DoesNotExist:
            # Create company info record
            company_info = CompanyInfo()
            company_info.company = company
            company_info.name = company_name
            company_info.sic = None
            company_info.state_incorporation = None
            company_info.state_location = None
            company_info.date = date_filed
            company_info.save()
    except Company.DoesNotExist:
        # Create company
        company = Company()
        company.cik = cik

        try:
            company.save()
        except django.db.utils.IntegrityError:
            return create_filing_error(row, filing_path)

        # Create company info record
        company_info = CompanyInfo()
        company_info.company = company
        company_info.name = company_name
        company_info.sic = None
        company_info.state_incorporation = None
        company_info.state_location = None
        company_info.date = date_filed
        company_info.save()

    # Finally update company and save
    filing.company = company
    filing.save()
    return True


@shared_task
def process_filing_index(file_path: str, filing_index_buffer: Union[str, bytes] = None,
                         form_type_list: Iterable[str] = None, store_raw: bool = False, store_text: bool = False, use_local: bool = False):
    """
    Process a filing index from an S3 path or buffer.
    :param file_path: S3 or local path to process; if filing_index_buffer is none, retrieved from here
    :param filing_index_buffer: buffer; if not present, s3_path must be set
    :param form_type_list: optional list of form type to process
    :param store_raw:
    :param store_text:
    :return:
    """
    # Log entry
    logger.info("Processing filing index {0}...".format(file_path))

    # Create S3 client
    configured_client = os.environ["CLIENT_TYPE"]

    if configured_client is None or configured_client == "S3":
        client = S3Client()
    else:
        client = LocalClient()

    # Retrieve buffer if not passed
    if filing_index_buffer is None:
        logger.info("Retrieving filing index buffer for: {}...".format(file_path))
        filing_index_buffer = client.get_buffer(file_path)

    # Write to disk to handle headaches
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(filing_index_buffer)
    temp_file.close()

    # Get main filing data structure
    filing_index_data = openedgar.parsers.edgar.parse_index_file(temp_file.name)
    logger.info("Parsed {0} records from index".format(filing_index_data.shape[0]))



    # Iterate through rows
    bad_record_count = 0
    for _, row in filing_index_data.iterrows():
        # Check for form type whitelist
        if form_type_list is not None:
            if row["Form Type"] not in form_type_list:
                logger.info("Skipping filing {0} with form type {1}...".format(row["File Name"], row["Form Type"]))
                continue

        # Cleanup path
        if row["File Name"].lower().startswith("data/"):
            filing_path = "edgar/{0}".format(row["File Name"])
        elif row["File Name"].lower().startswith("edgar/"):
            filing_path = row["File Name"]

        # Check if filing record exists
        try:
            filing = Filing.objects.get(s3_path=filing_path)
            logger.info("Filing record already exists: {0}".format(filing))
        except Filing.MultipleObjectsReturned as e:
            # Create new filing record
            logger.error("Multiple Filing records found for s3_path={0}, skipping...".format(filing_path))
            logger.info("Raw exception: {0}".format(e))
            continue
        except Filing.DoesNotExist as f:
            # Create new filing record
            logger.info("No Filing record found for {0}, creating...".format(filing_path))
            logger.info("Raw exception: {0}".format(f))

            # Check if exists; download and upload to S3 if missing
            if not openedgar.clients.s3.path_exists(filing_path, client=client):
                # Download
                try:
                    filing_buffer, _ = openedgar.clients.edgar.get_buffer("/Archives/{0}".format(filing_path))
                except RuntimeError as g:
                    logger.error("Unable to access resource {0} from EDGAR: {1}".format(filing_path, g))
                    bad_record_count += 1
                    create_filing_error(row, filing_path)
                    continue

                # Upload
                openedgar.clients.s3.put_buffer(filing_path, filing_buffer, client=client)

                logger.info("Downloaded from EDGAR and uploaded to S3...")
            else:
                # Download
                logger.info("File already stored on S3, retrieving and processing...")
                filing_buffer = openedgar.clients.s3.get_buffer(filing_path, client=client)

            # Parse
            filing_result = process_filing(filing_path, filing_buffer, store_raw=store_raw, store_text=store_text)
            if filing_result is None:
                logger.error("Unable to process filing.")
                bad_record_count += 1
                create_filing_error(row, filing_path)

    # Create a filing index record
    edgar_url = "/Archives/{0}".format(file_path).replace("//", "/")
    try:
        filing_index = FilingIndex.objects.get(edgar_url=edgar_url)
        filing_index.total_record_count = filing_index_data.shape[0]
        filing_index.bad_record_count = bad_record_count
        filing_index.is_processed = True
        filing_index.is_error = False
        filing_index.save()
        logger.info("Updated existing filing index record.")
    except FilingIndex.DoesNotExist:
        filing_index = FilingIndex()
        filing_index.edgar_url = edgar_url
        filing_index.date_published = None
        filing_index.date_downloaded = datetime.date.today()
        filing_index.total_record_count = filing_index_data.shape[0]
        filing_index.bad_record_count = bad_record_count
        filing_index.is_processed = True
        filing_index.is_error = False
        filing_index.save()
        logger.info("Created new filing index record.")

    # Delete file if we make it this far
    os.remove(temp_file.name)


@shared_task
def process_filing(s3_path: str, filing_buffer: Union[str, bytes] = None, store_raw: bool = False,
                   store_text: bool = False):
    """
    Process a filing from an S3 path or filing buffer.
    :param s3_path: S3 path to process; if filing_buffer is none, retrieved from here
    :param filing_buffer: buffer; if not present, s3_path must be set
    :param store_raw:
    :param store_text:
    :return:
    """
    # Log entry
    logger.info("Processing filing {0}...".format(s3_path))

    # Check for existing record first
    try:
        filing = Filing.objects.get(s3_path=s3_path)
        if filing is not None:
            logger.error("Filing {0} has already been created in record {1}".format(s3_path, filing))
            return None
    except Filing.DoesNotExist:
        logger.info("No existing record found.")
    except Filing.MultipleObjectsReturned:
        logger.error("Multiple existing record found.")
        return None

    # Get buffer
    if filing_buffer is None:
        logger.info("Retrieving filing buffer from S3...")
        filing_buffer = openedgar.clients.s3.get_buffer(s3_path)

    # Get main filing data structure
    filing_data = openedgar.parsers.edgar.parse_filing(filing_buffer, extract=store_text)
    if filing_data["cik"] is None:
        logger.error("Unable to parse CIK from filing {0}; assuming broken and halting...".format(s3_path))
        return None

    try:
        # Get company
        company = Company.objects.get(cik=filing_data["cik"])
        logger.info("Found existing company record.")

        # Check if record exists for date
        try:
            _ = CompanyInfo.objects.get(company=company, date=filing_data["date_filed"])

            logger.info("Found existing company info record.")
        except CompanyInfo.DoesNotExist:
            # Create company info record
            company_info = CompanyInfo()
            company_info.company = company
            company_info.name = filing_data["company_name"]
            company_info.sic = filing_data["sic"]
            company_info.state_incorporation = filing_data["state_incorporation"]
            company_info.state_location = filing_data["state_location"]
            company_info.date = filing_data["date_filed"].date() if isinstance(filing_data["date_filed"],
                                                                               datetime.datetime) else \
                filing_data["date_filed"]
            company_info.save()

            logger.info("Created new company info record.")

    except Company.DoesNotExist:
        # Create company
        company = Company()
        company.cik = filing_data["cik"]

        try:
            # Catch race with another task/thread
            company.save()

            try:
                _ = CompanyInfo.objects.get(company=company, date=filing_data["date_filed"])
            except CompanyInfo.DoesNotExist:
                # Create company info record
                company_info = CompanyInfo()
                company_info.company = company
                company_info.name = filing_data["company_name"]
                company_info.sic = filing_data["sic"]
                company_info.state_incorporation = filing_data["state_incorporation"]
                company_info.state_location = filing_data["state_location"]
                company_info.date = filing_data["date_filed"]
                company_info.save()
        except django.db.utils.IntegrityError:
            company = Company.objects.get(cik=filing_data["cik"])

        logger.info("Created company and company info records.")

    # Now create the filing record
    try:
        filing = Filing()
        filing.form_type = filing_data["form_type"]
        filing.accession_number = filing_data["accession_number"]
        filing.date_filed = filing_data["date_filed"]
        filing.document_count = filing_data["document_count"]
        filing.company = company
        filing.sha1 = hashlib.sha1(filing_buffer).hexdigest()
        filing.s3_path = s3_path
        filing.is_processed = False
        filing.is_error = True
        filing.save()
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Unable to create filing record: {0}".format(e))
        return None

    # Create filing document records
    try:
        create_filing_documents(filing_data["documents"], filing, store_raw=store_raw, store_text=store_text)
        filing.is_processed = True
        filing.is_error = False
        filing.save()
        return filing
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Unable to create filing documents for {0}: {1}".format(filing, e))
        return None


@shared_task
def extract_filing(s3_path: str, filing_buffer: Union[str, bytes] = None):
    """
    Extract the contents of a filing from an S3 path or filing buffer.
    :param s3_path: S3 path to process; if filing_buffer is none, retrieved from here
    :param filing_buffer: buffer; if not present, s3_path must be set
    :return:
    """
    # Get buffer
    if filing_buffer is None:
        logger.info("Retrieving filing buffer from S3...")
        filing_buffer = openedgar.clients.s3.get_buffer(s3_path)

    # Get main filing data structure
    _ = openedgar.parsers.edgar.parse_filing(filing_buffer)


@shared_task
def search_filing_document_sha1(sha1: str, term_list: Iterable[str], search_query_id: int, document_id: int,
                                case_sensitive: bool = False,
                                token_search: bool = False, stem_search: bool = False):
    """
    Search a filing document by sha1 hash.
    :param stem_search:
    :param token_search:
    :param sha1: sha1 hash of document to search
    :param term_list: list of terms
    :param search_query_id:
    :param document_id:
    :param case_sensitive:
    :return:
    """
    # Get buffer
    logger.info("Retrieving buffer from S3...")
    text_s3_path = pathlib.Path(S3_DOCUMENT_PATH, "text", sha1).as_posix()
    document_buffer = openedgar.clients.s3.get_buffer(text_s3_path).decode("utf-8")

    # Check if case
    if not case_sensitive:
        document_buffer = document_buffer.lower()

    # TODO: Refactor search types
    # TODO: Cleanup flow for reduced recalc
    # TODO: Don't search same SHA1 repeatedly, but need to coordinate with calling process

    # Get contents
    if not token_search and not stem_search:
        document_contents = document_buffer
    elif token_search:
        document_contents = lexnlp.nlp.en.tokens.get_token_list(document_buffer)
    elif stem_search:
        document_contents = lexnlp.nlp.en.tokens.get_stem_list(document_buffer)

    # For term in term list
    counts = {}
    for term in term_list:
        # term_tokens = lexnlp.nlp.en.tokens.get_token_list(term)

        if stem_search:
            term = lexnlp.nlp.en.tokens.DEFAULT_STEMMER.stem(term)

        if case_sensitive:
            counts[term] = document_contents.count(term)
        else:
            counts[term] = document_contents.count(term.lower())

    search_query = None
    results = []
    for term in counts:
        if counts[term] > 0:
            # Get search query if empty
            if search_query is None:
                search_query = SearchQuery.objects.get(id=search_query_id)

            # Get term
            search_term = SearchQueryTerm.objects.get(search_query_id=search_query_id, term=term)

            # Create result
            result = SearchQueryResult()
            result.search_query = search_query
            result.filing_document_id = document_id
            result.term = search_term
            result.count = counts[term]
            results.append(result)

    # Create if any
    if len(results) > 0:
        SearchQueryResult.objects.bulk_create(results)
    logger.info("Found {0} search terms in document sha1={1}".format(len(results), sha1))
    return True


@shared_task
def extract_filing_document_data_sha1(sha1: str):
    """
    Extract structured data from a filing document by sha1 hash, e.g.,
    dates, money, noun phrases.
    :param sha1:
    :param document_id:
    :return:
    """
    # Get buffer
    logger.info("Retrieving buffer from S3...")
    text_s3_path = pathlib.Path(S3_DOCUMENT_PATH, "text", sha1).as_posix()
    document_buffer = openedgar.clients.s3.get_buffer(text_s3_path).decode("utf-8")

    # TODO: Build your own database here.
    _ = len(document_buffer)
