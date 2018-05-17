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

import tempfile
from nose.tools import assert_equal

import openedgar.clients.edgar
import openedgar.parsers.edgar


def test_filing_parser():
    """
    Test parsing filing into segments.
    :return:
    """
    uri = "/Archives/edgar/data/1297937/000107878205000139/0001078782-05-000139.txt"
    buffer, _ = openedgar.clients.edgar.get_buffer(uri)

    # parser buffer
    segment_count = 0
    expected_segment_count = 10
    last_sequence = None
    expected_last_sequence = "EX-99"

    filing_data = openedgar.parsers.edgar.parse_filing(buffer)

    for document in filing_data["documents"]:
        last_sequence = document["type"]
        segment_count += 1

    assert_equal(segment_count, expected_segment_count)
    assert_equal(last_sequence, expected_last_sequence)


def test_filing_parser_header():
    """
    Test parsing filing into segments.
    :return:
    """
    uri = "/Archives/edgar/data/1599891/0001193125-18-000566.txt"
    buffer, _ = openedgar.clients.edgar.get_buffer(uri)

    # parser buffer
    expected_name = "Sunshine Bancorp, Inc."
    expected_state_inc = "MD"
    expected_sic = "SAVINGS INSTITUTION, FEDERALLY CHARTERED [6035]"

    filing_data = openedgar.parsers.edgar.parse_filing(buffer)
    assert_equal(filing_data["company_name"], expected_name)
    assert_equal(filing_data["sic"], expected_sic)
    assert_equal(filing_data["state_incorporation"], expected_state_inc)


def test_filing_parser_header_old():
    """
    Test parsing filing into segments.
    :return:
    """
    uri = "/Archives/edgar/data/7323/0000007323-94-000018.txt"
    buffer, _ = openedgar.clients.edgar.get_buffer(uri)

    # parser buffer
    expected_name = "ARKANSAS POWER & LIGHT CO"
    expected_state_inc = "AR"
    expected_sic = "4911"
    expected_content_type = "text/plain"

    filing_data = openedgar.parsers.edgar.parse_filing(buffer)
    assert_equal(filing_data["documents"][0]["content_type"], expected_content_type)
    assert_equal(filing_data["company_name"], expected_name)
    assert_equal(filing_data["sic"], expected_sic)
    assert_equal(filing_data["state_incorporation"], expected_state_inc)


def test_filing_parser_pdf():
    """
    Test parsing filing into segments with a PDF section.
    :return:
    """
    uri = "/Archives/edgar/data/721994/0000721994-18-000014.txt"
    buffer, _ = openedgar.clients.edgar.get_buffer(uri)

    # parser buffer
    segment_count = 0
    expected_segment_count = 142
    last_sequence = None
    expected_last_sequence = "ZIP"

    filing_data = openedgar.parsers.edgar.parse_filing(buffer)

    for document in filing_data["documents"]:
        if document["file_name"].lower().endswith("pdf"):
            assert_equal(document["content_type"], "application/pdf")

        last_sequence = document["type"]
        segment_count += 1

    assert_equal(segment_count, expected_segment_count)
    assert_equal(last_sequence, expected_last_sequence)


def test_index_parser():
    """
    Test parsing form index.
    :return:
    """
    # download index
    uri = "/Archives/edgar/daily-index/1994/QTR3/form.093094.idx"
    buffer, _ = openedgar.clients.edgar.get_buffer(uri)

    # save to temp file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file_name = temp_file.name
        temp_file.write(buffer)

    # parser buffer
    index_data = openedgar.parsers.edgar.parse_index_file(temp_file_name)
    result = index_data.shape[0]
    expected = 226
    assert_equal(result, expected)
