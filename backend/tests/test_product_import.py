"""Tests for the bulk product importer's parsing layer.

Everything here runs against an in-memory workbook and pure functions -- no
database. That is deliberate: the parser is the part that decides whether a
seller's spreadsheet is understood, and it is decidable from its inputs alone.
The commit path is not tested here because it exists to write rows, and faking
the session would only assert that the fake was called.
"""
import io
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.services.catalog import _next_free, slugify
from app.services.product_import import (
    MAX_PRICE,
    MAX_ROWS,
    ImportParseError,
    _parse_price,
    _parse_stock,
    parse_workbook,
)

SAMPLE = Path(__file__).resolve().parents[1] / "docs" / "Shemaeys Beauty Stock.xlsx"

# The sample's own header row, which is what the aliases were built from.
SHEET_HEADERS = ["Code", "Description", "Balance", "SellingPrice", "BalSellValue", "Brand"]


def workbook_bytes(header, *rows) -> bytes:
    """A .xlsx in memory, with every cell written as a string.

    The real export stores even balances and prices as text, so writing proper
    numbers here would test a file shape no seller actually sends.
    """
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(list(header))
    for row in rows:
        sheet.append(["" if cell is None else str(cell) for cell in row])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def parse_one(header, row):
    parsed = parse_workbook(workbook_bytes(header, row), "test.xlsx")
    assert len(parsed) == 1
    return parsed[0]


# --- header matching -------------------------------------------------------


def test_reads_the_sample_headers():
    row = parse_one(SHEET_HEADERS, ["HP1838", "4 STEP PEDICURE PADDLE", "12", "100.00", "1200", "HAIR PRODUCTS"])
    assert row.is_valid
    assert row.sku == "HP1838"
    assert row.name == "4 STEP PEDICURE PADDLE"
    assert row.stock_qty == 12
    assert row.price == "100.00"
    assert row.brand == "HAIR PRODUCTS"


def test_column_order_does_not_matter():
    """Columns are found by name, so a reordered export still imports."""
    row = parse_one(
        ["Brand", "SellingPrice", "Code", "Balance", "Description"],
        ["NIVEA", "250", "X1", "3", "BODY LOTION"],
    )
    assert row.is_valid
    assert (row.sku, row.name, row.price, row.stock_qty, row.brand) == (
        "X1",
        "BODY LOTION",
        "250.00",
        3,
        "NIVEA",
    )


@pytest.mark.parametrize(
    "headers",
    [
        ["SKU", "Product Name", "Qty", "Price"],
        ["item code", "ITEM NAME", "On Hand", "Unit Price"],
        ["Barcode", "Details", "closing balance", "Retail Price"],
    ],
)
def test_alias_headers_are_accepted(headers):
    """Case, spacing and wording vary between accounting exports."""
    row = parse_one(headers, ["A1", "SHEA BUTTER", "5", "400"])
    assert row.is_valid, row.error
    assert row.name == "SHEA BUTTER"
    assert row.price == "400.00"
    assert row.stock_qty == 5


def test_missing_name_column_rejects_the_whole_file():
    with pytest.raises(ImportParseError) as exc:
        parse_workbook(workbook_bytes(["Code", "SellingPrice"], ["A1", "100"]), "test.xlsx")
    assert "name" in str(exc.value).lower()


def test_missing_price_column_rejects_the_whole_file():
    with pytest.raises(ImportParseError):
        parse_workbook(workbook_bytes(["Code", "Description"], ["A1", "SOAP"]), "test.xlsx")


def test_empty_sheet_is_rejected():
    with pytest.raises(ImportParseError):
        parse_workbook(workbook_bytes(SHEET_HEADERS), "test.xlsx")


def test_a_file_that_is_not_a_workbook_is_rejected():
    with pytest.raises(ImportParseError):
        parse_workbook(b"Code,Description\nA1,SOAP\n", "stock.csv")


# --- stock -----------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("12", 12),
        ("0.00000", 0),
        ("", 0),
        (None, 0),
        # 7 rows of the sample are half-packs of hair extensions. Truncating is
        # the safe direction: rounding up would let a buyer order a pack that
        # isn't there.
        ("0.50000", 0),
        ("1.90000", 1),
        # 54 rows of the sample are negative -- a stocktake artefact, not
        # something to fail a product over.
        ("-4", 0),
        ("1,250", 1250),
        ("not a number", 0),
    ],
)
def test_stock_parsing(value, expected):
    assert _parse_stock(value) == expected


def test_a_bad_balance_never_fails_the_row():
    row = parse_one(SHEET_HEADERS, ["A1", "SOAP", "rubbish", "100", "", "NIVEA"])
    assert row.is_valid
    assert row.stock_qty == 0


# --- price -----------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("100", "100.00"),
        ("100.5", "100.50"),
        ("26000.00000", "26000.00"),
        ("1,250.00", "1250.00"),
        ("KES 300", "300.00"),
        ("Ksh 300", "300.00"),
        # 2dp is what Product.price stores, so a third decimal is quantized
        # rather than carried into the column.
        ("19.999", "20.00"),
    ],
)
def test_price_parsing(value, expected):
    price, error = _parse_price(value)
    assert error is None
    assert price == expected


