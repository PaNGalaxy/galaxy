"""
Utility functions used systemwide.

"""

import binascii
import codecs
import collections
import errno
import importlib
import itertools
import json
import os
import random
import re
import shlex
import shutil
import smtplib
import stat
import string
import sys
import tempfile
import textwrap
import threading
import time
import typing
import unicodedata
import xml.dom.minidom
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from hashlib import md5
from os.path import relpath
from pathlib import Path
from typing import (
    Any,
    Optional,
    overload,
)
from urllib.parse import (
    urlencode,
    urlparse,
    urlsplit,
    urlunsplit,
)

import requests
from boltons.iterutils import (
    default_enter,
    remap,
)
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing_extensions import Literal

try:
    import grp
except ImportError:
    # For Pulsar on Windows (which does not use the function that uses grp)
    grp = None  # type: ignore[assignment]
LXML_AVAILABLE = True
try:
    from lxml import etree
    from lxml.etree import _Element as Element
except ImportError:
    LXML_AVAILABLE = False
    import xml.etree.ElementTree as etree  # type: ignore[assignment,no-redef]
    from xml.etree.ElementTree import Element  # noqa: F401  # type: ignore[assignment,no-redef]

try:
    import docutils.core as docutils_core
    import docutils.writers.html4css1 as docutils_html4css1
except ImportError:
    docutils_core = None  # type: ignore[assignment]
    docutils_html4css1 = None  # type: ignore[assignment]

from .custom_logging import get_logger
from .inflection import Inflector
from .path import (  # noqa: F401
    safe_contains,
    safe_makedirs,
    safe_relpath,
)

try:
    shlex_join = shlex.join  # type: ignore[attr-defined]
except AttributeError:
    # Python < 3.8
    def shlex_join(split_command):
        return " ".join(map(shlex.quote, split_command))


inflector = Inflector()

log = get_logger(__name__)
_lock = threading.RLock()

namedtuple = collections.namedtuple

CHUNK_SIZE = 65536  # 64k

DATABASE_MAX_STRING_SIZE = 32768
DATABASE_MAX_STRING_SIZE_PRETTY = "32K"

DEFAULT_SOCKET_TIMEOUT = 600

gzip_magic = b"\x1f\x8b"
bz2_magic = b"BZh"
DEFAULT_ENCODING = os.environ.get("GALAXY_DEFAULT_ENCODING", "utf-8")
NULL_CHAR = b"\x00"
BINARY_CHARS = [NULL_CHAR]
FILENAME_VALID_CHARS = ".,^_-()[]0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

RW_R__R__ = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
RWXR_XR_X = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
RWXRWXRWX = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO

XML = etree.XML

defaultdict = collections.defaultdict


def str_removeprefix(s: str, prefix: str):
    """
    str.removeprefix() equivalent for Python < 3.9
    """
    if sys.version_info >= (3, 9):
        return s.removeprefix(prefix)
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


def remove_protocol_from_url(url):
    """Supplied URL may be null, if not ensure http:// or https://
    etc... is stripped off.
    """
    if url is None:
        return url

    # We have a URL
    if url.find("://") > 0:
        new_url = url.split("://")[1]
    else:
        new_url = url
    return new_url.rstrip("/")


def is_binary(value):
    """
    File is binary if it contains a null-byte by default (e.g. behavior of grep, etc.).
    This may fail for utf-16 files, but so would ASCII encoding.
    >>> is_binary( string.printable )
    False
    >>> is_binary( b'\\xce\\x94' )
    False
    >>> is_binary( b'\\x00' )
    True
    """
    value = smart_str(value)
    for binary_char in BINARY_CHARS:
        if binary_char in value:
            return True
    return False


