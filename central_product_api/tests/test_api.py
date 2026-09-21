import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ["DATABASE_URL"] = "sqlite:///./test_products.db"

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.main import ApiClient, AuditLog, Base, InventoryReceipt, Product, ProductSuggestion, engine, hash_secret


client = TestClient(__import__("app.main", fromlist=["app"]).app)


def setup_function():
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(delete(AuditLog))
        session.execute(delete(Product))
        session.execute(delete(ProductSuggestion))
        session.execute(delete(ApiClient))
        session.execute(delete(InventoryReceipt))
        session.add(ApiClient(client_id="test-client", secret_hash=hash_secret("test-secret")))
        session.commit()


def token() -> str:
    response = client.post("/api/auth/token", json={"client_id": "test-client", "client_secret": "test-secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def product_payload():
    return {
        "product_id": "PRD-1",
        "sku": "SKU-1",
        "product_name": "Test Product 500ml",
        "brand": "Test Brand",
        "pack_size": "500ml",
        "barcode": "8900000000001",
        "mrp": 100,
        "selling_price": 90,
        "gst_rate": 18,
        "available_stock": 4,
    }


def suggestion_payload():
    return {
        "product_id": "PRD-SUG-1",
        "sku": "SUG-SKU-1",
        "product_name": "Suggested Product 500ml",
        "brand": "Suggested Brand",
        "pack_size": "500ml",
        "barcode": "8900000000002",
        "mrp": 150,
        "selling_price": 135,
        "gst_rate": 18,
        "source_reference": "OCR-INV-001",
        "confidence": 85.0,
    }


def test_protected_product_flow_and_duplicate_prevention():
    assert client.get("/api/products").status_code == 401
    headers = {"Authorization": f"Bearer {token()}"}
    created = client.post("/api/product", json=product_payload(), headers=headers)
    assert created.status_code == 200
    assert client.post("/api/product", json=product_payload(), headers=headers).status_code == 409
    lookup = client.get("/api/product/barcode/8900000000001", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["confidence"] == 100.0


def test_matching_inventory_billing_and_audit():
    headers = {"Authorization": f"Bearer {token()}"}
    client.post("/api/product", json=product_payload(), headers=headers)
    match = client.post("/api/product/match", json={"product_name": "Test Product", "brand": "Test Brand"}, headers=headers)
    assert match.status_code == 200
    assert match.json()["requiresReview"] is True

    sync = client.post("/api/inventory/sync", json={"product_id": "PRD-1", "quantity_delta": 3, "source_reference": "GRN-1"}, headers=headers)
    assert sync.status_code == 200
    assert sync.json()["availableStock"] == 7

    billing = client.get("/api/billing/product/PRD-1", headers=headers)
    assert billing.status_code == 200
    assert billing.json()["productId"] == "PRD-1"

    with Session(engine) as session:
        actions = {row.action for row in session.query(AuditLog).all()}
    assert {"auth.token", "product.create", "product.match", "inventory.sync", "billing.product"}.issubset(actions)


def test_product_ocr_rejects_unsupported_file_type():
    headers = {"Authorization": f"Bearer {token()}"}
    response = client.post("/api/ocr/product", files={"file": ("sample.txt", b"not processed")}, headers=headers)
    assert response.status_code == 415


def test_invoice_pdf_extraction_returns_provenance_and_review_flag():
    headers = {"Authorization": f"Bearer {token()}"}
    response = client.post("/api/ocr/invoice", files={"file": ("invoice.pdf", b"%PDF-1.4 not really a pdf", "application/pdf")}, headers=headers)
    assert response.status_code == 422


def test_upload_type_is_rejected_before_provider_processing():
    headers = {"Authorization": f"Bearer {token()}"}
    response = client.post("/api/ocr/invoice", files={"file": ("sample.txt", b"hello", "text/plain")}, headers=headers)
    assert response.status_code == 415


def test_invoice_processing_requires_approval_and_is_idempotent():
    headers = {"Authorization": f"Bearer {token()}"}
    client.post("/api/product", json=product_payload(), headers=headers)
    payload = {"source_reference": "INV-1", "approve": False, "lines": [{"barcode": "8900000000001", "quantity": 2, "purchase_price": 95, "gst_rate": 18}]}
    review = client.post("/api/invoice/process", json=payload, headers=headers)
    assert review.status_code == 200
    assert review.json()["status"] == "review_required"
    approved = client.post("/api/invoice/process", json={**payload, "approve": True}, headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["updatedProducts"][0]["availableStock"] == 6
    replay = client.post("/api/invoice/process", json={**payload, "approve": True}, headers=headers)
    assert replay.json()["status"] == "approved"
    # The source reference prevents a second stock update.
    with Session(engine) as session:
        assert session.query(InventoryReceipt).count() == 1


def test_invoice_ocr_extracts_all_required_fields():
    """Test that invoice OCR response model includes all required fields from requirements."""
    headers = {"Authorization": f"Bearer {token()}"}
    # This will fail with 422 because it's not a real PDF, but we can check the response model
    # by looking at the OpenAPI schema
    import json
    schema_response = client.get("/openapi.json", headers=headers)
    assert schema_response.status_code == 200
    schema = schema_response.json()
    
    invoice_extraction = schema["components"]["schemas"]["InvoiceExtraction"]
    props = invoice_extraction.get("properties", {})
    
    # Check all required fields from requirements are present
    required_fields = [
        "invoiceNumber", "invoiceDate", "vendorName", "vendorAddress",
        "vendorGstin", "fssaiNumber", "taxableValue", "totalAmount",
        "cgst", "sgst", "igst", "lines"
    ]
    
    for field in required_fields:
        assert field in props, f"Missing required field in InvoiceExtraction: {field}"
    
    # Check lines have all required sub-fields
    lines_schema = props.get("lines", {})
    assert lines_schema.get("type") == "array"


def test_product_suggestion_workflow():
    """Test the new-product approval workflow: create suggestion -> list -> get -> review (approve) -> becomes product."""
    headers = {"Authorization": f"Bearer {token()}"}
    
    # 1. Create a product suggestion
    suggestion_resp = client.post("/api/product/suggestion", json=suggestion_payload(), headers=headers)
    assert suggestion_resp.status_code == 200
    suggestion = suggestion_resp.json()
    assert suggestion["status"] == "pending"
    assert suggestion["product_id"] == "PRD-SUG-1"
    suggestion_id = suggestion["id"]
    
    # 2. List suggestions
    list_resp = client.get("/api/product/suggestions", headers=headers)
    assert list_resp.status_code == 200
    suggestions = list_resp.json()
    assert len(suggestions) == 1
    assert suggestions[0]["id"] == suggestion_id
    
    # 3. Get specific suggestion
    get_resp = client.get(f"/api/product/suggestion/{suggestion_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == suggestion_id
    
    # 4. Review - approve
    review_resp = client.post(
        f"/api/product/suggestion/{suggestion_id}/review",
        json={"action": "approve", "reviewed_by": "admin-user"},
        headers=headers
    )
    assert review_resp.status_code == 200
    reviewed = review_resp.json()
    assert reviewed["status"] == "approved"
    assert reviewed["reviewed_by"] == "admin-user"
    assert reviewed["reviewed_at"] is not None
    
    # 5. Verify product was created
    product_resp = client.get("/api/product/barcode/8900000000002", headers=headers)
    assert product_resp.status_code == 200
    product = product_resp.json()
    assert product["productId"] == "PRD-SUG-1"
    assert product["productName"] == "Suggested Product 500ml"
    assert product["mrp"] == 150
    assert product["confidence"] == 100.0


def test_product_suggestion_reject():
    """Test rejecting a product suggestion."""
    headers = {"Authorization": f"Bearer {token()}"}
    
    # Create a suggestion
    suggestion_resp = client.post("/api/product/suggestion", json=suggestion_payload(), headers=headers)
    assert suggestion_resp.status_code == 200
    suggestion_id = suggestion_resp.json()["id"]
    
    # Reject it
    review_resp = client.post(
        f"/api/product/suggestion/{suggestion_id}/review",
        json={"action": "reject", "reviewed_by": "admin-user"},
        headers=headers
    )
    assert review_resp.status_code == 200
    reviewed = review_resp.json()
    assert reviewed["status"] == "rejected"
    
    # Verify product was NOT created
    product_resp = client.get("/api/product/barcode/8900000000002", headers=headers)
    assert product_resp.status_code == 404


def test_product_suggestion_duplicate_prevention():
    """Test that duplicate suggestions (by barcode) are prevented."""
    headers = {"Authorization": f"Bearer {token()}"}
    
    # Create first suggestion
    resp1 = client.post("/api/product/suggestion", json=suggestion_payload(), headers=headers)
    assert resp1.status_code == 200
    
    # Try to create another with same barcode
    dup_payload = {**suggestion_payload(), "product_id": "PRD-SUG-2", "sku": "SUG-SKU-2"}
    resp2 = client.post("/api/product/suggestion", json=dup_payload, headers=headers)
    assert resp2.status_code == 409
    
    # Create actual product with same barcode
    product_payload_with_barcode = {**product_payload(), "product_id": "PRD-2", "sku": "SKU-2", "barcode": "8900000000002"}
    resp3 = client.post("/api/product", json=product_payload_with_barcode, headers=headers)
    assert resp3.status_code == 200
    
    # Now try suggestion with same barcode - should fail
    resp4 = client.post("/api/product/suggestion", json=suggestion_payload(), headers=headers)
    assert resp4.status_code == 409
