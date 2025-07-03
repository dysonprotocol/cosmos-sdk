#!/usr/bin/env python
"""
Extended bencoding implementation supporting **all basic Python data types**
(as defined in the built‑ins module) *and* offering an opt‑in flag to preserve
raw‐bytes vs UTF‑8 strings.

**Scalar tags**                                     | Bytes pattern
----------------------------------------------------|----------------
`None`                                              | ``ne``
`bool`                                              | ``b1e`` / ``b0e``
`int`                                               | ``i<digits>e``
`float`                                             | ``f<repr>e``

**Byte‑like & text**                                | Bytes pattern
----------------------------------------------------|----------------
`bytes` / `bytearray`                               | ``<len>:<payload>``
`str` (UTF‑8)                                       | *same*, detected at decode time unless
                                                   ``strict_bytes=True``

**Collections**                                     | Bytes pattern
----------------------------------------------------|----------------
`list`                                              | ``l…e``
`tuple`                                             | ``t…e``
`set` / `frozenset`                                 | ``s…e`` (items sorted by encoded bytes)
`dict`                                              | ``d…e`` (keys `bytes`/`str`, sorted)

---

**Round‑trip examples**

>>> decode(encode((True, None, 3.14)))
(True, None, 3.14)
>>> decode(b'1:a')  # default: auto UTF‑8
'a'
>>> decode(b'1:a', strict_bytes=True)
b'a'
>>> {decode(b'1:a'), decode(b'1:a', strict_bytes=True)} == {'a', b'a'}
True
"""

from __future__ import annotations

import itertools as it
import re
import string
from typing import Any, Iterable

__all__ = ["encode", "decode"]

# ---------------------------------------------------------------------------
# Encoding helpers & constants
# ---------------------------------------------------------------------------

_DIGITS = set(string.digits.encode())
_BOOLEAN_PREFIX = b"b"
_FLOAT_PREFIX = b"f"
_NONE_PREFIX = b"n"
_TUPLE_PREFIX = b"t"
_SET_PREFIX = b"s"
_INT_PREFIX = b"i"
_LIST_PREFIX = b"l"
_DICT_PREFIX = b"d"
_END = b"e"
_COLON = b":"


def _encode_iterable(items: Iterable[Any]) -> bytes:
    """Helper that joins *encoded* items into a single ``bytes`` blob."""
    return b"".join(map(encode, items))


# ---------------------------------------------------------------------------
# Public API – encode
# ---------------------------------------------------------------------------

def encode(obj: Any) -> bytes:  # noqa: C901 complexity acceptable for clarity
    """B‑encodes *obj*.

    Supported types: ``None``, ``bool``, ``int``, ``float``, ``bytes``,
    ``bytearray``, ``str``, ``list``, ``tuple``, ``set``, ``frozenset``, ``dict``.

    For ``dict`` keys only ``bytes`` or ``str`` are allowed; ``str`` keys are
    UTF‑8 encoded automatically. Keys are sorted lexicographically (byte order)
    to guarantee deterministic output.
    """

    # -- Simple scalar types --------------------------------------------------
    if obj is None:
        return _NONE_PREFIX + _END  # b"ne"

    # ``bool`` precedes ``int`` (bool is a subclass of int).
    if isinstance(obj, bool):
        return _BOOLEAN_PREFIX + (b"1" if obj else b"0") + _END

    if isinstance(obj, int):
        return _INT_PREFIX + str(obj).encode() + _END

    if isinstance(obj, float):
        return _FLOAT_PREFIX + repr(obj).encode() + _END

    # -- Byte‑like and text ---------------------------------------------------
    if isinstance(obj, (bytes, bytearray)):
        bobj = bytes(obj)
        return str(len(bobj)).encode() + _COLON + bobj

    if isinstance(obj, str):
        return encode(obj.encode("utf-8"))

    # -- Sequences ------------------------------------------------------------
    if isinstance(obj, list):
        return _LIST_PREFIX + _encode_iterable(obj) + _END

    if isinstance(obj, tuple):
        return _TUPLE_PREFIX + _encode_iterable(obj) + _END

    # -- Sets (unordered) -----------------------------------------------------
    if isinstance(obj, (set, frozenset)):
        encoded_items = sorted(map(encode, obj))  # deterministic order
        return _SET_PREFIX + b"".join(encoded_items) + _END

    # -- Mapping --------------------------------------------------------------
    if isinstance(obj, dict):
        converted: list[tuple[bytes, Any]] = []
        for k, v in obj.items():
            if isinstance(k, str):
                k = k.encode("utf-8")
            elif not isinstance(k, bytes):
                raise ValueError(
                    f"dict keys should be bytes or str, not {type(k).__name__}"
                )
            converted.append((k, v))
        converted.sort(key=lambda kv: kv[0])
        return _DICT_PREFIX + _encode_iterable(it.chain(*converted)) + _END

    raise ValueError(
        "Allowed types: None, bool, int, float, bytes/bytearray, str, list, tuple,"\
        " set/frozenset, dict; not " + type(obj).__name__
    )


