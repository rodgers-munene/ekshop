from fastapi import APIRouter, File, Form, HTTPException, Depends, UploadFile, status, Query
import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import cast, Numeric, update, delete, func, desc

from app.models.user import User
from app.dependencies.database import get_db
from app.dependencies.auth import get_current_active_user, require_admin
from app.schemas.catalog import (
    CategoryRead,
    CategoryCreate,
    CategoryUpdate,
    ProductRead,
    ProductCreate,
    ProductUpdate,
    ProductStatus,
    ProductListResponse,
    CategoryListResponse,
    ProductImageRead,
    ProductVariantCreate,
    ProductVariantUpdate,
    ProductVariantRead,
    ReviewCreate,
    ReviewRead,
)
from app.models.catalog import Category, Product, ProductImage, ProductVariant, ProductReview
from app.models.shop import Shop
from app.services import storage
from app.services.catalog import with_active_shop

categories_router = APIRouter(prefix="/categories", tags=["categories"])
products_router = APIRouter(prefix="/products", tags=["products"])


def _build_prefix_tsquery(term: str) -> Optional[str]:
    """Turn free-text search input into a tsquery string that AND-matches
    each word and prefix-matches the last one (so live-suggestion typing
    like "run sho" behaves like "run* & sho*")."""
    tokens = re.findall(r"\w+", term)
    if not tokens:
        return None
    tokens[-1] = tokens[-1] + ":*"
    return " & ".join(tokens)

# get all categories and their children
@categories_router.get(
    "/",
    response_model=list[CategoryRead],
    status_code=status.HTTP_200_OK,
    summary="get all top-level categories"
)
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).filter(
        Category.parent_id == None,
        Category.is_active == True
    ).order_by(Category.sort_order).all()
    
    return categories

# get a single category
@categories_router.get(
    "/{category_id}",
    response_model=CategoryRead,
    status_code=status.HTTP_200_OK,
    summary="get a single category"
)
def get_single_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.is_active == True
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found or inactive")

    return category


# admin: list all categories including inactive ones, for management
@categories_router.get(
    "/admin/all",
    response_model=CategoryListResponse,
    summary="List all categories including inactive (admin only)",
)
def list_all_categories(
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(Category).filter(Category.parent_id == None)
    total = query.count()
    skip = (page - 1) * limit
    results = query.order_by(Category.sort_order).offset(skip).limit(limit).all()
    return CategoryListResponse(total=total, page=page, limit=limit, results=results)


# admin: create a category
@categories_router.post(
    "/",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category (admin only)",
)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if db.query(Category).filter(Category.slug == payload.slug).first():
        raise HTTPException(status_code=409, detail="A category with this slug already exists")

    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


# admin: update a category
@categories_router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Update a category (admin only)",
)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


# admin: upload a category's icon image
@categories_router.post(
    "/{category_id}/icon",
    response_model=CategoryRead,
    summary="Upload a category icon image (admin only)",
)
def upload_category_icon(
    category_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    try:
        url = storage.upload_category_icon(
            category_id=category_id,
            filename=file.filename or "icon.jpg",
            content_type=file.content_type or "application/octet-stream",
            data=file.file.read(),
        )
    except storage.StorageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    old_url = category.icon_url
    category.icon_url = url
    db.commit()
    db.refresh(category)

    if old_url:
        storage.delete_category_icon(old_url)

    return category


# admin: delete a category
@categories_router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category (admin only)",
)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()


# PRODUCTS

# seller creates a product
@products_router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Seller creates a product"
)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    shop = db.query(Shop).filter(
        Shop.seller_id == current_user.id
    ).first()
    
    if not shop:
        raise HTTPException(status_code=404, detail="Shop doesn't exist.")
    
    product_data = payload.model_dump(exclude={"variants"})
    product = Product(**product_data, shop_id=shop.id)
    
    db.add(product)
    db.flush() # write to db and generate a product.id before the final commit
    
    if payload.variants:
        for v in payload.variants:
            variant = ProductVariant(**v.model_dump(), product_id=product.id)
            db.add(variant)
            
            
    db.commit()
    db.refresh(product)
    
    return product

