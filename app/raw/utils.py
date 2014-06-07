"""
Some utilities for working with spiders
"""
from scrapy.crawler import Crawler
from scrapy.utils.project import get_project_settings
import magic
import subprocess


HTML = 1
DOC = 2
DOCX = 3
PDF = 4


def list_spiders():
    settings = get_project_settings()
    crawler = Crawler(settings)
    return crawler.spiders.list()


def check_file_type(filepath, as_string=False):
    filetype = magic.from_file(filepath)
    if not filetype:
        # Filetype Could Not Be Determined
        return None
    elif filetype == 'empty':
        # Filetype Could Not Be Determined (file looks empty)
        return None
    elif filetype == 'very short file (no magic)':
        # Filetype Could Not Be Determined (very short file)
        return None
    elif "Microsoft Office Word" in filetype:
        return DOC if not as_string else 'DOC'
    elif filetype[0:4] == 'HTML':
        return HTML if not as_string else 'HTML'
    elif filetype == 'Microsoft Word 2007+':
        return DOCX if not as_string else 'DOCX'
    elif 'PDF' in filetype:
        return PDF if not as_string else 'PDF'
    else:
        # some other filetype that we don't account for
        return None


def doc_to_xml(filepath):
    """
    Converts a doc file into an in-memory xml (docbook schema) string

    :param filepath: full filepath to the file to convert
    :return: unicode string
    """
    cmd = ['antiword', '-x', 'db', filepath]
    return subprocess.check_output(cmd).decode('utf-8')