@pytest.mark.parametrize("value", ["0", "0.00", "-5", "", None, "free", str(MAX_PRICE + 1)])
def test_unusable_prices_are_rejected(value):
    price, error = _parse_price(value)
    assert price is None
    assert error


def test_a_zero_price_marks_the_row_invalid_without_stopping_the_file():
    parsed = parse_workbook(
        workbook_bytes(
            SHEET_HEADERS,
            ["A1", "GOOD ONE", "1", "100", "", "NIVEA"],
            ["A2", "NO PRICE", "1", "0", "", "NIVEA"],
            ["A3", "ALSO GOOD", "1", "200", "", "NIVEA"],
        ),
        "test.xlsx",
    )
    assert [r.is_valid for r in parsed] == [True, False, True]
    assert parsed[1].error


# --- rows ------------------------------------------------------------------


def test_row_numbers_match_the_spreadsheet():
    """A rejection has to be findable, so row 1 is the header and data starts at 2."""
    parsed = parse_workbook(
        workbook_bytes(
            SHEET_HEADERS,
            ["A1", "FIRST", "1", "100", "", ""],
            ["A2", "SECOND", "1", "100", "", ""],
        ),
        "test.xlsx",
    )
    assert [r.row_number for r in parsed] == [2, 3]


def test_blank_rows_are_dropped_rather_than_reported():
    """Trailing blank rows are an artefact of how the file was saved, not an
    error the seller should have to look at."""
    parsed = parse_workbook(
        workbook_bytes(
            SHEET_HEADERS,
            ["A1", "REAL", "1", "100", "", ""],
            ["", "", "", "", "", ""],
            [None, None, None, None, None, None],
        ),
        "test.xlsx",
    )
    assert len(parsed) == 1
    assert parsed[0].name == "REAL"


def test_a_row_with_no_name_is_invalid():
    row = parse_one(SHEET_HEADERS, ["A1", "", "1", "100", "", "NIVEA"])
    assert not row.is_valid
    assert row.error


def test_the_raw_cells_are_kept_for_rows_that_failed():
    """A row that didn't parse has nothing in the typed columns, so `raw` is the
    only record of what the seller actually sent."""
    row = parse_one(SHEET_HEADERS, ["A1", "SOAP", "1", "nonsense", "", "NIVEA"])
    assert not row.is_valid
    assert "nonsense" in str(row.raw.values())


def test_long_cells_are_truncated_to_the_column_widths():
    """An overlong cell would otherwise abort the whole batch on insert."""
    row = parse_one(
        SHEET_HEADERS,
        ["S" * 200, "N" * 400, "1", "100", "", "B" * 400],
    )
    assert row.is_valid
    assert len(row.sku) <= 100
    assert len(row.name) <= 255
    assert len(row.brand) <= 255


def test_too_many_rows_is_rejected_as_a_whole():
    header = ["Description", "SellingPrice"]
    rows = [[f"ITEM {i}", "100"] for i in range(MAX_ROWS + 1)]
    with pytest.raises(ImportParseError) as exc:
        parse_workbook(workbook_bytes(header, *rows), "big.xlsx")
    assert f"{MAX_ROWS:,}" in str(exc.value)


# --- slugs -----------------------------------------------------------------


def test_duplicate_names_get_distinct_slugs():
    """Slugs are unique per shop, and a stock export repeats names freely."""
    taken = set()
    slugs = []
    for _ in range(3):
        slug = _next_free(slugify("BODY LOTION"), taken)
        taken.add(slug)
        slugs.append(slug)
    assert slugs == ["body-lotion", "body-lotion-2", "body-lotion-3"]


def test_a_name_with_no_usable_characters_still_yields_a_slug():
    assert slugify("!!!") == "product"


# --- the real file ---------------------------------------------------------


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample spreadsheet not checked in")
def test_the_real_export_parses_cleanly():
    """The file this feature was built for, as-is."""
    parsed = parse_workbook(SAMPLE.read_bytes(), SAMPLE.name)

    assert len(parsed) == 9608
    assert all(row.is_valid for row in parsed), [r.error for r in parsed if not r.is_valid][:5]

    # Codes are the dedupe key, so a duplicate in the source would silently
    # collapse two products into one.
    skus = [row.sku for row in parsed]
    assert len(set(skus)) == len(skus)

    # Prices land in Product.price's column as 2dp strings.
    assert all(Decimal(row.price) > 0 for row in parsed)
    assert all(row.price == str(Decimal(row.price).quantize(Decimal("0.01"))) for row in parsed)

    # Most of a stock export is out of stock, which is exactly why the review
    # screen filters on it rather than the importer skipping those rows.
    in_stock = sum(1 for row in parsed if row.stock_qty > 0)
    assert 0 < in_stock < len(parsed)