def is_uuid(value):
    """
    This method returns True if value is a UUID, otherwise False.
    >>> is_uuid( "123e4567-e89b-12d3-a456-426655440000" )
    True
    >>> is_uuid( "0x3242340298902834" )
    False
    """
    uuid_re = re.compile("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    if re.match(uuid_re, str(value)):
        return True
    else:
        return False


def directory_hash_id(id):
    """

    >>> directory_hash_id( 100 )
    ['000']
    >>> directory_hash_id( "90000" )
    ['090']
    >>> directory_hash_id("777777777")
    ['000', '777', '777']
    >>> directory_hash_id("135ee48a-4f51-470c-ae2f-ce8bd78799e6")
    ['1', '3', '5']
    """
    s = str(id)
    len_s = len(s)
    # Shortcut -- ids 0-999 go under ../000/
    if len_s < 4:
        return ["000"]
    if not is_uuid(s):
        # Pad with zeros until a multiple of three
        padded = ((3 - len_s % 3) * "0") + s
        # Drop the last three digits -- 1000 files per directory
        padded = padded[:-3]
        # Break into chunks of three
        return [padded[i * 3 : (i + 1) * 3] for i in range(len(padded) // 3)]
    else:
        # assume it is a UUID
        return list(iter(s[0:3]))


def get_charset_from_http_headers(headers, default=None):
    rval = headers.get("content-type", None)
    if rval and "charset=" in rval:
        rval = rval.split("charset=")[-1].split(";")[0].strip()
        if rval:
            return rval
    return default


def synchronized(func):
    """This wrapper will serialize access to 'func' to a single thread. Use it as a decorator."""

    def caller(*params, **kparams):
        _lock.acquire(True)  # Wait
        try:
            return func(*params, **kparams)
        finally:
            _lock.release()

    return caller


def iter_start_of_line(fh, chunk_size=None):
    """Iterate over fh and call readline(chunk_size)."""
    while True:
        data = fh.readline(chunk_size)
        if not data:
            break
        if not data.endswith("\n"):
            # Discard the rest of the line
            fh.readline()
        yield data


def file_reader(fp, chunk_size=CHUNK_SIZE):
    """This generator yields the open file object in chunks (default 64k)."""
    while True:
        data = fp.read(chunk_size)
        if not data:
            break
        yield data


def chunk_iterable(it: typing.Iterable, size: int = 1000):
    """
    Break an iterable into chunks of ``size`` elements.

    >>> list(chunk_iterable([1, 2, 3, 4, 5, 6, 7], 3))
    [(1, 2, 3), (4, 5, 6), (7,)]
    """
    it = iter(it)
    while True:
        p = tuple(itertools.islice(it, size))
        if not p:
            break
        yield p


def unique_id(KEY_SIZE=128):
    """
    Generates an unique id

    >>> ids = [ unique_id() for i in range(1000) ]
    >>> len(set(ids))
    1000
    """
    random_bits = str(random.getrandbits(KEY_SIZE)).encode("UTF-8")
    return md5(random_bits).hexdigest()


def parse_xml(fname: typing.Union[str, Path], strip_whitespace=True, remove_comments=True):
    """Returns a parsed xml tree"""
    parser = None
    if remove_comments and LXML_AVAILABLE:
        # If using stdlib etree comments are always removed,
        # but lxml doesn't do this by default
        parser = etree.XMLParser(remove_comments=remove_comments)
    try:
        tree = etree.parse(str(fname), parser=parser)
        root = tree.getroot()
        if strip_whitespace:
            for elem in root.iter("*"):
                if elem.text is not None:
                    elem.text = elem.text.strip()
                if elem.tail is not None:
                    elem.tail = elem.tail.strip()
    except OSError as e:
        if e.errno is None and not os.path.exists(fname):
            # lxml doesn't set errno
            e.errno = errno.ENOENT
        raise
    except etree.ParseError:
        log.exception("Error parsing file %s", fname)
        raise
    return tree


def parse_xml_string(xml_string, strip_whitespace=True):
    try:
        tree = etree.fromstring(xml_string)
    except ValueError as e:
        if "strings with encoding declaration are not supported" in unicodify(e):
            tree = etree.fromstring(xml_string.encode("utf-8"))
        else:
            raise e
    if strip_whitespace:
        for elem in tree.iter("*"):
            if elem.text is not None:
                elem.text = elem.text.strip()
            if elem.tail is not None:
                elem.tail = elem.tail.strip()
    return tree


def parse_xml_string_to_etree(xml_string, strip_whitespace=True):
    return etree.ElementTree(parse_xml_string(xml_string=xml_string, strip_whitespace=strip_whitespace))


def xml_to_string(elem, pretty=False):
    """
    Returns a string from an xml tree.
    """
    try:
        if elem is not None:
            xml_str = etree.tostring(elem, encoding="unicode")
        else:
            xml_str = ""
    except TypeError as e:
        # we assume this is a comment
        if hasattr(elem, "text"):
            return f"<!-- {elem.text} -->\n"
        else:
            raise e
    if xml_str and pretty:
        pretty_string = xml.dom.minidom.parseString(xml_str).toprettyxml(indent="    ")
        return "\n".join(line for line in pretty_string.split("\n") if not re.match(r"^[\s\\nb\']*$", line))
    return xml_str


def xml_element_compare(elem1, elem2):
    if not isinstance(elem1, dict):
        elem1 = xml_element_to_dict(elem1)
    if not isinstance(elem2, dict):
        elem2 = xml_element_to_dict(elem2)
    return elem1 == elem2


def xml_element_list_compare(elem_list1, elem_list2):
    return [xml_element_to_dict(elem) for elem in elem_list1] == [xml_element_to_dict(elem) for elem in elem_list2]


def xml_element_to_dict(elem):
    rval = {}
    if elem.attrib:
        rval[elem.tag] = {}
    else:
        rval[elem.tag] = None

    sub_elems = list(elem)
    if sub_elems:
        sub_elem_dict = dict()
        for sub_sub_elem_dict in map(xml_element_to_dict, sub_elems):
            for key, value in sub_sub_elem_dict.items():
                if key not in sub_elem_dict:
                    sub_elem_dict[key] = []
                sub_elem_dict[key].append(value)
        for key, value in sub_elem_dict.items():
            if len(value) == 1:
                rval[elem.tag][key] = value[0]
            else:
                rval[elem.tag][key] = value
    if elem.attrib:
        for key, value in elem.attrib.items():
            rval[elem.tag][f"@{key}"] = value

    if elem.text:
        text = elem.text.strip()
        if text and sub_elems or elem.attrib:
            rval[elem.tag]["#text"] = text
        else:
            rval[elem.tag] = text

    return rval


def pretty_print_xml(elem, level=0):
    pad = "    "
    i = "\n" + level * pad
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + pad + pad
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for e in elem:
            pretty_print_xml(e, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i + pad
    return elem


def get_file_size(value, default=None):
    try:
        # try built-in
        return os.path.getsize(value)
    except Exception:
        try:
            # try built-in one name attribute
            return os.path.getsize(value.name)
        except Exception:
            try:
                # try tell() of end of object
                offset = value.tell()
                value.seek(0, 2)
                rval = value.tell()
                value.seek(offset)
                return rval
            except Exception:
                # return default value
                return default


def shrink_stream_by_size(
    value, size, join_by=b"..", left_larger=True, beginning_on_size_error=False, end_on_size_error=False
):
    """
    Shrinks bytes read from `value` to `size`.

    `value` needs to implement tell/seek, so files need to be opened in binary mode.
    Returns unicode text with invalid characters replaced.
    """
    rval = b""
    join_by = smart_str(join_by)
    if get_file_size(value) > size:
        start = value.tell()
        len_join_by = len(join_by)
        min_size = len_join_by + 2
        if size < min_size:
            if beginning_on_size_error:
                rval = value.read(size)
                value.seek(start)
                return rval
            elif end_on_size_error:
                value.seek(-size, 2)
                rval = value.read(size)
                value.seek(start)
                return rval
            raise ValueError(
                "With the provided join_by value (%s), the minimum size value is %i." % (join_by, min_size)
            )
        left_index = right_index = int((size - len_join_by) / 2)
        if left_index + right_index + len_join_by < size:
            if left_larger:
                left_index += 1
            else:
                right_index += 1
        rval = value.read(left_index) + join_by
        value.seek(-right_index, 2)
        rval += value.read(right_index)
    else:
        while True:
            data = value.read(CHUNK_SIZE)
            if not data:
                break
            rval += data
    return unicodify(rval)


def shrink_and_unicodify(stream):
    stream = unicodify(stream, strip_null=True) or ""
    if len(stream) > DATABASE_MAX_STRING_SIZE:
        stream = shrink_string_by_size(
            stream, DATABASE_MAX_STRING_SIZE, join_by="\n..\n", left_larger=True, beginning_on_size_error=True
        )
    return stream


def shrink_string_by_size(
    value, size, join_by="..", left_larger=True, beginning_on_size_error=False, end_on_size_error=False
):
    if len(value) > size:
        len_join_by = len(join_by)
        min_size = len_join_by + 2
        if size < min_size:
            if beginning_on_size_error:
                return value[:size]
            elif end_on_size_error:
                return value[-size:]
            raise ValueError(
                "With the provided join_by value (%s), the minimum size value is %i." % (join_by, min_size)
            )
        left_index = right_index = int((size - len_join_by) / 2)
        if left_index + right_index + len_join_by < size:
            if left_larger:
                left_index += 1
            else:
                right_index += 1
        value = f"{value[:left_index]}{join_by}{value[-right_index:]}"
    return value


def pretty_print_time_interval(time=False, precise=False, utc=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    credit: http://stackoverflow.com/questions/1551382/user-friendly-time-format-in-python
    """
    if utc:
        now = datetime.utcnow()
    else:
        now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        diff = now - time
    elif isinstance(time, str):
        try:
            time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            # MySQL may not support microseconds precision
            time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S")
        diff = now - time
    else:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ""

    if precise:
        if day_diff == 0:
            if second_diff < 10:
                return "just now"
            if second_diff < 60:
                return str(second_diff) + " seconds ago"
            if second_diff < 120:
                return "a minute ago"
            if second_diff < 3600:
                return str(second_diff / 60) + " minutes ago"
            if second_diff < 7200:
                return "an hour ago"
            if second_diff < 86400:
                return str(second_diff / 3600) + " hours ago"
        if day_diff == 1:
            return "yesterday"
        if day_diff < 7:
            return str(day_diff) + " days ago"
        if day_diff < 31:
            return str(day_diff / 7) + " weeks ago"
        if day_diff < 365:
            return str(day_diff / 30) + " months ago"
        return str(day_diff / 365) + " years ago"
    else:
        if day_diff == 0:
            return "today"
        if day_diff == 1:
            return "yesterday"
        if day_diff < 7:
            return "less than a week"
        if day_diff < 31:
            return "less than a month"
        if day_diff < 365:
            return "less than a year"
        return "a few years ago"


def pretty_print_json(json_data, is_json_string=False):
    if is_json_string:
        json_data = json.loads(json_data)
    return json.dumps(json_data, sort_keys=True, indent=4)


# characters that are valid
valid_chars = set(string.ascii_letters + string.digits + " -=_.()/+*^,:?!")

# characters that are allowed but need to be escaped
mapped_chars = {
    ">": "__gt__",
    "<": "__lt__",
    "'": "__sq__",
    '"': "__dq__",
    "[": "__ob__",
    "]": "__cb__",
    "{": "__oc__",
    "}": "__cc__",
    "@": "__at__",
    "\n": "__cn__",
    "\r": "__cr__",
    "\t": "__tc__",
    "#": "__pd__",
}


def restore_text(text, character_map=mapped_chars):
    """Restores sanitized text"""
    if not text:
        return text
    for key, value in character_map.items():
        text = text.replace(value, key)
    return text


def sanitize_text(text, valid_characters=valid_chars, character_map=mapped_chars, invalid_character="X"):
    """
    Restricts the characters that are allowed in text; accepts both strings
    and lists of strings; non-string entities will be cast to strings.
    """
    if isinstance(text, list):
        return [
            sanitize_text(
                x, valid_characters=valid_characters, character_map=character_map, invalid_character=invalid_character
            )
            for x in text
        ]
    if not isinstance(text, str):
        text = smart_str(text)
    return _sanitize_text_helper(text, valid_characters=valid_characters, character_map=character_map)


def _sanitize_text_helper(text, valid_characters=valid_chars, character_map=mapped_chars, invalid_character="X"):
    """Restricts the characters that are allowed in a string"""

    out = []
    for c in text:
        if c in valid_characters:
            out.append(c)
        elif c in character_map:
            out.append(character_map[c])
        else:
            out.append(invalid_character)  # makes debugging easier
    return "".join(out)


def sanitize_lists_to_string(values, valid_characters=valid_chars, character_map=mapped_chars, invalid_character="X"):
    if isinstance(values, list):
        rval = []
        for value in values:
            rval.append(
                sanitize_lists_to_string(
                    value,
                    valid_characters=valid_characters,
                    character_map=character_map,
                    invalid_character=invalid_character,
                )
            )
        values = ",".join(rval)
    else:
        values = sanitize_text(
            values, valid_characters=valid_characters, character_map=character_map, invalid_character=invalid_character
        )
    return values


def sanitize_param(value, valid_characters=valid_chars, character_map=mapped_chars, invalid_character="X"):
    """Clean incoming parameters (strings or lists)"""
    if isinstance(value, str):
        return sanitize_text(
            value, valid_characters=valid_characters, character_map=character_map, invalid_character=invalid_character
        )
    elif isinstance(value, list):
        return [
            sanitize_text(
                x, valid_characters=valid_characters, character_map=character_map, invalid_character=invalid_character
            )
            for x in value
        ]
    else:
        raise Exception(f"Unknown parameter type ({type(value)})")


valid_filename_chars = set(string.ascii_letters + string.digits + "_.")
invalid_filenames = ["", ".", ".."]


def sanitize_for_filename(text, default=None):
    """
    Restricts the characters that are allowed in a filename portion; Returns default value or a unique id string if result is not a valid name.
    Method is overly aggressive to minimize possible complications, but a maximum length is not considered.
    """
    out = []
    for c in text:
        if c in valid_filename_chars:
            out.append(c)
        else:
            out.append("_")
    out = "".join(out)
    if out in invalid_filenames:
        if default is None:
            return sanitize_for_filename(str(unique_id()))
        return default
    return out


def find_instance_nested(item, instances):
    """
    Recursively find instances from lists, dicts, tuples.

    `instances` should be a tuple of valid instances.
    Returns a dictionary, where keys are the deepest key at which an instance has been found,
    and the value is the matched instance.
    """

    matches = {}

    def visit(path, key, value):
        if isinstance(value, instances):
            if key not in matches:
                matches[key] = value
        return key, value

    def enter(path, key, value):
        if isinstance(value, instances):
            return None, False
        return default_enter(path, key, value)

    remap(item, visit, reraise_visit=False, enter=enter)

    return matches


def mask_password_from_url(url):
    """
    Masks out passwords from connection urls like the database connection in galaxy.ini

    >>> mask_password_from_url( 'sqlite+postgresql://user:password@localhost/' )
    'sqlite+postgresql://user:********@localhost/'
    >>> mask_password_from_url( 'amqp://user:amqp@localhost' )
    'amqp://user:********@localhost'
    >>> mask_password_from_url( 'amqp://localhost')
    'amqp://localhost'
    """
    split = urlsplit(url)
    if split.password:
        if url.count(split.password) == 1:
            url = url.replace(split.password, "********")
        else:
            # This can manipulate the input other than just masking password,
            # so the previous string replace method is preferred when the
            # password doesn't appear twice in the url
            split = split._replace(
                netloc=split.netloc.replace(f"{split.username}:{split.password}", f"{split.username}:********")
            )
            url = urlunsplit(split)
    return url


def ready_name_for_url(raw_name):
    """General method to convert a string (i.e. object name) to a URL-ready
    slug.

    >>> ready_name_for_url( "My Cool Object" )
    'My-Cool-Object'
    >>> ready_name_for_url( "!My Cool Object!" )
    'My-Cool-Object'
    >>> ready_name_for_url( "Hello₩◎ґʟⅾ" )
    'Hello'
    """

    # Replace whitespace with '-'
    slug_base = re.sub(r"\s+", "-", raw_name)
    # Remove all non-alphanumeric characters.
    slug_base = re.sub(r"[^a-zA-Z0-9\-]", "", slug_base)
    # Remove trailing '-'.
    if slug_base.endswith("-"):
        slug_base = slug_base[:-1]
    return slug_base


def which(file):
    # http://stackoverflow.com/questions/5226958/which-equivalent-function-in-python
    for path in os.environ["PATH"].split(":"):
        if os.path.exists(path + "/" + file):
            return path + "/" + file

    return None


def in_directory(file, directory, local_path_module=os.path):
    """
    Return true, if the common prefix of both is equal to directory
    e.g. /a/b/c/d.rst and directory is /a/b, the common prefix is /a/b.
    This function isn't used exclusively for security checks, but if it is
    used for such checks it is assumed that ``directory`` is a "trusted" path -
    supplied by Galaxy or by the admin and ``file`` is something generated by
    a tool, configuration, external web server, or user supplied input.

    local_path_module is used by Pulsar to check Windows paths while running on
    a POSIX-like system.
    """
    if local_path_module != os.path:
        _safe_contains = importlib.import_module(f"galaxy.util.path.{local_path_module.__name__}").safe_contains
    else:
        directory = os.path.realpath(directory)
        _safe_contains = safe_contains
    return _safe_contains(directory, file)


def merge_sorted_iterables(operator, *iterables):
    """

    >>> operator = lambda x: x
    >>> list( merge_sorted_iterables( operator, [1,2,3], [4,5] ) )
    [1, 2, 3, 4, 5]
    >>> list( merge_sorted_iterables( operator, [4, 5], [1,2,3] ) )
    [1, 2, 3, 4, 5]
    >>> list( merge_sorted_iterables( operator, [1, 4, 5], [2], [3] ) )
    [1, 2, 3, 4, 5]
    """
    first_iterable = iterables[0]
    if len(iterables) == 1:
        yield from first_iterable
    else:
        yield from __merge_two_sorted_iterables(
            operator, iter(first_iterable), merge_sorted_iterables(operator, *iterables[1:])
        )


def __merge_two_sorted_iterables(operator, iterable1, iterable2):
    unset = object()
    continue_merge = True
    next_1 = unset
    next_2 = unset
    while continue_merge:
        try:
            if next_1 is unset:
                next_1 = next(iterable1)
            if next_2 is unset:
                next_2 = next(iterable2)
            if operator(next_2) < operator(next_1):
                yield next_2
                next_2 = unset
            else:
                yield next_1
                next_1 = unset
        except StopIteration:
            continue_merge = False
    if next_1 is not unset:
        yield next_1
    if next_2 is not unset:
        yield next_2
    yield from iterable1
    yield from iterable2


class Params:
    """
    Stores and 'sanitizes' parameters. Alphanumeric characters and the
    non-alphanumeric ones that are deemed safe are let to pass through (see L{valid_chars}).
    Some non-safe characters are escaped to safe forms for example C{>} becomes C{__lt__}
    (see L{mapped_chars}). All other characters are replaced with C{X}.

    Operates on string or list values only (HTTP parameters).

    >>> values = { 'status':'on', 'symbols':[  'alpha', '<>', '$rm&#!' ]  }
    >>> par = Params(values)
    >>> par.status
    'on'
    >>> par.value == None      # missing attributes return None
    True
    >>> par.get('price', 0)
    0
    >>> par.symbols            # replaces unknown symbols with X
    ['alpha', '__lt____gt__', 'XrmX__pd__!']
    >>> sorted(par.flatten())  # flattening to a list
    [('status', 'on'), ('symbols', 'XrmX__pd__!'), ('symbols', '__lt____gt__'), ('symbols', 'alpha')]
    """

    # is NEVER_SANITIZE required now that sanitizing for tool parameters can be controlled on a per parameter basis and occurs via InputValueWrappers?
    NEVER_SANITIZE = ["file_data", "url_paste", "URL", "filesystem_paths"]

    def __init__(self, params, sanitize=True):
        if sanitize:
            for key, value in params.items():
                # sanitize check both ungrouped and grouped parameters by
                # name. Anything relying on NEVER_SANITIZE should be
                # changed to not require this and NEVER_SANITIZE should be
                # removed.
                if (
                    value is not None
                    and key not in self.NEVER_SANITIZE
                    and True
                    not in [key.endswith(f"|{nonsanitize_parameter}") for nonsanitize_parameter in self.NEVER_SANITIZE]
                ):
                    self.__dict__[key] = sanitize_param(value)
                else:
                    self.__dict__[key] = value
        else:
            self.__dict__.update(params)

    def flatten(self):
        """
        Creates a tuple list from a dict with a tuple/value pair for every value that is a list
        """
        flat = []
        for key, value in self.__dict__.items():
            if isinstance(value, list):
                for v in value:
                    flat.append((key, v))
            else:
                flat.append((key, value))
        return flat

    def __getattr__(self, name):
        """This is here to ensure that we get None for non existing parameters"""
        return None

    def get(self, key, default):
        return self.__dict__.get(key, default)

    def __str__(self):
        return f"{self.__dict__}"

    def __len__(self):
        return len(self.__dict__)

    def __iter__(self):
        return iter(self.__dict__)

    def update(self, values):
        self.__dict__.update(values)


def rst_to_html(s, error=False):
    """Convert a blob of reStructuredText to HTML"""
    log = get_logger("docutils")

    if docutils_core is None:
        raise Exception("Attempted to use rst_to_html but docutils unavailable.")

    class FakeStream:
        def write(self, str):
            if len(str) > 0 and not str.isspace():
                if error:
                    raise Exception(str)
                log.warning(str)

    settings_overrides = {
        "embed_stylesheet": False,
        "template": os.path.join(os.path.dirname(__file__), "docutils_template.txt"),
        "warning_stream": FakeStream(),
        "doctitle_xform": False,  # without option, very different rendering depending on
        # number of sections in help content.
    }

    return unicodify(
        docutils_core.publish_string(s, writer=docutils_html4css1.Writer(), settings_overrides=settings_overrides)
    )


def xml_text(root, name=None):
    """Returns the text inside an element"""
    if name is not None:
        # Try attribute first
        val = root.get(name)
        if val:
            return val
        # Then try as element
        elem = root.find(name)
    else:
        elem = root
    if elem is not None and elem.text:
        text = "".join(elem.text.splitlines())
        return text.strip()
    # No luck, return empty string
    return ""


def parse_resource_parameters(resource_param_file):
    """Code shared between jobs and workflows for reading resource parameter configuration files.

    TODO: Allow YAML in addition to XML.
    """
    resource_parameters = {}
    if os.path.exists(resource_param_file):
        resource_definitions = parse_xml(resource_param_file)
        resource_definitions_root = resource_definitions.getroot()
        for parameter_elem in resource_definitions_root.findall("param"):
            name = parameter_elem.get("name")
            resource_parameters[name] = parameter_elem

    return resource_parameters


# asbool implementation pulled from PasteDeploy
truthy = frozenset({"true", "yes", "on", "y", "t", "1"})
falsy = frozenset({"false", "no", "off", "n", "f", "0"})


def asbool(obj):
    if isinstance(obj, str):
        obj = obj.strip().lower()
        if obj in truthy:
            return True
        elif obj in falsy:
            return False
        else:
            raise ValueError(f"String is not true/false: {obj!r}")
    return bool(obj)


def string_as_bool(string: typing.Any) -> bool:
    if str(string).lower() in ("true", "yes", "on", "1"):
        return True
    else:
        return False


def string_as_bool_or_none(string):
    """
    Returns True, None or False based on the argument:
        True if passed True, 'True', 'Yes', or 'On'
        None if passed None or 'None'
        False otherwise

    Note: string comparison is case-insensitive so lowecase versions of those
    function equivalently.
    """
    string = str(string).lower()
    if string in ("true", "yes", "on"):
        return True
    elif string in ["none", "null"]:
        return None
    else:
        return False


def listify(item, do_strip=False) -> typing.List[typing.Any]:
    """
    Make a single item a single item list.

    If *item* is a string, it is split on comma (``,``) characters to produce the list. Optionally, if *do_strip* is
    true, any extra whitespace around the split items is stripped.

    If *item* is a list it is returned unchanged. If *item* is a tuple, it is converted to a list and returned. If
    *item* evaluates to False, an empty list is returned.

    :type  item:        object
    :param item:        object to make a list from
    :type  do_strip:    bool
    :param do_strip:    strip whitespaces from around split items, if set to ``True``
    :rtype:             list
    :returns:           The input as a list
    """
    if not item:
        return []
    elif isinstance(item, list):
        return item
    elif isinstance(item, tuple):
        return list(item)
    elif isinstance(item, str) and item.count(","):
        if do_strip:
            return [token.strip() for token in item.split(",")]
        else:
            return item.split(",")
    else:
        return [item]


def commaify(amount):
    orig = amount
    new = re.sub(r"^(-?\d+)(\d{3})", r"\g<1>,\g<2>", amount)
    if orig == new:
        return new
    else:
        return commaify(new)


def roundify(amount, sfs=2):
    """
    Take a number in string form and truncate to 'sfs' significant figures.
    """
    if len(amount) <= sfs:
        return amount
    else:
        return amount[0:sfs] + "0" * (len(amount) - sfs)


@overload
def unicodify(  # type: ignore[misc]
    value: Literal[None],
    encoding: str = DEFAULT_ENCODING,
    error: str = "replace",
    strip_null: bool = False,
    log_exception: bool = True,
) -> None:
    ...


@overload
def unicodify(
    value: Any,
    encoding: str = DEFAULT_ENCODING,
    error: str = "replace",
    strip_null: bool = False,
    log_exception: bool = True,
) -> str:
    ...


def unicodify(
    value: Any,
    encoding: str = DEFAULT_ENCODING,
    error: str = "replace",
    strip_null: bool = False,
    log_exception: bool = True,
) -> Optional[str]:
    """
    Returns a Unicode string or None.

    >>> assert unicodify(None) is None
    >>> assert unicodify('simple string') == 'simple string'
    >>> assert unicodify(3) == '3'
    >>> assert unicodify(bytearray([115, 116, 114, 196, 169, 195, 177, 103])) == 'strĩñg'
    >>> assert unicodify(Exception('strĩñg')) == 'strĩñg'
    >>> assert unicodify('cómplǐcḁtëd strĩñg') == 'cómplǐcḁtëd strĩñg'
    >>> s = 'cómplǐcḁtëd strĩñg'; assert unicodify(s) == s
    >>> s = 'lâtín strìñg'; assert unicodify(s.encode('latin-1'), 'latin-1') == s
    >>> s = 'lâtín strìñg'; assert unicodify(s.encode('latin-1')) == 'l\ufffdt\ufffdn str\ufffd\ufffdg'
    >>> s = 'lâtín strìñg'; assert unicodify(s.encode('latin-1'), error='ignore') == 'ltn strg'
    """
    if value is None:
        return value
    try:
        if isinstance(value, bytearray):
            value = bytes(value)
        elif not isinstance(value, (str, bytes)):
            value = str(value)
        # Now value is an instance of bytes or str
        if not isinstance(value, str):
            value = str(value, encoding, error)
    except Exception as e:
        if log_exception:
            msg = f"Value '{repr(value)}' could not be coerced to Unicode: {type(e).__name__}('{e}')"
            log.exception(msg)
        raise
    if strip_null:
        return value.replace("\0", "")
    return value


def filesystem_safe_string(
    s, max_len=255, truncation_chars="..", strip_leading_dot=True, invalid_chars=("/",), replacement_char="_"
):
    """
    Strip unicode null chars, truncate at 255 characters.
    Optionally replace additional ``invalid_chars`` with `replacement_char` .

    Defaults are probably only safe on linux / osx.
    Needs further escaping if used in shell commands
    """
    sanitized_string = unicodify(s, strip_null=True)
    if strip_leading_dot:
        sanitized_string = sanitized_string.lstrip(".")
    for invalid_char in invalid_chars:
        sanitized_string = sanitized_string.replace(invalid_char, replacement_char)
    if len(sanitized_string) > max_len:
        sanitized_string = sanitized_string[: max_len - len(truncation_chars)]
        sanitized_string = f"{sanitized_string}{truncation_chars}"
    return sanitized_string


def smart_str(s, encoding=DEFAULT_ENCODING, strings_only=False, errors="strict"):
    """
    Returns a bytestring version of 's', encoded as specified in 'encoding'.

    If strings_only is True, don't convert (some) non-string-like objects.

    Adapted from an older, simpler version of django.utils.encoding.smart_str.

    >>> assert smart_str(None) == b'None'
    >>> assert smart_str(None, strings_only=True) is None
    >>> assert smart_str(3) == b'3'
    >>> assert smart_str(3, strings_only=True) == 3
    >>> s = b'a bytes string'; assert smart_str(s) == s
    >>> s = bytearray(b'a bytes string'); assert smart_str(s) == s
    >>> assert smart_str('a simple unicode string') == b'a simple unicode string'
    >>> assert smart_str('à strange ünicode ڃtring') == b'\\xc3\\xa0 strange \\xc3\\xbcnicode \\xda\\x83tring'
    >>> assert smart_str(b'\\xc3\\xa0n \\xc3\\xabncoded utf-8 string', encoding='latin-1') == b'\\xe0n \\xebncoded utf-8 string'
    >>> assert smart_str(bytearray(b'\\xc3\\xa0n \\xc3\\xabncoded utf-8 string'), encoding='latin-1') == b'\\xe0n \\xebncoded utf-8 string'
    """
    if strings_only and isinstance(s, (type(None), int)):
        return s
    if not isinstance(s, (str, bytes, bytearray)):
        s = str(s)
    # Now s is an instance of str, bytes or bytearray
    if not isinstance(s, (bytes, bytearray)):
        return s.encode(encoding, errors)
    elif s and encoding != DEFAULT_ENCODING:
        return s.decode(DEFAULT_ENCODING, errors).encode(encoding, errors)
    else:
        return s


def strip_control_characters(s):
    """Strip unicode control characters from a string."""
    return "".join(c for c in unicodify(s) if unicodedata.category(c) != "Cc")


def object_to_string(obj):
    return binascii.hexlify(obj)


def string_to_object(s):
    return binascii.unhexlify(s)


def clean_multiline_string(multiline_string, sep="\n"):
    """
    Dedent, split, remove first and last empty lines, rejoin.
    """
    multiline_string = textwrap.dedent(multiline_string)
    string_list = multiline_string.split(sep)
    if not string_list[0]:
        string_list = string_list[1:]
    if not string_list[-1]:
        string_list = string_list[:-1]
    return "\n".join(string_list) + "\n"


class ParamsWithSpecs(collections.defaultdict):
    """ """

    def __init__(self, specs=None, params=None):
        self.specs = specs or dict()
        self.params = params or dict()
        for name, value in self.params.items():
            if name not in self.specs:
                self._param_unknown_error(name)
            if "map" in self.specs[name]:
                try:
                    self.params[name] = self.specs[name]["map"](value)
                except Exception:
                    self._param_map_error(name, value)
            if "valid" in self.specs[name]:
                if not self.specs[name]["valid"](value):
                    self._param_vaildation_error(name, value)

        self.update(self.params)

    def __missing__(self, name):
        return self.specs[name]["default"]

    def __getattr__(self, name):
        return self[name]

    def _param_unknown_error(self, name):
        raise NotImplementedError()

    def _param_map_error(self, name, value):
        raise NotImplementedError()

    def _param_vaildation_error(self, name, value):
        raise NotImplementedError()


def compare_urls(url1, url2, compare_scheme=True, compare_hostname=True, compare_path=True):
    url1 = urlparse(url1)
    url2 = urlparse(url2)
    if compare_scheme and url1.scheme and url2.scheme and url1.scheme != url2.scheme:
        return False
    if compare_hostname and url1.hostname and url2.hostname and url1.hostname != url2.hostname:
        return False
    if compare_path and url1.path and url2.path and url1.path != url2.path:
        return False
    return True


def read_build_sites(filename, check_builds=True):
    """read db names to ucsc mappings from file, this file should probably be merged with the one above"""
    build_sites = []
    try:
        for line in open(filename):
            try:
                if line[0:1] == "#":
                    continue
                fields = line.replace("\r", "").replace("\n", "").split("\t")
                site_name = fields[0]
                site = fields[1]
                if check_builds:
                    site_builds = fields[2].split(",")
                    site_dict = {"name": site_name, "url": site, "builds": site_builds}
                else:
                    site_dict = {"name": site_name, "url": site}
                build_sites.append(site_dict)
            except Exception:
                continue
    except Exception:
        log.error("ERROR: Unable to read builds for site file %s", filename)
    return build_sites


def relativize_symlinks(path, start=None, followlinks=False):
    for root, _, files in os.walk(path, followlinks=followlinks):
        rel_start = None
        for file_name in files:
            symlink_file_name = os.path.join(root, file_name)
            if os.path.islink(symlink_file_name):
                symlink_target = os.readlink(symlink_file_name)
                if rel_start is None:
                    if start is None:
                        rel_start = root
                    else:
                        rel_start = start
                rel_path = relpath(symlink_target, rel_start)
                os.remove(symlink_file_name)
                os.symlink(rel_path, symlink_file_name)


def stringify_dictionary_keys(in_dict):
    # returns a new dictionary
    # changes unicode keys into strings, only works on top level (does not recurse)
    # unicode keys are not valid for expansion into keyword arguments on method calls
    out_dict = {}
    for key, value in in_dict.items():
        out_dict[str(key)] = value
    return out_dict


def mkstemp_ln(src, prefix="mkstemp_ln_"):
    """
    From tempfile._mkstemp_inner, generate a hard link in the same dir with a
    random name.  Created so we can persist the underlying file of a
    NamedTemporaryFile upon its closure.
    """
    dir = os.path.dirname(src)
    names = tempfile._get_candidate_names()
    for _ in range(tempfile.TMP_MAX):
        name = next(names)
        file = os.path.join(dir, prefix + name)
        try:
            os.link(src, file)
            return os.path.abspath(file)
        except OSError as e:
            if e.errno == errno.EEXIST:
                continue  # try again
            raise
    raise OSError(errno.EEXIST, "No usable temporary file name found")


def umask_fix_perms(path, umask, unmasked_perms, gid=None):
    """
    umask-friendly permissions fixing
    """
    perms = unmasked_perms & ~umask
    try:
        st = os.stat(path)
    except OSError:
        log.exception("Unable to set permissions or group on %s", path)
        return
    # fix modes
    if stat.S_IMODE(st.st_mode) != perms:
        try:
            os.chmod(path, perms)
        except Exception as e:
            log.warning(
                "Unable to honor umask ({}) for {}, tried to set: {} but mode remains {}, error was: {}".format(
                    oct(umask), path, oct(perms), oct(stat.S_IMODE(st.st_mode)), unicodify(e)
                )
            )
    # fix group
    if gid is not None and st.st_gid != gid:
        try:
            os.chown(path, -1, gid)
        except Exception as e:
            try:
                desired_group = grp.getgrgid(gid)
                current_group = grp.getgrgid(st.st_gid)
            except Exception:
                desired_group = gid
                current_group = st.st_gid
            log.warning(
                "Unable to honor primary group ({}) for {}, group remains {}, error was: {}".format(
                    desired_group, path, current_group, unicodify(e)
                )
            )


def docstring_trim(docstring):
    """Trimming python doc strings. Taken from: http://www.python.org/dev/peps/pep-0257/"""
    if not docstring:
        return ""
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return "\n".join(trimmed)


def nice_size(size):
    """
    Returns a readably formatted string with the size

    >>> nice_size(100)
    '100 bytes'
    >>> nice_size(10000)
    '9.8 KB'
    >>> nice_size(1000000)
    '976.6 KB'
    >>> nice_size(100000000)
    '95.4 MB'
    """
    words = ["bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    prefix = ""
    try:
        size = float(size)
        if size < 0:
            size = abs(size)
            prefix = "-"
    except Exception:
        return "??? bytes"
    for ind, word in enumerate(words):
        step = 1024 ** (ind + 1)
        if step > size:
            size = size / float(1024**ind)
            if word == "bytes":  # No decimals for bytes
                return "%s%d bytes" % (prefix, size)
            return f"{prefix}{size:.1f} {word}"
    return "??? bytes"


def size_to_bytes(size):
    """
    Returns a number of bytes (as integer) if given a reasonably formatted string with the size

    >>> size_to_bytes('1024')
    1024
    >>> size_to_bytes('1.0')
    1
    >>> size_to_bytes('10 bytes')
    10
    >>> size_to_bytes('4k')
    4096
    >>> size_to_bytes('2.2 TB')
    2418925581107
    >>> size_to_bytes('.01 TB')
    10995116277
    >>> size_to_bytes('1.b')
    1
    >>> size_to_bytes('1.2E2k')
    122880
    """
    # The following number regexp is based on https://stackoverflow.com/questions/385558/extract-float-double-value/385597#385597
    size_re = re.compile(r"(?P<number>(\d+(\.\d*)?|\.\d+)(e[+-]?\d+)?)\s*(?P<multiple>[eptgmk]?(b|bytes?)?)?$")
    size_match = size_re.match(size.lower())
    if size_match is None:
        raise ValueError(f"Could not parse string '{size}'")
    number = float(size_match.group("number"))
    multiple = size_match.group("multiple")
    if multiple == "" or multiple.startswith("b"):
        return int(number)
    elif multiple.startswith("k"):
        return int(number * 1024)
    elif multiple.startswith("m"):
        return int(number * 1024**2)
    elif multiple.startswith("g"):
        return int(number * 1024**3)
    elif multiple.startswith("t"):
        return int(number * 1024**4)
    elif multiple.startswith("p"):
        return int(number * 1024**5)
    elif multiple.startswith("e"):
        return int(number * 1024**6)
    else:
        raise ValueError(f"Unknown multiplier '{multiple}' in '{size}'")


def send_mail(frm, to, subject, body, config, html=None):
    """
    Sends an email.

    :type  frm: str
    :param frm: from address

    :type  to: str
    :param to: to address

    :type  subject: str
    :param subject: Subject line

    :type  body: str
    :param body: Body text (should be plain text)

    :type  config: object
    :param config: Galaxy configuration object

    :type  html: str
    :param html: Alternative HTML representation of the body content. If
                 provided will convert the message to a MIMEMultipart. (Default 'None')
    """

    to = listify(to)
    if html:
        msg = MIMEMultipart("alternative")
    else:
        msg = MIMEText(body, "plain", "utf-8")

    msg["To"] = ", ".join(to)
    msg["From"] = frm
    msg["Subject"] = subject

    if config.smtp_server is None:
        log.error("Mail is not configured for this Galaxy instance.")
        log.info(msg)
        return

    if html:
        mp_text = MIMEText(body, "plain", "utf-8")
        mp_html = MIMEText(html, "html", "utf-8")
        msg.attach(mp_text)
        msg.attach(mp_html)

    smtp_ssl = asbool(getattr(config, "smtp_ssl", False))
    if smtp_ssl:
        s = smtplib.SMTP_SSL(config.smtp_server)
    else:
        s = smtplib.SMTP(config.smtp_server)
    if not smtp_ssl:
        try:
            s.starttls()
            log.debug("Initiated SSL/TLS connection to SMTP server: %s", config.smtp_server)
        except RuntimeError as e:
            log.warning("SSL/TLS support is not available to your Python interpreter: %s", unicodify(e))
        except smtplib.SMTPHeloError as e:
            log.error("The server didn't reply properly to the HELO greeting: %s", unicodify(e))
            s.close()
            raise
        except smtplib.SMTPException as e:
            log.warning("The server does not support the STARTTLS extension: %s", unicodify(e))
    if config.smtp_username and config.smtp_password:
        try:
            s.login(config.smtp_username, config.smtp_password)
        except smtplib.SMTPHeloError as e:
            log.error("The server didn't reply properly to the HELO greeting: %s", unicodify(e))
            s.close()
            raise
        except smtplib.SMTPAuthenticationError as e:
            log.error("The server didn't accept the username/password combination: %s", unicodify(e))
            s.close()
            raise
        except smtplib.SMTPException as e:
            log.error("No suitable authentication method was found: %s", unicodify(e))
            s.close()
            raise
    s.sendmail(frm, to, msg.as_string())
    s.quit()


def force_symlink(source, link_name):
    try:
        os.symlink(source, link_name)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.symlink(source, link_name)
        else:
            raise e


def unlink(path_or_fd, ignore_errors=False):
    """Calls os.unlink on `path_or_fd`, and ignore FileNoteFoundError if ignore_errors is True."""
    try:
        os.unlink(path_or_fd)
    except FileNotFoundError:
        if ignore_errors:
            pass
        else:
            raise


def move_merge(source, target):
    # when using shutil and moving a directory, if the target exists,
    # then the directory is placed inside of it
    # if the target doesn't exist, then the target is made into the directory
    # this makes it so that the target is always the target, and if it exists,
    # the source contents are moved into the target
    if os.path.isdir(source) and os.path.exists(target) and os.path.isdir(target):
        for name in os.listdir(source):
            move_merge(os.path.join(source, name), os.path.join(target, name))
    else:
        return shutil.move(source, target)


def safe_str_cmp(a, b):
    """safely compare two strings in a timing-attack-resistant manner"""
    if len(a) != len(b):
        return False
    rv = 0
    for x, y in zip(a, b):
        rv |= ord(x) ^ ord(y)
    return rv == 0


#  Don't use these two directly, prefer method version that "works" with packaged Galaxy.
galaxy_root_path = os.path.join(__path__[0], os.pardir, os.pardir, os.pardir)  # type: ignore[name-defined]
galaxy_samples_path = os.path.join(__path__[0], os.pardir, "config", "sample")  # type: ignore[name-defined]


def galaxy_directory():
    root_path = os.path.abspath(galaxy_root_path)
    if os.path.basename(root_path) == "packages":
        root_path = os.path.abspath(os.path.join(root_path, ".."))
    return root_path


def galaxy_samples_directory():
    return os.path.join(galaxy_directory(), "lib", "galaxy", "config", "sample")


def config_directories_from_setting(directories_setting, galaxy_root=galaxy_root_path):
    """
    Parse the ``directories_setting`` into a list of relative or absolute
    filesystem paths that will be searched to discover plugins.

    :type   galaxy_root:    string
    :param  galaxy_root:    the root path of this galaxy installation
    :type   directories_setting: string (default: None)
    :param  directories_setting: the filesystem path (or paths)
        to search for plugins. Can be CSV string of paths. Will be treated as
        absolute if a path starts with '/', relative otherwise.
    :rtype:                 list of strings
    :returns:               list of filesystem paths
    """
    directories = []
    if not directories_setting:
        return directories

    for directory in listify(directories_setting):
        directory = directory.strip()
        if not directory.startswith("/"):
            directory = os.path.join(galaxy_root, directory)
        if not os.path.exists(directory):
            log.warning("directory not found: %s", directory)
            continue
        directories.append(directory)
    return directories


def parse_int(value, min_val=None, max_val=None, default=None, allow_none=False):
    try:
        value = int(value)
        if min_val is not None and value < min_val:
            return min_val
        if max_val is not None and value > max_val:
            return max_val
        return value
    except ValueError:
        if allow_none:
            if default is None or value == "None":
                return None
        if default:
            return default
        else:
            raise


def parse_non_hex_float(s):
    r"""
    Parse string `s` into a float but throw a `ValueError` if the string is in
    the otherwise acceptable format `\d+e\d+` (e.g. 40000000000000e5.)

    This can be passed into `json.loads` to prevent a hex string in the above
    format from being incorrectly parsed as a float in scientific notation.

    >>> parse_non_hex_float( '123.4' )
    123.4
    >>> parse_non_hex_float( '2.45e+3' )
    2450.0
    >>> parse_non_hex_float( '2.45e-3' )
    0.00245
    >>> parse_non_hex_float( '40000000000000e5' )
    Traceback (most recent call last):
        ...
    ValueError: could not convert string to float: 40000000000000e5
    """
    f = float(s)
    # successfully parsed as float if here - check for format in original string
    if "e" in s and not ("+" in s or "-" in s):
        raise ValueError("could not convert string to float: " + s)
    return f


def build_url(base_url, port=80, scheme="http", pathspec=None, params=None, doseq=False):
    if params is None:
        params = dict()
    if pathspec is None:
        pathspec = []
    parsed_url = urlparse(base_url)
    if scheme != "http":
        parsed_url.scheme = scheme
    assert parsed_url.scheme in ("http", "https", "ftp"), f"Invalid URL scheme: {scheme}"
    if port != 80:
        url = "%s://%s:%d/%s" % (parsed_url.scheme, parsed_url.netloc.rstrip("/"), int(port), parsed_url.path)
    else:
        url = f"{parsed_url.scheme}://{parsed_url.netloc.rstrip('/')}/{parsed_url.path.lstrip('/')}"
    if len(pathspec) > 0:
        url = f"{url.rstrip('/')}/{'/'.join(pathspec)}"
    if parsed_url.query:
        for query_parameter in parsed_url.query.split("&"):
            key, value = query_parameter.split("=")
            params[key] = value
    if params:
        url += f"?{urlencode(params, doseq=doseq)}"
    return url


def url_get(base_url, auth=None, pathspec=None, params=None, max_retries=5, backoff_factor=1):
    """Make contact with the uri provided and return any contents."""
    full_url = build_url(base_url, pathspec=pathspec, params=params)
    s = requests.Session()
    retries = Retry(total=max_retries, backoff_factor=backoff_factor, status_forcelist=[429])
    s.mount(base_url, HTTPAdapter(max_retries=retries))
    response = s.get(full_url, auth=auth)
    response.raise_for_status()
    return response.text


def is_url(uri, allow_list=None):
    """
    Check if uri is (most likely) an URL, more precisely the function checks
    if uri starts with a scheme from the allow list (defaults to "http://",
    "https://", "ftp://")
    >>> is_url('https://zenodo.org/record/4104428/files/UCSC-hg38-chr22-Coding-Exons.bed')
    True
    >>> is_url('file:///some/path')
    False
    >>> is_url('/some/path')
    False
    """
    if allow_list is None:
        allow_list = ("http://", "https://", "ftp://")
    return any(uri.startswith(scheme) for scheme in allow_list)


def download_to_file(url, dest_file_path, timeout=30, chunk_size=2**20):
    """Download a URL to a file in chunks."""
    with requests.get(url, timeout=timeout, stream=True) as r, open(dest_file_path, "wb") as f:
        for chunk in r.iter_content(chunk_size):
            if chunk:
                f.write(chunk)


def stream_to_open_named_file(
    stream, fd, filename, source_encoding=None, source_error="strict", target_encoding=None, target_error="strict"
):
    """Writes a stream to the provided file descriptor, returns the file name. Closes file descriptor"""
    # signature and behavor is somewhat odd, due to backwards compatibility, but this can/should be done better
    CHUNK_SIZE = 1048576
    try:
        codecs.lookup(target_encoding)
    except Exception:
        target_encoding = DEFAULT_ENCODING  # utf-8
    use_source_encoding = source_encoding is not None
    try:
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            if use_source_encoding:
                # If a source encoding is given we use it to convert to the target encoding
                try:
                    if not isinstance(chunk, str):
                        chunk = chunk.decode(source_encoding, source_error)
                    os.write(fd, chunk.encode(target_encoding, target_error))
                except UnicodeDecodeError:
                    use_source_encoding = False
                    os.write(fd, chunk)
            else:
                # Compressed files must be encoded after they are uncompressed in the upload utility,
                # while binary files should not be encoded at all.
                if isinstance(chunk, str):
                    chunk = chunk.encode(target_encoding, target_error)
                os.write(fd, chunk)
    finally:
        os.close(fd)
    return filename


class classproperty:
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


class ExecutionTimer:
    def __init__(self):
        self.begin = time.time()

    def __str__(self):
        return f"({self.elapsed * 1000:0.3f} ms)"

    @property
    def elapsed(self):
        return time.time() - self.begin


class StructuredExecutionTimer:
    def __init__(self, timer_id, template, **tags):
        self.begin = time.time()
        self.timer_id = timer_id
        self.template = template
        self.tags = tags

    def __str__(self):
        return self.to_str()

    def to_str(self, **kwd):
        if kwd:
            message = string.Template(self.template).safe_substitute(kwd)
        else:
            message = self.template
        log_message = message + f" ({self.elapsed * 1000:0.3f} ms)"
        return log_message

    @property
    def elapsed(self):
        return time.time() - self.begin


if __name__ == "__main__":
    import doctest

    doctest.testmod(sys.modules[__name__], verbose=False)
