from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.providers import (
    LocalPdfInvoiceProvider,
    LocalDocumentClassifier,
    LocalBarcodeDecoder,
    LocalProductImageOcr,
    LocalVisualRecognition,
    LocalLabReportProvider,
    ProviderNotConfigured,
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://central:central@localhost:5432/central_product")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
ALLOWED_UPLOAD_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
invoice_provider = LocalPdfInvoiceProvider()
document_classifier = LocalDocumentClassifier()
barcode_decoder = LocalBarcodeDecoder()
product_image_ocr = LocalProductImageOcr()
visual_recognition = LocalVisualRecognition()
lab_report_provider = LocalLabReportProvider()


class Base(DeclarativeBase):
    pass


class ApiClient(Base):
    __tablename__ = "api_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    secret_hash: Mapped[str] = mapped_column(String(256))
    token_hash: Mapped[Optional[str]] = mapped_column(String(256), unique=True, nullable=True, index=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sku: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(255), default="")
    sub_category: Mapped[str] = mapped_column(String(255), default="")
    barcode: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    hsn: Mapped[str] = mapped_column(String(64), default="")
    gst_rate: Mapped[float] = mapped_column(Float, default=0)
    mrp: Mapped[float] = mapped_column(Float, default=0)
    selling_price: Mapped[float] = mapped_column(Float, default=0)
    purchase_price: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(64), default="")
    pack_size: Mapped[str] = mapped_column(String(64), default="")
    weight: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    available_stock: Mapped[int] = mapped_column(Integer, default=0)
    batch_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    manufacturing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    license_certificate_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ingredients_attributes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    product_box_image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    logo: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    primary_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    secondary_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    custom_fields: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource: Mapped[str] = mapped_column(String(255), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class InventoryReceipt(Base):
    __tablename__ = "inventory_receipts"
    __table_args__ = (UniqueConstraint("source_reference", name="uq_inventory_receipt_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="approved")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProductSuggestion(Base):
    __tablename__ = "product_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sku: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(255), default="")
    sub_category: Mapped[str] = mapped_column(String(255), default="")
    barcode: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    hsn: Mapped[str] = mapped_column(String(64), default="")
    gst_rate: Mapped[float] = mapped_column(Float, default=0)
    mrp: Mapped[float] = mapped_column(Float, default=0)
    selling_price: Mapped[float] = mapped_column(Float, default=0)
    purchase_price: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(64), default="")
    pack_size: Mapped[str] = mapped_column(String(64), default="")
    weight: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    batch_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    manufacturing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    license_certificate_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ingredients_attributes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    product_box_image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    logo: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    primary_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    secondary_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    custom_fields: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_reference: Mapped[str] = mapped_column(String(255), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, approved, rejected
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(engine)
app = FastAPI(title="Central AI OCR & Product Intelligence API", version="0.2.0")
security = HTTPBearer(auto_error=False)


class TokenRequest(BaseModel):
    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)


class ProductCreate(BaseModel):
    product_id: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    brand: str = ""
    category: str = ""
    sub_category: str = ""
    barcode: Optional[str] = None
    hsn: str = ""
    gst_rate: float = Field(default=0, ge=0, le=100)
    mrp: float = Field(default=0, ge=0)
    selling_price: float = Field(default=0, ge=0)
    purchase_price: float = Field(default=0, ge=0)
    unit: str = ""
    pack_size: str = ""
    weight: str = ""
    description: str = ""
    available_stock: int = Field(default=0, ge=0)
    batch_number: Optional[str] = None
    manufacturing_date: Optional[date] = None
    expiry_date: Optional[date] = None
    serial_number: Optional[str] = None
    license_certificate_info: Optional[str] = None
    ingredients_attributes: Optional[str] = None
    product_image: Optional[str] = None
    product_box_image: Optional[str] = None
    logo: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    custom_fields: Optional[str] = None


class ProductOut(ProductCreate):
    id: int
    model_config = {"from_attributes": True}


class ProductSuggestionBase(BaseModel):
    product_id: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    brand: str = ""
    category: str = ""
    sub_category: str = ""
    barcode: Optional[str] = None
    hsn: str = ""
    gst_rate: float = Field(default=0, ge=0, le=100)
    mrp: float = Field(default=0, ge=0)
    selling_price: float = Field(default=0, ge=0)
    purchase_price: float = Field(default=0, ge=0)
    unit: str = ""
    pack_size: str = ""
    weight: str = ""
    description: str = ""
    batch_number: Optional[str] = None
    manufacturing_date: Optional[date] = None
    expiry_date: Optional[date] = None
    serial_number: Optional[str] = None
    license_certificate_info: Optional[str] = None
    ingredients_attributes: Optional[str] = None
    product_image: Optional[str] = None
    product_box_image: Optional[str] = None
    logo: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    custom_fields: Optional[str] = None
    source_reference: str = ""
    confidence: float = Field(default=0, ge=0, le=100)


class ProductSuggestionCreate(ProductSuggestionBase):
    pass


class ProductSuggestionOut(ProductSuggestionBase):
    id: int
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ProductSuggestionReview(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    reviewed_by: str = Field(min_length=1)


class MatchRequest(BaseModel):
    barcode: Optional[str] = None
    sku: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    pack_size: Optional[str] = None
    weight: Optional[str] = None


class InventorySyncRequest(BaseModel):
    product_id: str = Field(min_length=1)
    quantity_delta: int
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    source_reference: str = ""


class InvoiceLineInput(BaseModel):
    barcode: Optional[str] = None
    sku: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    pack_size: Optional[str] = None
    weight: Optional[str] = None
    quantity: float = Field(gt=0)
    purchase_price: Optional[float] = Field(default=None, ge=0)
    gst_rate: Optional[float] = Field(default=None, ge=0, le=100)
    hsn: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None


class InvoiceProcessRequest(BaseModel):
    source_reference: str = Field(min_length=1, max_length=255)
    lines: list[InvoiceLineInput] = Field(min_length=1)
    approve: bool = False


class InvoiceProcessResponse(BaseModel):
    success: bool
    sourceReference: str
    status: str
    updatedProducts: list[BillingResponse] = []
    reviewReasons: list[str] = []


class BillingResponse(BaseModel):
    success: bool
    productId: str
    productName: str
    barcode: Optional[str]
    batchNo: Optional[str]
    expiryDate: Optional[date]
    mrp: float
    sellingPrice: float
    gstRate: float
    hsn: str
    availableStock: int
    confidence: float
    requiresReview: bool = False


class ExtractedField(BaseModel):
    value: object
    confidence: float = Field(ge=0, le=100)
    source: str


class InvoiceExtraction(BaseModel):
    success: bool
    documentType: str
    filename: str
    pageCount: int
    invoiceNumber: Optional[ExtractedField] = None
    invoiceDate: Optional[ExtractedField] = None
    vendorName: Optional[ExtractedField] = None
    vendorAddress: Optional[ExtractedField] = None
    vendorGstin: Optional[ExtractedField] = None
    fssaiNumber: Optional[ExtractedField] = None
    taxableValue: Optional[ExtractedField] = None
    totalAmount: Optional[ExtractedField] = None
    cgst: Optional[ExtractedField] = None
    sgst: Optional[ExtractedField] = None
    igst: Optional[ExtractedField] = None
    lines: list[dict] = []
    warnings: list[str] = []
    requiresReview: bool = False


class DocumentClassification(BaseModel):
    success: bool
    documentType: str
    filename: str
    confidence: float
    source: str
    allScores: Optional[dict] = None
    suggestedTypes: Optional[list[str]] = None
    requiresReview: bool = False


class BarcodeDecodeResponse(BaseModel):
    success: bool
    filename: str
    barcodes: list[dict] = []
    message: Optional[str] = None


class ProductImageOcrResponse(BaseModel):
    success: bool
    documentType: str
    filename: str
    fields: dict
    rawText: Optional[str] = None
    requiresReview: bool = False


class VisualComparisonResponse(BaseModel):
    success: bool
    similarity: float
    hash1: str
    hash2: str
    difference: int
    match: bool
    confidence: float


class LabReportExtraction(BaseModel):
    success: bool
    documentType: str
    filename: str
    fields: dict
    requiresReview: bool = False


class ProductAnalyzeResponse(BaseModel):
    success: bool
    filename: str
    documentType: str
    barcodeResult: Optional[BarcodeDecodeResponse] = None
    ocrResult: Optional[ProductImageOcrResponse] = None
    visualMatch: Optional[VisualComparisonResponse] = None
    matchedProduct: Optional[BillingResponse] = None
    confidence: float
    requiresReview: bool = False


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def norm(value: Optional[str]) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def current_client(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Bearer token required")
    with Session(engine) as session:
        client = session.scalar(select(ApiClient).where(ApiClient.token_hash == hash_secret(credentials.credentials), ApiClient.active.is_(True)))
    if not client:
        raise HTTPException(401, "Invalid or inactive token")
    return client.client_id


def audit(session: Session, client_id: str, action: str, resource: str, detail: str = "") -> None:
    session.add(AuditLog(client_id=client_id, action=action, resource=resource, detail=detail))


def billing_response(product: Product, confidence: float) -> BillingResponse:
    return BillingResponse(
        success=True, productId=product.product_id, productName=product.product_name,
        barcode=product.barcode, batchNo=product.batch_number, expiryDate=product.expiry_date,
        mrp=product.mrp, sellingPrice=product.selling_price, gstRate=product.gst_rate,
        hsn=product.hsn, availableStock=product.available_stock,
        confidence=round(confidence, 2), requiresReview=confidence < 80,
    )


def match_score(product: Product, request: MatchRequest) -> float:
    if request.barcode and product.barcode and norm(request.barcode) == norm(product.barcode):
        return 100.0
    score = 0.0
    for supplied, stored, weight in ((request.sku, product.sku, 35), (request.product_name, product.product_name, 30), (request.brand, product.brand, 15), (request.pack_size, product.pack_size, 10), (request.weight, product.weight, 10)):
        if supplied and norm(supplied) == norm(stored):
            score += weight
        elif supplied and norm(supplied) in norm(stored) and weight <= 30:
            score += weight * 0.66
    return min(score, 99.9)


def find_product(session: Session, line: InvoiceLineInput) -> tuple[Product | None, float]:
    if line.barcode:
        product = session.scalar(select(Product).where(Product.barcode == line.barcode))
        if product:
            return product, 100.0
    request = MatchRequest(**line.model_dump(exclude={"quantity", "purchase_price", "gst_rate", "hsn", "batch_number", "expiry_date"}))
    ranked = sorted(((match_score(item, request), item) for item in session.scalars(select(Product))), key=lambda pair: pair[0], reverse=True)
    return (ranked[0][1], ranked[0][0]) if ranked else (None, 0.0)


@app.get("/")
def root():
    return {"name": app.title, "version": app.version, "status": "running"}


@app.get("/health")
def health():
    try:
        with Session(engine) as session:
            session.execute(select(1))
        return {"status": "ok", "database": "postgresql"}
    except Exception:
        raise HTTPException(503, "Database unavailable")


@app.post("/api/auth/token")
def token(request: TokenRequest):
    with Session(engine) as session:
        client = session.scalar(select(ApiClient).where(ApiClient.client_id == request.client_id, ApiClient.active.is_(True)))
        if not client or not hmac.compare_digest(client.secret_hash, hash_secret(request.client_secret)):
            raise HTTPException(401, "Invalid client credentials")
        access_token = secrets.token_urlsafe(32)
        client.token_hash = hash_secret(access_token)
        audit(session, client.client_id, "auth.token", client.client_id)
        session.commit()
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/product", response_model=ProductOut)
def create_product(product: ProductCreate, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        products = list(session.scalars(select(Product)))
        duplicate = next((item for item in products if (product.barcode and item.barcode and norm(product.barcode) == norm(item.barcode)) or norm(product.sku) == norm(item.sku) or (norm(product.product_name) == norm(item.product_name) and norm(product.brand) == norm(item.brand) and norm(product.pack_size) == norm(item.pack_size))), None)
        if duplicate:
            raise HTTPException(409, f"Possible duplicate product: {duplicate.product_id}")
        row = Product(**product.model_dump())
        session.add(row)
        audit(session, client_id, "product.create", product.product_id)
        session.commit()
        session.refresh(row)
        return row


@app.get("/api/products", response_model=list[ProductOut])
def list_products(client_id: str = Depends(current_client)):
    with Session(engine) as session:
        audit(session, client_id, "product.list", "products")
        session.commit()
        return list(session.scalars(select(Product).order_by(Product.id.desc())))


@app.get("/api/product/barcode/{barcode}", response_model=BillingResponse)
def barcode_lookup(barcode: str, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        product = session.scalar(select(Product).where(Product.barcode == barcode))
        if not product:
            raise HTTPException(404, "Product not found")
        audit(session, client_id, "product.barcode_lookup", product.product_id, barcode)
        session.commit()
        return billing_response(product, 100.0)


@app.post("/api/product/match", response_model=BillingResponse)
def match_product(request: MatchRequest, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        ranked = sorted(((match_score(item, request), item) for item in session.scalars(select(Product))), key=lambda item: item[0], reverse=True)
        if not ranked or ranked[0][0] < 30:
            raise HTTPException(404, "No sufficiently confident product match")
        score, product = ranked[0]
        audit(session, client_id, "product.match", product.product_id, f"confidence={score}")
        session.commit()
        return billing_response(product, score)


@app.post("/api/inventory/sync", response_model=BillingResponse)
def inventory_sync(request: InventorySyncRequest, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        product = session.scalar(select(Product).where(Product.product_id == request.product_id))
        if not product:
            raise HTTPException(404, "Product not found")
        if product.available_stock + request.quantity_delta < 0:
            raise HTTPException(409, "Inventory cannot become negative")
        product.available_stock += request.quantity_delta
        if request.batch_number is not None:
            product.batch_number = request.batch_number
        if request.expiry_date is not None:
            product.expiry_date = request.expiry_date
        audit(session, client_id, "inventory.sync", product.product_id, request.source_reference)
        session.commit()
        return billing_response(product, 100.0)


@app.post("/api/invoice/process", response_model=InvoiceProcessResponse)
def process_invoice(request: InvoiceProcessRequest, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        existing = session.scalar(select(InventoryReceipt).where(InventoryReceipt.source_reference == request.source_reference))
        if existing and (existing.status == "approved" or not request.approve):
            return InvoiceProcessResponse(success=True, sourceReference=request.source_reference, status=existing.status)

        review_reasons: list[str] = []
        matches: list[tuple[InvoiceLineInput, Product, float]] = []
        for index, line in enumerate(request.lines, start=1):
            product, confidence = find_product(session, line)
            if not product or confidence < 80:
                review_reasons.append(f"line {index}: product match requires review")
                continue
            if line.gst_rate is not None and abs(product.gst_rate - line.gst_rate) > 0.01:
                review_reasons.append(f"line {index}: GST mismatch with product master")
            if line.hsn and product.hsn and line.hsn != product.hsn:
                review_reasons.append(f"line {index}: HSN mismatch with product master")
            matches.append((line, product, confidence))

        if review_reasons or not request.approve:
            status = "review_required"
            if not review_reasons and not request.approve:
                review_reasons.append("approval is required before inventory is changed")
            if existing:
                existing.status = status
                existing.detail = "; ".join(review_reasons)
            else:
                session.add(InventoryReceipt(source_reference=request.source_reference, status=status, detail="; ".join(review_reasons)))
            audit(session, client_id, "invoice.review", request.source_reference, "; ".join(review_reasons))
            session.commit()
            return InvoiceProcessResponse(success=False, sourceReference=request.source_reference, status=status, reviewReasons=review_reasons)

        updated: list[BillingResponse] = []
        for line, product, confidence in matches:
            product.available_stock += int(line.quantity)
            if line.batch_number is not None:
                product.batch_number = line.batch_number
            if line.expiry_date is not None:
                product.expiry_date = line.expiry_date
            if line.purchase_price is not None:
                product.purchase_price = line.purchase_price
            updated.append(billing_response(product, confidence))
        if existing:
            existing.status = "approved"
            existing.detail = f"updated={len(updated)}"
        else:
            session.add(InventoryReceipt(source_reference=request.source_reference, status="approved", detail=f"updated={len(updated)}"))
        audit(session, client_id, "invoice.approve", request.source_reference, f"updated={len(updated)}")
        session.commit()
        return InvoiceProcessResponse(success=True, sourceReference=request.source_reference, status="approved", updatedProducts=updated)


@app.get("/api/billing/product/{product_id}", response_model=BillingResponse)
def billing_product(product_id: str, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        product = session.scalar(select(Product).where(Product.product_id == product_id))
        if not product:
            raise HTTPException(404, "Product not found")
        audit(session, client_id, "billing.product", product.product_id)
        session.commit()
        return billing_response(product, 100.0)


@app.post("/api/product/suggestion", response_model=ProductSuggestionOut)
def create_product_suggestion(suggestion: ProductSuggestionCreate, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        # Check for duplicates in both products and suggestions
        duplicate = session.scalar(
            select(Product).where(
                (Product.barcode == suggestion.barcode) if suggestion.barcode else False
            )
        )
        if duplicate:
            raise HTTPException(409, f"Product with barcode already exists: {duplicate.product_id}")
        
        duplicate_suggestion = session.scalar(
            select(ProductSuggestion).where(
                (ProductSuggestion.barcode == suggestion.barcode) if suggestion.barcode else False
            )
        )
        if duplicate_suggestion:
            raise HTTPException(409, f"Suggestion with barcode already exists: {duplicate_suggestion.product_id}")
        
        row = ProductSuggestion(**suggestion.model_dump())
        session.add(row)
        audit(session, client_id, "product.suggestion.create", suggestion.product_id, suggestion.source_reference)
        session.commit()
        session.refresh(row)
        return row


@app.get("/api/product/suggestions", response_model=list[ProductSuggestionOut])
def list_product_suggestions(status: Optional[str] = None, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        query = select(ProductSuggestion).order_by(ProductSuggestion.created_at.desc())
        if status:
            query = query.where(ProductSuggestion.status == status)
        audit(session, client_id, "product.suggestion.list", "product_suggestions")
        return list(session.scalars(query))


@app.get("/api/product/suggestion/{suggestion_id}", response_model=ProductSuggestionOut)
def get_product_suggestion(suggestion_id: int, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        suggestion = session.scalar(select(ProductSuggestion).where(ProductSuggestion.id == suggestion_id))
        if not suggestion:
            raise HTTPException(404, "Product suggestion not found")
        audit(session, client_id, "product.suggestion.get", suggestion.product_id)
        return suggestion


@app.post("/api/product/suggestion/{suggestion_id}/review", response_model=ProductSuggestionOut)
def review_product_suggestion(suggestion_id: int, review: ProductSuggestionReview, client_id: str = Depends(current_client)):
    with Session(engine) as session:
        suggestion = session.scalar(select(ProductSuggestion).where(ProductSuggestion.id == suggestion_id))
        if not suggestion:
            raise HTTPException(404, "Product suggestion not found")
        
        if suggestion.status != "pending":
            raise HTTPException(400, f"Suggestion already {suggestion.status}")
        
        if review.action == "approve":
            # Create the actual product from the suggestion
            product_data = suggestion.__dict__.copy()
            product_data.pop("id", None)
            product_data.pop("status", None)
            product_data.pop("reviewed_by", None)
            product_data.pop("reviewed_at", None)
            product_data.pop("source_reference", None)
            product_data.pop("confidence", None)
            product_data.pop("created_at", None)
            product_data.pop("_sa_instance_state", None)
            
            product = Product(**product_data)
            session.add(product)
            suggestion.status = "approved"
            suggestion.reviewed_by = review.reviewed_by
            suggestion.reviewed_at = datetime.now(timezone.utc)
            audit(session, client_id, "product.suggestion.approve", suggestion.product_id, f"created product {product.product_id}")
        else:
            suggestion.status = "rejected"
            suggestion.reviewed_by = review.reviewed_by
            suggestion.reviewed_at = datetime.now(timezone.utc)
            audit(session, client_id, "product.suggestion.reject", suggestion.product_id)
        
        session.commit()
        session.refresh(suggestion)
        return suggestion


async def read_upload(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(415, "Unsupported file type; upload PDF, JPEG, PNG, or WebP")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES} byte upload limit")
    if not content:
        raise HTTPException(400, "Uploaded file is empty")
    return content


@app.post("/api/ocr/invoice", response_model=InvoiceExtraction)
async def invoice_ocr(file: UploadFile = File(...), client_id: str = Depends(current_client)):
    content = await read_upload(file)
    try:
        result = invoice_provider.extract_invoice(content, file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    with Session(engine) as session:
        audit(session, client_id, "ocr.invoice", file.filename or "upload", f"bytes={len(content)}")
        session.commit()
    return result


@app.post("/api/document/classify", response_model=DocumentClassification)
async def classify_document(file: UploadFile = File(...), client_id: str = Depends(current_client)):
    content = await read_upload(file)
    try:
        result = document_classifier.classify(content, file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    with Session(engine) as session:
        audit(session, client_id, "document.classify", file.filename or "upload", f"bytes={len(content)}")
        session.commit()
    return result


@app.post("/api/barcode/decode", response_model=BarcodeDecodeResponse)
async def decode_barcode(file: UploadFile = File(...), client_id: str = Depends(current_client)):
    content = await read_upload(file)
    try:
        result = barcode_decoder.decode(content, file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    with Session(engine) as session:
        audit(session, client_id, "barcode.decode", file.filename or "upload", f"bytes={len(content)}")
        session.commit()
    return result


@app.post("/api/ocr/product", response_model=ProductImageOcrResponse)
async def product_ocr(file: UploadFile = File(...), client_id: str = Depends(current_client)):
    content = await read_upload(file)
    try:
        result = product_image_ocr.extract(content, file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    with Session(engine) as session:
        audit(session, client_id, "ocr.product", file.filename or "upload", f"bytes={len(content)}")
        session.commit()
    return result


@app.post("/api/visual/compare", response_model=VisualComparisonResponse)
async def compare_visual(file: UploadFile = File(...), reference: UploadFile = File(...), client_id: str = Depends(current_client)):
    content = await read_upload(file)
    reference_content = await read_upload(reference)
    try:
        result = visual_recognition.compare(content, reference_content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    with Session(engine) as session:
        audit(session, client_id, "visual.compare", file.filename or "upload", f"bytes={len(content)}")
        session.commit()
    return result


@app.post("/api/document/lab-report", response_model=LabReportExtraction)
async def lab_report_ocr(file: UploadFile = File(...), client_id: str = Depends(current_client)):
    content = await read_upload(file)
    try:
        result = lab_report_provider.extract_lab_report(content, file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    with Session(engine) as session:
        audit(session, client_id, "ocr.lab_report", file.filename or "upload", f"bytes={len(content)}")
        session.commit()
    return result


@app.post("/api/product/analyze", response_model=ProductAnalyzeResponse)
async def analyze_product(file: UploadFile = File(...), reference: UploadFile | None = File(None), client_id: str = Depends(current_client)):
    content = await read_upload(file)
    
    # First classify the document
    classification = document_classifier.classify(content, file.filename or "upload")
    
    # Try barcode decoding
    barcode_result = None
    try:
        barcode_data = barcode_decoder.decode(content, file.filename or "upload")
        barcode_result = BarcodeDecodeResponse(**barcode_data)
    except NotImplementedError:
        pass
    except Exception:
        pass
    
    # Try OCR
    ocr_result = None
    try:
        ocr_data = product_image_ocr.extract(content, file.filename or "upload")
        ocr_result = ProductImageOcrResponse(**ocr_data)
    except NotImplementedError:
        pass
    except Exception:
        pass
    
    # Try visual comparison if reference provided
    visual_match = None
    if reference:
        reference_content = await read_upload(reference)
        try:
            visual_data = visual_recognition.compare(content, reference_content)
            visual_match = VisualComparisonResponse(**visual_data)
        except NotImplementedError:
            pass
        except Exception:
            pass
    
    # Try to match with product master
    matched_product = None
    best_confidence = 0.0
    
    # If barcode found, try exact match
    if barcode_result and barcode_result.barcodes:
        barcode_value = barcode_result.barcodes[0].get("data")
        if barcode_value:
            with Session(engine) as session:
                product = session.scalar(select(Product).where(Product.barcode == barcode_value))
                if product:
                    matched_product = billing_response(product, 100.0)
                    best_confidence = 100.0
    
    # If no barcode match, try OCR fields
    if not matched_product and ocr_result and ocr_result.fields:
        fields = ocr_result.fields
        request = MatchRequest(
            barcode=fields.get("barcode", {}).get("value") if isinstance(fields.get("barcode"), dict) else None,
            sku=fields.get("sku", {}).get("value") if isinstance(fields.get("sku"), dict) else None,
            product_name=fields.get("product_name", {}).get("value") if isinstance(fields.get("product_name"), dict) else None,
            brand=fields.get("brand", {}).get("value") if isinstance(fields.get("brand"), dict) else None,
            pack_size=fields.get("pack_size", {}).get("value") if isinstance(fields.get("pack_size"), dict) else None,
            weight=fields.get("weight", {}).get("value") if isinstance(fields.get("weight"), dict) else None,
        )
        with Session(engine) as session:
            ranked = sorted(
                ((match_score(item, request), item) for item in session.scalars(select(Product))),
                key=lambda item: item[0],
                reverse=True,
            )
            if ranked and ranked[0][0] >= 30:
                score, product = ranked[0]
                matched_product = billing_response(product, score)
                best_confidence = score
    
    # Determine overall confidence
    confidences = []
    if barcode_result:
        for bc in barcode_result.barcodes:
            confidences.append(bc.get("confidence", 0))
    if ocr_result:
        for field_data in ocr_result.fields.values():
            if isinstance(field_data, dict):
                confidences.append(field_data.get("confidence", 0))
    if visual_match:
        confidences.append(visual_match.confidence)
    if matched_product:
        confidences.append(matched_product.confidence)
    
    overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    requires_review = overall_confidence < 80 or matched_product is None
    
    with Session(engine) as session:
        audit(session, client_id, "product.analyze", file.filename or "upload", f"confidence={overall_confidence:.1f}")
        session.commit()
    
    return ProductAnalyzeResponse(
        success=True,
        filename=file.filename or "upload",
        documentType=classification.get("documentType", "unknown"),
        barcodeResult=barcode_result,
        ocrResult=ocr_result,
        visualMatch=visual_match,
        matchedProduct=matched_product,
        confidence=round(overall_confidence, 2),
        requiresReview=requires_review,
    )
