# Central AI OCR & Product Intelligence API

## Current implementation status (2026-09-21)

- Phase 1: product master fields, duplicate prevention, barcode lookup, weighted matching, bearer authentication, and billing responses are implemented.
- Phase 2: text-PDF invoice extraction, confidence/provenance fields, upload validation, local image OCR, barcode/QR providers, and visual comparison are implemented with explicit system-dependency errors.
- Phase 3: invoice processing supports verified-product matching, GST/HSN review gates, approval-before-stock-update, batch/expiry updates, and idempotent source references. Complex scanned invoices and table extraction remain limited.
- Product approval: product suggestions can be created, listed, approved, rejected, and converted into verified master products through API endpoints.
- Phases 4–6: baseline billing, inventory sync, audit logging, health checks, Docker PostgreSQL, and OpenAPI documentation exist. Normalized batch/serial/inventory tables, ERP connectors, background jobs, scopes, pagination, request IDs, admin UI, and full production hardening remain.

## Goal
Build a central, master-data-first API that accepts product and document scans, extracts structured information, matches it against verified product data, validates uncertain fields, and returns inventory/billing-ready results.

## Current baseline
- FastAPI service with SQLite and SQLAlchemy.
- Product create/list operations.
- Barcode lookup and simple field-based product matching.
- Billing-shaped response for matched products.
- Invoice and product upload endpoints are placeholders.
- No API key is required by the current MVP.
- Local dependencies are not installed in the current environment yet.

## Delivery plan

### Phase 1: Stabilize the product master
- Expand the product schema to cover the requirements: sub-category, GTIN/barcode variants, images, packaging metadata, batch/expiry/serial data, licenses, ingredients/attributes, and custom fields.
- Separate stable product data from batch, serial, and inventory records.
- Add migrations/configuration instead of relying on import-time table creation.
- Add request validation for prices, GST, dates, identifiers, and units.
- Add duplicate prevention using normalized barcode/SKU/brand/name/pack-size/weight signals.
- Add focused API tests for create, conflict, lookup, and duplicate behavior.

### Phase 2: Local scan foundations
- Add a provider interface for document classification, OCR, barcode/QR decoding, and visual analysis.
- Implement a no-API-key local provider where the machine supports it.
- Return extracted fields with per-field confidence, source, and validation status.
- Make unsupported capabilities explicit instead of returning invented values.
- Add file type/size limits and safe temporary-file handling.

### Phase 3: Invoice OCR to inventory
- Classify uploads before extraction.
- Extract invoice header, vendor, tax, totals, and line items.
- Match each line to the product master using verified identifiers first, then weighted fallback matching.
- Validate tax/HSN/GST and arithmetic against master data and business rules.
- Introduce a review state for low-confidence or conflicting fields.
- On approval, create/update batch and inventory records idempotently.

### Phase 4: Product/package scan to billing
- Decode supported barcode/QR formats.
- Use OCR fields and visual signals as fallback when no code match exists.
- Compare packaging/product images only when reference images exist in the master.
- Return verified billing data, stock, batch/expiry information, confidence, and review requirements.
- Add expiry and stock safeguards appropriate for billing.

### Phase 5: Documents, sync, and audit
- Implement document classification for product boxes, invoices, labels, lab reports, certificates, IDs, warranty cards, shipping labels, and other documents.
- Add lab report/certificate extraction models with document-specific schemas.
- Add inventory sync with idempotency and conflict reporting.
- Add audit/process records for uploads, extracted values, matching decisions, approvals, and sync outcomes.

### Phase 6: Integration hardening
- Add authentication/token issuance and per-client scopes.
- Add consistent error schemas, request IDs, pagination, health/readiness checks, and structured logs.
- Add PostgreSQL support and environment-based configuration.
- Add background processing for larger files and a status endpoint.
- Add OpenAPI examples and integration documentation for ERP/POS clients.
- Run end-to-end tests for invoice-to-stock and scan-to-billing flows.

## External requirements and conditional dependencies

### Needed for the no-key local MVP
- Python 3.11+ recommended.
- `pip install -r requirements.txt`.
- A local OCR engine and barcode decoder if real image/PDF processing is required. Candidate stack: Tesseract plus `pytesseract`, OpenCV, and a barcode library. Tesseract is a machine-level install, not a cloud API key.
- PDF/image fixtures for repeatable tests.

### Needed later, depending on deployment choices
- PostgreSQL database for production or multi-instance deployment.
- Object storage for uploaded files and reference images.
- A job queue/worker for asynchronous OCR.
- TLS, secret storage, and an identity/client provisioning method.
- Optional managed OCR/vision service credentials only if local OCR quality or throughput is insufficient.
- ERP/POS integration credentials and contracts for each external system.

## Decisions required before implementation
1. Target deployment: local/on-premise, private cloud, or public cloud?
2. OCR policy: local-only, managed provider, or pluggable local-first with optional provider?
3. Database target for the first usable release: SQLite only or PostgreSQL from the start?
4. Upload storage and retention policy: filesystem, object storage, and how long files/logs remain?
5. Authentication model: API keys, OAuth2 client credentials, or integration-specific tokens?
6. Tax/business rules: India-only GST/HSN rules, and which authority/source is authoritative?
7. Review workflow owner and interface: API-only approval or an admin UI?
8. First integration to validate end-to-end: retail POS, pharma/medical ERP, wholesale ERP, or another system?
9. Expected file sizes, daily volume, latency targets, and supported languages/document quality?
10. Whether product images and sensitive invoice/lab data may leave the deployment boundary.

## Proposed first executable milestone
Implement Phases 1 and 2 as a local, API-only vertical slice: a complete product master, duplicate-safe matching, local barcode/OCR provider contracts, confidence-bearing extraction responses, and automated tests using fixtures. Do not add a cloud API or invent tax/integration behavior until the decisions above are confirmed.

## Verification gates
- Every extracted field has a confidence and provenance status.
- Low-confidence/conflicting data cannot silently update master or inventory records.
- Existing products update stock/batch data idempotently.
- New products enter a review workflow before becoming verified master data.
- Billing responses use verified master values for price, GST, HSN, and product identity.
- Uploads, decisions, approvals, and sync operations are auditable.
- OpenAPI documentation and automated tests cover each released endpoint.
