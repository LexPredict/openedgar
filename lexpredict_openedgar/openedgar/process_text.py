from typing import Union

from bs4 import BeautifulSoup
import re


def html_to_text(html_doc: str) -> str:
    """
    Convert html/xml to the pure text
    :param html_doc: the document to convert
    :return:
    """
    soup = BeautifulSoup(html_doc, 'html.parser')
    if soup.find('xbrl'):
        return xbr(soup)
    else:
        return not_xbrl(soup)


def not_xbrl(soup: BeautifulSoup) -> str:
    """
    Handle format not in XBLR
    :param soup:
    :return:
    """
    doc = ''
    for string in soup.strings:
        string = string.strip()
        if len(string) > 0:
            doc += string + '\n'
    return doc


def xbr(soup: BeautifulSoup) -> str:
    """
    Handle XBLR format for extracting all the text fields
    :param soup:
    :return:
    """
    doc = ""
    for tag in soup.find_all(re.compile("[T,t]ext|[D,d]escription")):
        if tag.string is not None:
            inner_soup = BeautifulSoup(tag.string, 'html.parser')
            string = ""
            for string_inner in inner_soup.strings:
                if string_inner is not None:
                    string = string + " " + string_inner
            doc += string + '\n'
    return doc
