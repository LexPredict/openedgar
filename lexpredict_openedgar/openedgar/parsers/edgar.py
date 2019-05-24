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
import binascii
import gzip
import hashlib
import io
import logging
import mimetypes
import re
import os
import zlib
from typing import Union

# Packages
import dateutil.parser
import pandas
import tika.parser

# Project imports
from config.settings.base import TIKA_ENDPOINT

# Setup logger
logger = logging.getLogger(__name__)


def uudecode(buffer: Union[bytes, str]):
    """
    uudecode an input buffer; based on python library uu but with support for byte stream
    :param buffer:
    :return:
    """
    # Create in_file from buffer
    in_file = io.BytesIO(buffer)
    out_file = io.BytesIO()

    while True:
        hdr = in_file.readline()
        if not hdr.startswith(b'begin'):
            continue
        hdrfields = hdr.split(b' ', 2)
        if len(hdrfields) == 3 and hdrfields[0] == b'begin':
            try:
                int(hdrfields[1], 8)
                break
            except ValueError:
                pass

    s = in_file.readline()
    while s and s.strip(b' \t\r\n\f') != b'end':
        try:
            data = binascii.a2b_uu(s)
        except binascii.Error as _:
            # Workaround for broken uuencoders by /Fredrik Lundh
            nbytes = (((s[0] - 32) & 63) * 4 + 5) // 3
            data = binascii.a2b_uu(s[:nbytes])
        out_file.write(data)
        s = in_file.readline()

    return out_file.getvalue()


def extract_text(buffer: Union[bytes, str]):
    """
    Extract text from a document using tika.
    :param buffer: buffer to send to tika
    :return:
    """
    # Extract HTML using Tika
    tika_results = tika.parser.from_buffer(buffer, TIKA_ENDPOINT)

    if "content" in tika_results:
        return tika_results["content"]

    return ""


def parse_index_file(file_name: str, double_gz: bool = False):
    """
    Parse an index file.
    :param file_name:
    :param double_gz:
    :return:
    """
    # Log entrance
    if not os.path.exists(file_name):
        if os.path.exists(file_name + ".gz"):
            file_name += ".gz"
        else:
            logger.error("File {0} does not exist on filesystem.".format(file_name))
            return pandas.DataFrame()

    logger.info("Parsing index file: {0}".format(file_name))

    # Read index
    try:
        with gzip.open(file_name, "rb") as index_file:
            index_buffer = index_file.read()
    except IOError as e:
        # Read as plain binary
        with open(file_name, "rb") as index_file:
            index_buffer = index_file.read()

        # Check for alternative header
        if index_buffer[0] == '\x78' and (ord(index_buffer[1]) + 0x7800) % 31 == 0:
            index_buffer = zlib.decompress(index_buffer).decode("utf-8")
            logger.info("gz with valid header: decompressing {0} to {1} bytes.".format(file_name,
                                                                                       len(index_buffer)))
        else:
            logger.info("IOError parsing {0}: {1}".format(file_name, e))

        # Check for double-gz
        if double_gz:
            index_buffer = os.popen("gunzip -c {0} | gunzip -c".format(file_name)).read() \
                .decode("utf-8", "ignore").decode("utf-8", "ignore")
            logger.warning("Double-decompressing buffer for {0}".format(file_name))

    # Re-code to UTF-8
    try:
        index_buffer = index_buffer.decode("utf-8")
    except UnicodeDecodeError as _:
        # Check for double-compression
        try:
            index_buffer = gzip.GzipFile(fileobj=io.BytesIO(index_buffer)).read().encode("utf-8").decode("utf-8")
        except UnicodeDecodeError as _:
            try:
                index_buffer = os.popen("gunzip -c {0} | gunzip -c".format(file_name)).read() \
                    .decode("utf-8", "ignore").decode("utf-8", "ignore")
                logger.warning("Double-decompressing buffer for {0}".format(file_name))
            except UnicodeDecodeError as g:
                logger.error("Error decoding {0}: {1}".format(file_name, g))
                logger.error("First 10 bytes: {0}".format(index_buffer[0:10]))
                return pandas.DataFrame()
            except OSError as h:
                logger.error("Error decoding {0}: {1}".format(file_name, h))
                logger.error("First 10 bytes: {0}".format(index_buffer[0:10]))
                return pandas.DataFrame()
        except OSError as h:
            logger.error("Error decoding {0}: {1}".format(file_name, h))
            logger.error("First 10 bytes: {0}".format(index_buffer[0:10]))
            return pandas.DataFrame()

    # Get header line and data line starts
    header_line_pos = index_buffer.find("\nForm Type") + 1
    separator_line_pos = index_buffer.find("-", header_line_pos + 1)
    data_line_pos = index_buffer.find("\n", separator_line_pos + 1)

    # Build buffer and parse as fixed-width file
    data_buffer = io.StringIO(index_buffer[header_line_pos:separator_line_pos].replace("\n", "\t")
                              + index_buffer[data_line_pos:])
    data_table = pandas.read_fwf(data_buffer,
                                 colspecs="infer",
                                 encoding="utf-8")

    # Deal with broken field names
    if "Form" in data_table.columns and "Form Type" not in data_table.columns:
        logger.warning("Index file has abnormal columns: {0}".format(file_name))
        data_table["Form Type"] = data_table["Form"]
        del data_table["Form"]

    # Remove unknown field names
    good_columns = ["CIK", "Company Name", "Date Filed", "File Name", "Form Type"]
    try:
        data_table = data_table.loc[:, good_columns]
    except KeyError:
        logger.error("Unable to identify proper columns in {0}".format(file_name))
        logger.error("Columns found: {0}".format(data_table.columns))

    # Log exit
    logger.info("Completed parsing index file: {0}".format(file_name))
    logger.info("Index data shape: {0}".format(data_table.shape))

    # Return
    return data_table