# ---------------------------------------------------------------------------
# Public API – decode
# ---------------------------------------------------------------------------

def decode(bdata: bytes | str, *, strict_bytes: bool = False) -> Any:
    """Decodes *bdata* back to a Python object.

    Parameters
    ----------
    bdata : ``bytes`` | ``str``
        The B‑encoded payload.
    strict_bytes : bool, default ``False``
        * ``False`` (default) – try UTF‑8 decode; if it succeeds return ``str``.
        * ``True``  – **always** return raw ``bytes`` even if the payload is
          valid UTF‑8. This lets callers disambiguate the type when needed.
    """

    if isinstance(bdata, str):
        bdata = bdata.encode("utf-8")

    value, rest = _decode_first(bdata, strict_bytes)
    if rest:
        raise ValueError("Malformed input – trailing data detected.")
    return value


# ---------------------------------------------------------------------------
# Internal – parsing helpers
# ---------------------------------------------------------------------------

_int_re = re.compile(rb"i(-?\d+)e")
_float_re = re.compile(rb"f([^e]+)e")
_bool_re = re.compile(rb"b([01])e")
_length_re = re.compile(rb"(\d+):")


def _decode_first(buf: bytes, strict_bytes: bool) -> tuple[Any, bytes]:
    """Decodes *one* value from the start of *buf* and returns ``(value, rest)``."""

    # -- None ---------------------------------------------------------------
    if buf.startswith(_NONE_PREFIX):
        return None, buf[2:]

    # -- Bool ---------------------------------------------------------------
    if buf.startswith(_BOOLEAN_PREFIX):
        m = _bool_re.match(buf)
        if not m:
            raise ValueError("Malformed bool value")
        return (m.group(1) == b"1"), buf[m.end():]

    # -- Int ----------------------------------------------------------------
    if buf.startswith(_INT_PREFIX):
        m = _int_re.match(buf)
        if not m:
            raise ValueError("Malformed int value")
        return int(m.group(1)), buf[m.end():]

    # -- Float --------------------------------------------------------------
    if buf.startswith(_FLOAT_PREFIX):
        m = _float_re.match(buf)
        if not m:
            raise ValueError("Malformed float value")
        return float(m.group(1).decode()), buf[m.end():]

    # -- Lists, tuples, sets, dicts ----------------------------------------
    if buf.startswith((_LIST_PREFIX, _TUPLE_PREFIX, _SET_PREFIX, _DICT_PREFIX)):
        prefix = buf[:1]
        rest = buf[1:]
        items: list[Any] = []
        while not rest.startswith(_END):
            elem, rest = _decode_first(rest, strict_bytes)
            items.append(elem)
        rest = rest[1:]  # skip END

        if prefix == _LIST_PREFIX:
            return items, rest
        if prefix == _TUPLE_PREFIX:
            return tuple(items), rest
        if prefix == _SET_PREFIX:
            return set(items), rest
        if len(items) % 2:
            raise ValueError("Malformed dict – uneven items.")
        return {k: v for k, v in zip(items[::2], items[1::2])}, rest

    # -- Bytes / str --------------------------------------------------------
    if buf[:1] in _DIGITS:
        m = _length_re.match(buf)
        if not m:
            raise ValueError("Malformed length header")
        length = int(m.group(1))
        start = m.end()
        end = start + length
        raw = buf[start:end]
        if strict_bytes:
            return raw, buf[end:]
        try:
            return raw.decode("utf-8"), buf[end:]
        except UnicodeDecodeError:
            return raw, buf[end:]

    raise ValueError("Malformed input – unknown tag")


if __name__ == "__main__":  # pragma: no cover
    import doctest, sys

    failed, total = doctest.testmod(verbose=False)
    if failed:
        sys.exit(1)
