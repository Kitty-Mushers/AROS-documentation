# Copyright (C) 2026, The AROS Development Team. All rights reserved.
"""Hash-backed views of the AutoDocs already accepted by the output audit.

This is not a source-code scanner or a second parser.  The audit's records
remain authoritative; indexes point to those same records and parsed objects.
Unselected source files are outside this index's coverage.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class IndexedAutoDoc:
    record: dict
    parsed: object
    kind: str
    page: str
    qualifier: str

    @property
    def symbol(self):
        return self.record['entry']


class AutoDocEntryIndex:
    """Insertion-ordered entries, hash-indexed by source, symbol and page."""

    def __init__(self):
        self.clear()

    def clear(self):
        self._entries = []
        self._by_source = defaultdict(list)
        self._by_symbol = defaultdict(list)
        self._by_output = defaultdict(list)
        self._by_page = defaultdict(list)

    @staticmethod
    def _kind(document, is_hidd):
        if document.startswith('documentation/users/shell/'):
            return 'shell'
        if document.startswith('documentation/users/applications/'):
            return 'applications'
        if document.startswith('documentation/developers/autodocs/'):
            return 'hidd' if is_hidd else 'modules'
        raise ValueError('AutoDoc output has no supported category: ' + document)

    def add(self, record, parsed, *, is_hidd=False):
        """Reference an audited entry without copying or reparsing its sections."""
        document = record['document']
        kind = self._kind(document, is_hidd)
        filename = PurePosixPath(document).name
        if not filename.endswith('.en.rst'):
            raise ValueError('Invalid AutoDoc output name: ' + document)
        page = filename[:-7]
        qualifier = (parsed.titles.get('LOCATION', '').strip()
                     if is_hidd else '')
        entry = IndexedAutoDoc(record, parsed, kind, page, qualifier)
        self._entries.append(entry)
        self._by_output[document].append(entry)
        self._by_page[(kind, page.casefold())].append(entry)
        self._by_symbol[record['entry'].casefold()].append(entry)
        sources = record.get('sources', (record['source'],))
        for source in dict.fromkeys(sources):
            self._by_source[source].append(entry)
        return entry

    @property
    def entries(self):
        return tuple(self._entries)

    def for_source(self, source):
        return tuple(self._by_source.get(source, ()))

    def for_symbol(self, symbol):
        return tuple(self._by_symbol.get(symbol.casefold(), ()))

    def for_output(self, document):
        return tuple(self._by_output.get(document, ()))

    def pages(self):
        """Deterministic group order; each object appears exactly once."""
        for key in sorted(self._by_page):
            rows = self._by_page[key]
            yield rows[0].kind, rows[0].page, tuple(rows)

    def expected_counts(self):
        """ReST audit's existing Soll counts, indexed by actual output page."""
        return {output: Counter(item.symbol for item in rows)
                for output, rows in self._by_output.items()}

    def repeated_symbols(self):
        """Return possible collisions without rejecting historical valid overloads."""
        result = {}
        for kind, page, rows in self.pages():
            buckets = defaultdict(list)
            for item in rows:
                buckets[(item.symbol.casefold(), item.qualifier.casefold())].append(item)
            for key, items in buckets.items():
                if len(items) > 1:
                    result[(kind, page, *key)] = tuple(items)
        return result