def extract_filing_header_field(buffer: Union[bytes, str], field: str):
    """
    Extract a given field from an SEC-HEADER buffer.
    :param buffer: SEC-HEADER buffer
    :param field: field to extract
    :return:
    """
    # Get name
    field_string = "{0}:".format(field)
    if field_string not in buffer:
        return None

    p0 = buffer.find(field_string) + len(field_string)
    p1 = buffer.find("\n", p0)
    return buffer[p0:p1].strip()


def decode_filing(to_decode: Union[bytes, str]) -> Union[str, None]:
    buffer = to_decode
    if isinstance(buffer, bytes):
        try:
            # Start with UTF-8
            buffer = str(buffer.decode("utf-8"))
        except UnicodeDecodeError as _:
            try:
                # Fallback to ISO 8859-1
                logger.warning("Falling back to ISO 8859-1 after failing to decode with UTF-8...")
                buffer = str(buffer.decode("iso-8859-1"))
            except UnicodeDecodeError as _:
                try:
                    # Fallback to ISO 8859-15
                    logger.warning("Falling back to ISO 8859-15 after failing to decode with UTF-8...")
                    buffer = str(buffer.decode("iso-8859-5"))
                except UnicodeDecodeError as _:
                    # Give up if we can't
                    logger.error("Unable to decode with either UTF-8 or ISO 8859-1; giving up...")
                    return None
    return buffer


def parse_filing(buffer: Union[bytes, str], extract: bool = False):
    """
    Parse a filing file by returning each document within
    :param buffer:
    :param extract: whether to extract raw text
    :return:
    """
    # Start and end tags
    start_tag = "<DOCUMENT>"
    end_tag = "</DOCUMENT>"
    filing_data = {"documents": [],
                   "accession_number": None,
                   "form_type": None,
                   "document_count": None,
                   "reporting_period": None,
                   "date_filed": None,
                   "company_name": None,
                   "cik": None,
                   "sic": None,
                   "irs_number": None,
                   "state_incorporation": None,
                   "state_location": None}

    # Typing
    if isinstance(buffer, bytes):
        buffer = decode_filing(buffer)
    if buffer is None:
        return filing_data

    # Check for SEC-HEADER block
    if "<SEC-HEADER>" in buffer or "<IMS-HEADER>" in buffer:
        # Get header subset
        if "<SEC-HEADER>" in buffer:
            header_p0 = buffer.find("<SEC-HEADER>")
            header_p1 = buffer.find("</SEC-HEADER>")
        elif "<IMS-HEADER>" in buffer:
            header_p0 = buffer.find("<IMS-HEADER>")
            header_p1 = buffer.find("</IMS-HEADER>")
        else:
            header_p0 = -1
            header_p1 = -1

        if header_p0 == -1 or header_p1 == -1:
            logger.error("Invalid HEADER block found in document")
        else:
            # Parse valid header
            header = buffer[header_p0 + len("<SEC-HEADER>"):header_p1]

            # Get name
            filing_data["accession_number"] = extract_filing_header_field(header, "ACCESSION NUMBER")
            filing_data["form_type"] = extract_filing_header_field(header, "CONFORMED SUBMISSION TYPE")

            try:
                document_count_value = extract_filing_header_field(header, "PUBLIC DOCUMENT COUNT")
                filing_data["document_count"] = int(document_count_value)
            except ValueError as _:
                logger.warning("Unable to set document_count")
                filing_data["document_count"] = None

            try:
                reporting_period_value = extract_filing_header_field(header, "CONFORMED PERIOD OF REPORT")
                filing_data["reporting_period"] = dateutil.parser.parse(
                    reporting_period_value).date() if reporting_period_value is not None else None
            except ValueError as _:
                logger.warning("Unable to set reporting_period")
                filing_data["reporting_period"] = None

            try:
                date_filed_value = extract_filing_header_field(header, "FILED AS OF DATE")
                filing_data["date_filed"] = dateutil.parser.parse(
                    date_filed_value).date() if date_filed_value is not None else None
            except ValueError as _:
                logger.warning("Unable to set date_filed")
                filing_data["date_filed"] = None

            filing_data["company_name"] = extract_filing_header_field(header, "COMPANY CONFORMED NAME")
            filing_data["cik"] = extract_filing_header_field(header, "CENTRAL INDEX KEY")
            filing_data["sic"] = extract_filing_header_field(header, "STANDARD INDUSTRIAL CLASSIFICATION")
            filing_data["irs_number"] = extract_filing_header_field(header, "IRS NUMBER")
            filing_data["state_incorporation"] = extract_filing_header_field(header, "STATE OF INCORPORATION")
            filing_data["state_location"] = extract_filing_header_field(header, "STATE")

    # Parse and yield by doc
    p0 = buffer.find(start_tag)
    while p0 != -1:
        p1 = buffer.find(end_tag, p0)

        # Parse document
        document_buffer = buffer[p0:(p1 + len(end_tag))]
        document_data = parse_filing_document(document_buffer, extract=extract)
        document_data["start_pos"] = p0
        document_data["end_pos"] = (p1 + len(end_tag))
        filing_data["documents"].append(document_data)
        p0 = buffer.find(start_tag, p1)

    return filing_data