# get product with limits and option for filter (Category, count, price, range, search term)
@products_router.get(
    "/",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="get products"
)
def get_products(
    category_id: Optional[uuid.UUID] = None,
    category_slug: Optional[str] = None,
    search: Optional[str] = None,
    q: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    county: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db)
):
    base_query = with_active_shop(
        db.query(Product).filter(Product.status == ProductStatus.active)
    )

    if county:
        base_query = base_query.filter(func.lower(Shop.county) == county.lower())

    if category_slug:
        cat = db.query(Category).filter(Category.slug == category_slug).first()
        if cat:
            child_ids = [c.id for c in (cat.children or [])]
            all_ids = [cat.id] + child_ids
            base_query = base_query.filter(Product.category_id.in_(all_ids))
    elif category_id:
        base_query = base_query.filter(Product.category_id == category_id)

    if min_price:
        base_query = base_query.filter(cast(Product.price, Numeric) >= min_price)

    if max_price:
        base_query = base_query.filter(cast(Product.price, Numeric) <= max_price)

    term = search or q
    relevance = None
    query = base_query

    if term:
        tsquery_str = _build_prefix_tsquery(term)
        if tsquery_str:
            ts_query = func.to_tsquery("english", tsquery_str)
            relevance = func.ts_rank_cd(Product.search_vector, ts_query)
            query = base_query.filter(Product.search_vector.op("@@")(ts_query))
            total = query.count()

            # no word/stem/prefix match at all (likely a typo) -- fall back
            # to trigram similarity instead of showing "no results".
            # word_similarity (vs. similarity) scores how well the query matches
            # the best substring of name, so it isn't diluted by long product titles
            if total == 0:
                name_similarity = func.word_similarity(term, Product.name)
                relevance = name_similarity
                query = base_query.filter(name_similarity > 0.4)
                total = query.count()
        else:
            query = base_query.filter(Product.name.ilike(f"%{term}%"))
            total = query.count()
    else:
        total = query.count()

    skip = (page - 1) * limit

    if relevance is not None:
        query = query.order_by(desc(relevance), Product.popularity.desc(), Product.created_at.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    products = (
        query.options(selectinload(Product.images), selectinload(Product.variants), selectinload(Product.shop))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return ProductListResponse(
        total=total,
        page=page,
        limit=limit,
        results=products
    )
    
# get specific product details
@products_router.get(
    "/{slug}",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
    summary="get the details of a specific product"
)
def get_product_details(slug: str, db: Session = Depends(get_db)):
    product = with_active_shop(
        db.query(Product).filter(Product.slug == slug, Product.status == ProductStatus.active)
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product

# seller updates their product
@products_router.patch(
    "/{slug}",
    response_model=ProductRead,
    summary="Sellers update their product"
)
def update_product(slug: str, payload: ProductUpdate, db: Session= Depends(get_db), current_user: User = Depends(get_current_active_user)):
    shop = db.query(Shop).filter(
        Shop.seller_id == current_user.id
    ).first()
    
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    product = db.query(Product).filter(
        Product.slug == slug,
        Product.shop_id == shop.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_stmt = update(Product).where(
        Product.slug == slug,
        Product.shop_id == shop.id,
    ).values(**payload.model_dump(exclude_unset=True))
    
    db.execute(update_stmt)
    db.commit()
    db.refresh(product)
    
    return product


# delete a product
@products_router.delete(
    "/{slug}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_product(slug: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    shop = db.query(Shop).filter(
        Shop.seller_id == current_user.id
    ).first()
    
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    product = db.query(Product).filter(
        Product.slug == slug,
        Product.shop_id == shop.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    delete_stmt = delete(Product).where(
        Product.slug == slug,
        Product.shop_id == shop.id
    )
    
    db.execute(delete_stmt)
    db.commit()


# Images 

@products_router.post(
    "/{product_id}/images",
    response_model=ProductImageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image to a product",
)
def add_product_image(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    alt_text: Optional[str] = Form(None),
    sort_order: int = Form(0),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop.id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        url = storage.upload_product_image(
            product_id=product.id,
            filename=file.filename or "image.jpg",
            content_type=file.content_type or "application/octet-stream",
            data=file.file.read(),
        )
    except storage.StorageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    image = ProductImage(
        product_id=product.id,
        url=url,
        alt_text=alt_text,
        sort_order=sort_order,
        is_primary=is_primary,
    )
    db.add(image)
    db.commit()
    db.refresh(image)

    return image


@products_router.delete(
    "/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an image from a product",
)
def delete_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    image = db.query(ProductImage).filter(
        ProductImage.id == image_id,
        ProductImage.product_id == product_id,
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # confirm the product belongs to this seller's shop
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop.id,
    ).first()
    if not product:
        raise HTTPException(status_code=403, detail="Not your product")

    storage.delete_product_image(image.url)
    db.delete(image)
    db.commit()


#  Variants 

@products_router.post(
    "/{product_id}/variants",
    response_model=ProductVariantRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a variant to a product",
)
def add_product_variant(
    product_id: uuid.UUID,
    payload: ProductVariantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop.id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant = ProductVariant(**payload.model_dump(), product_id=product.id)
    db.add(variant)
    db.commit()
    db.refresh(variant)

    return variant


@products_router.patch(
    "/{product_id}/variants/{variant_id}",
    response_model=ProductVariantRead,
    summary="Update a product variant",
)
def update_product_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    payload: ProductVariantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop.id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id,
        ProductVariant.product_id == product_id,
    ).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    update_stmt = update(ProductVariant).where(
        ProductVariant.id == variant_id,
    ).values(**payload.model_dump(exclude_unset=True))

    db.execute(update_stmt)
    db.commit()
    db.refresh(variant)

    return variant


#  Reviews 

@products_router.post(
    "/{product_id}/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Leave a review on a product",
)
def create_review(
    product_id: uuid.UUID,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.status == ProductStatus.active,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = db.query(ProductReview).filter(
        ProductReview.product_id == product_id,
        ProductReview.buyer_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this product")

    review = ProductReview(
        **payload.model_dump(),
        product_id=product.id,
        shop_id=product.shop_id,
        buyer_id=current_user.id,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return review


@products_router.get(
    "/{product_id}/reviews",
    response_model=list[ReviewRead],
    status_code=status.HTTP_200_OK,
    summary="Get all reviews for a product",
)
def get_product_reviews(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product.reviews
