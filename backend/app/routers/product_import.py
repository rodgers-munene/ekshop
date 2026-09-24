import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies.auth import require_seller
from app.dependencies.database import get_db
from app.models.catalog import Category
from app.models.product_import import (
    ImportRowStatus,
    ImportStatus,
    ProductImport,
    ProductImportRow,
)
from app.models.shop import Shop
from app.models.user import User
from app.schemas.product_import import (
    ImportCommitRequest,
    ImportCommitResult,
    ImportListResponse,
    ImportPreview,
    ImportRead,
    ImportRowListResponse,
    ImportRowRead,
)
from app.services import product_import as importer

# Deliberately not nested under /products: products_router serves GET
# /products/{slug}, and FastAPI matches in registration order, so a
# /products/imports route would resolve as a product whose slug is "imports"
# depending on which router main.py includes first. A sibling prefix can't be
# broken by reordering.
router = APIRouter(prefix="/product-imports", tags=["product imports"])

# How many rows the review screen gets up front. Enough to show the seller what
# they're getting; the rest are a page away via /rows.
PREVIEW_ROWS = 25

TEMPLATE_HEADERS = ["Code", "Description", "Balance", "SellingPrice", "Brand"]
TEMPLATE_EXAMPLE = ["HP1838", "4 STEP PEDICURE PADDLE", "12", "100.00", "HAIR PRODUCTS"]


def _shop_for(db: Session, user: User) -> Shop:
    shop = db.query(Shop).filter(Shop.seller_id == user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="You don't have a shop yet")
    return shop


def _import_for(db: Session, shop: Shop, import_id: uuid.UUID) -> ProductImport:
    record = (
        db.query(ProductImport)
        .filter(ProductImport.id == import_id, ProductImport.shop_id == shop.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Import not found")
    return record


def _preview(db: Session, record: ProductImport) -> ImportPreview:
    def rows_with(row_status: ImportRowStatus):
        return (
            db.query(ProductImportRow)
            .filter(
                ProductImportRow.import_id == record.id,
                ProductImportRow.status == row_status,
            )
            .order_by(ProductImportRow.row_number.asc())
            .limit(PREVIEW_ROWS)
            .all()
        )

    preview = ImportPreview.model_validate(record)
    preview.sample = [ImportRowRead.model_validate(r) for r in rows_with(ImportRowStatus.valid)]
    preview.problems = [ImportRowRead.model_validate(r) for r in rows_with(ImportRowStatus.invalid)]
    return preview


# Declared before /{import_id} so "template" isn't parsed as a UUID.
@router.get(
    "/template",
    summary="Download the blank bulk-upload spreadsheet",
)
def download_template(_: User = Depends(require_seller)):
    """The headers the importer looks for, so a seller doesn't have to guess.

    Column names are matched case- and spacing-insensitively and by a few
    aliases, so a seller's existing stock export usually imports as-is -- this
    is for the ones starting from scratch.
    """
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Products"
    sheet.append(TEMPLATE_HEADERS)
    sheet.append(TEMPLATE_EXAMPLE)
    for index, header in enumerate(TEMPLATE_HEADERS, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = max(
            14, len(header) + 4
        )

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ekshop-product-template.xlsx"'},
    )


@router.post(
    "",
    response_model=ImportPreview,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a spreadsheet and stage it for review",
)
def create_import(
    file: UploadFile = File(...),
    category_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    """Parse an upload and stage every row. Creates no products.

    The seller reviews the counts this returns, then calls /commit -- which is
    where products actually appear, as drafts.
    """
    shop = _shop_for(db, current_user)

    if category_id is not None:
        exists = db.query(Category.id).filter(Category.id == category_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="That category doesn't exist")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="That file is empty")

    try:
        parsed = importer.parse_workbook(data, file.filename or "")
    except importer.ImportParseError as e:
        raise HTTPException(status_code=422, detail=str(e))

    record = importer.stage_import(
        db, shop, file.filename or "upload.xlsx", parsed, category_id=category_id
    )
    return _preview(db, record)


@router.get(
    "",
    response_model=ImportListResponse,
    summary="List my past imports",
)
def list_imports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    shop = _shop_for(db, current_user)
    query = db.query(ProductImport).filter(ProductImport.shop_id == shop.id)
    total = query.count()
    records = (
        query.order_by(ProductImport.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ImportListResponse(total=total, page=page, limit=limit, results=records)


@router.get(
    "/{import_id}",
    response_model=ImportPreview,
    summary="Progress and counts for one import",
)
def get_import(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    shop = _shop_for(db, current_user)
    return _preview(db, _import_for(db, shop, import_id))


@router.get(
    "/{import_id}/rows",
    response_model=ImportRowListResponse,
    summary="Page through an import's staged rows",
)
def list_import_rows(
    import_id: uuid.UUID,
    row_status: Optional[ImportRowStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    shop = _shop_for(db, current_user)
    record = _import_for(db, shop, import_id)

    query = db.query(ProductImportRow).filter(ProductImportRow.import_id == record.id)
    if row_status:
        query = query.filter(ProductImportRow.status == row_status)

    total = query.count()
    rows = (
        query.order_by(ProductImportRow.row_number.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ImportRowListResponse(total=total, page=page, limit=limit, results=rows)


@router.post(
    "/{import_id}/commit",
    response_model=ImportCommitResult,
    summary="Create the next batch of products from a staged import",
)
def commit_import(
    import_id: uuid.UUID,
    payload: ImportCommitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    """One batch per call. Keep calling while `remaining` is above zero.

    Batched rather than fire-and-forget because there's no job queue here: the
    caller driving the loop gets honest progress, and an interrupted run leaves
    staged rows that a later call picks up rather than a job wedged at
    `processing`.
    """
    shop = _shop_for(db, current_user)
    shop_id = shop.id
    record = _import_for(db, shop, import_id)

    if record.status == ImportStatus.cancelled:
        raise HTTPException(status_code=409, detail="That import was discarded")

    if payload.category_id is not None:
        exists = db.query(Category.id).filter(Category.id == payload.category_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="That category doesn't exist")

    try:
        result = importer.commit_batch(
            db,
            record.id,
            shop,
            on_duplicate=payload.on_duplicate,
            category_id=payload.category_id,
            limit=payload.limit,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Import not found")
    except Exception as e:
        db.rollback()
        # Leave a trail on the import itself: rows that already landed keep their
        # own status, so a retry resumes rather than restarts. Re-query by id
        # rather than reusing `record`, which the rollback has expired.
        failed = (
            db.query(ProductImport)
            .filter(ProductImport.id == import_id, ProductImport.shop_id == shop_id)
            .first()
        )
        if failed is not None:
            failed.status = ImportStatus.failed
            failed.error_message = str(e)[:2000]
            db.commit()
        raise HTTPException(status_code=500, detail="That batch failed. Try again to resume.")

    return ImportCommitResult(
        status=result.status,
        processed=result.processed,
        remaining=result.remaining,
        created_count=result.created,
        updated_count=result.updated,
        skipped_count=result.skipped,
        failed_count=result.failed,
    )


@router.delete(
    "/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Discard a staged import",
)
def delete_import(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    """Throws away the staged rows. Products already created are left alone --
    they're ordinary drafts by now, and the seller deletes those from the
    products page like any other."""
    shop = _shop_for(db, current_user)
    record = _import_for(db, shop, import_id)
    db.delete(record)
    db.commit()