def parse_filing_document(document_buffer: Union[bytes, str], extract: bool = False):
    """
    Parse a document buffer into metadata and contents.
    :param document_buffer: raw document buffer
    :param extract: whether to pass to Tika for text extraction
    :return:
    """
    # Parse segment
    doc_type = re.findall("<TYPE>(.+)", document_buffer)
    doc_sequence = re.findall("<SEQUENCE>(.+)", document_buffer)
    doc_file_name = re.findall("<FILENAME>(.+)", document_buffer)
    doc_description = re.findall("<DESCRIPTION>(.+)", document_buffer)

    # Start and end tags
    content_p0 = document_buffer.rfind("</", 0, document_buffer.rfind("</"))
    content_p1 = document_buffer.find(">", content_p0)
    doc_tag_type = document_buffer[content_p0 + len("</"):content_p1]
    content_start_tag = "<{0}>".format(doc_tag_type)
    content_end_tag = "</{0}>".format(doc_tag_type)

    doc_content_p0 = document_buffer.find(content_start_tag) + len(content_start_tag)
    doc_content_p1 = document_buffer.find(content_end_tag)
    doc_content = document_buffer[doc_content_p0:doc_content_p1]

    # Check content types
    is_uuencoded = False
    doc_text_head = doc_content[0:100]
    doc_text_head_upper = doc_text_head.upper()

    if "<PDF>" in doc_text_head_upper:
        is_uuencoded = True
        content_type = "application/pdf"
    elif "<HTML" in doc_text_head_upper:
        content_type = "text/html"
    elif "<XML" in doc_text_head_upper:
        content_type = "application/xml"
    elif "<?XML" in doc_text_head_upper:
        content_type = "application/xml"
    elif doc_text_head.startswith("\nbegin "):
        is_uuencoded = True
        if len(doc_file_name) > 0:
            content_type = mimetypes.guess_type(os.path.basename(doc_file_name[0]))
            if content_type is None:
                content_type = "application/octet-stream"
            else:
                content_type = content_type[0]
        else:
            content_type = "application/octet-stream"
    else:
        content_type = "text/plain"

    # uudecode if required and calculate hash for sharding/dedupe
    doc_content = doc_content.encode("utf-8")
    if is_uuencoded:
        doc_content = uudecode(doc_content)
    doc_sha1 = hashlib.sha1(doc_content).hexdigest()

    # extract text from tika if requested
    if extract:
        doc_content_text = extract_text(doc_content)
    else:
        doc_content_text = None

    return {"type": doc_type[0] if len(doc_type) > 0 else None,
            "sequence": doc_sequence[0] if len(doc_sequence) > 0 else None,
            "file_name": doc_file_name[0] if len(doc_file_name) > 0 else None,
            "description": doc_description[0] if len(doc_description) > 0 else None,
            "content_type": content_type,
            "sha1": doc_sha1,
            "content": doc_content,
            "content_text": doc_content_text}
