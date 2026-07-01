from fastapi import APIRouter, HTTPException, Depends, status, Query
import uuid
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import cast, Numeric, update, delete

from app.models.user import User
from app.dependencies.database import get_db
from app.dependencies.auth import get_current_active_user
from app.schemas.catalog import (
    CategoryRead,
    ProductRead,
    ProductCreate,
    ProductUpdate,
    ProductStatus,
    ProductListResponse,
    ProductImageCreate,
    ProductImageRead,
    ProductVariantCreate,
    ProductVariantUpdate,
    ProductVariantRead,
    ReviewCreate,
    ReviewRead,
)
from app.models.catalog import Category, Product, ProductImage, ProductVariant, ProductReview
from app.models.shop import Shop

categories_router = APIRouter(prefix="/categories", tags=["categories"])
products_router = APIRouter(prefix="/products", tags=["products"])

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
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(
        Product.status == ProductStatus.active
    )
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
        
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    
    if min_price:
        query = query.filter(cast(Product.price, Numeric) >= min_price)
        
    if max_price:
        query = query.filter(cast(Product.price, Numeric) <= max_price)
        
        
    total = query.count()
    skip = (page - 1) * limit
    
    products = query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()
    
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
    product = db.query(Product).filter(
        Product.slug == slug
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
    summary="Add an image to a product",
)
def add_product_image(
    product_id: uuid.UUID,
    payload: ProductImageCreate,
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

    image = ProductImage(**payload.model_dump(), product_id=product.id)
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
