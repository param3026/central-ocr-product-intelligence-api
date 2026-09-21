# Central OCR & Product Intelligence API

Local-first FastAPI MVP for a central product master, invoice extraction, product/package scanning, product matching, inventory updates, billing responses, audit logging, and new-product approval.

This repository is ready for demonstration and local integration. It is not presented as a complete production ERP/POS platform; deferred work is listed at the end of this document.

## Available now

- Local PostgreSQL database through Docker Compose.
- Client credential token issuance and bearer-token protection.
- Product master create/list, normalized duplicate prevention, barcode lookup, weighted matching, and billing responses.
- Invoice PDF text extraction with header fields, line-item fields, confidence, provenance, and review warnings.
- Product image OCR through Tesseract when the system dependency is installed.
- Barcode and QR decoding through OpenCV and zbar when the system dependency is installed.
- Product analysis pipeline combining classification, barcode, OCR, visual comparison, and product-master matching.
- Inventory synchronization with negative-stock protection and idempotent invoice references.
- Product suggestion queue with pending, approve, reject, and duplicate-prevention behavior.
- Audit records for protected operations.
- OpenAPI documentation at `/docs`.

## Prerequisites

- Python 3.11 or newer.
- Docker Desktop or Docker Engine with Docker Compose.
- macOS: Homebrew for Tesseract and zbar.
- Linux: `apt` or an equivalent package manager for Tesseract and libzbar.

## Download and run

Clone the public repository, then enter it:

```bash
git clone https://github.com/<your-github-username>/central-ocr-product-intelligence-api.git
cd central-ocr-product-intelligence-api
```

Create the Python environment and install all project dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install local OCR and barcode system tools.

macOS:

```bash
brew install tesseract zbar
```

Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr libzbar0
```

Start PostgreSQL, apply the tracked migration, and seed demo data:

```bash
docker compose up -d db
alembic upgrade head
python seed.py
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

The default local database settings are:

```text
Host: localhost
Port: 5432
Database: central_product
User: central
Password: central
```

To use another database, copy `.env.example` to `.env` and export the values before starting the API:

```bash
export DATABASE_URL='postgresql+psycopg://user:password@host:5432/database'
export MAX_UPLOAD_BYTES=15728640
```

## Demo credentials

The seed script creates:

```text
client_id: demo-pos
client_secret: change-me-in-development
```

Exchange them for a bearer token:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"client_id":"demo-pos","client_secret":"change-me-in-development"}'
```

Use the returned token as `Authorization: Bearer <TOKEN>`.

## Main endpoints

| Module | Endpoint | Purpose |
| --- | --- | --- |
| Authentication | `POST /api/auth/token` | Issue a bearer token |
| Product master | `POST /api/product` | Create a product |
| Product master | `GET /api/products` | List products |
| Product lookup | `GET /api/product/barcode/{barcode}` | Return billing-ready data |
| Product matching | `POST /api/product/match` | Match scan fields to master data |
| Invoice processing | `POST /api/ocr/invoice` | Extract invoice data from a PDF |
| Invoice inventory | `POST /api/invoice/process` | Review or approve invoice lines |
| Product OCR | `POST /api/ocr/product` | Extract printed product fields from an image |
| Barcode/QR | `POST /api/barcode/decode` | Decode supported codes from an image |
| Product analysis | `POST /api/product/analyze` | Run classification, OCR, barcode, and matching |
| Document classification | `POST /api/document/classify` | Classify uploaded material |
| Lab report | `POST /api/document/lab-report` | Extract basic lab-report fields |
| Visual comparison | `POST /api/visual/compare` | Compare two product images |
| Inventory | `POST /api/inventory/sync` | Apply a protected stock change |
| Billing | `GET /api/billing/product/{product_id}` | Return verified billing data |
| Suggestions | `POST /api/product/suggestion` | Create a new-product suggestion |
| Suggestions | `GET /api/product/suggestions` | List suggestions, optionally by status |
| Suggestions | `POST /api/product/suggestion/{id}/review` | Approve or reject a suggestion |

## Suggested demo sequence

1. Start PostgreSQL and the API.
2. Request a token using the seeded credentials.
3. Create or list a product.
4. Look up the seeded product by barcode: `8901234567890`.
5. Submit an invoice or product image to the OCR endpoint.
6. Create a product suggestion for an unknown product.
7. Approve the suggestion through the review endpoint.
8. Confirm that the approved product can be found in the product master and billing endpoint.

## Tests

Run the automated test suite from the project root:

```bash
source .venv/bin/activate
pytest -q
```

The current suite covers authentication, product creation, duplicate prevention, matching, inventory, billing, upload validation, invoice approval/idempotency, invoice response fields, and product-suggestion approval/rejection.

## Database and migrations

The application defaults to PostgreSQL. Tests override `DATABASE_URL` with SQLite so they can run without a database service. SQLAlchemy metadata still bootstraps the application tables for the local MVP, while Alembic tracks the product-suggestion schema change for repeatable deployments.

## Known limitations and future work

- Invoice extraction is conservative and regex-based; complex table layouts and scanned/image-only invoices require a stronger table/OCR pipeline.
- Product OCR and barcode decoding require the system tools listed above.
- Batch, serial, and inventory data are not yet normalized into separate tables.
- Advanced logo recognition, colour extraction, and model-based visual recognition are deferred.
- ERP/POS connectors, background jobs, request IDs, scopes, pagination, structured logs, TLS/secret management, and an admin review UI are deferred.
- The current approval workflow is API-based; it is not a web administration screen.

## Handoff summary

Available: local PostgreSQL-backed API, authentication, product master, matching, invoice OCR foundation, image OCR and barcode providers, inventory, billing, audit logging, document analysis, and new-product approval.

Updated: dependencies, local setup instructions, OCR/barcode installation instructions, Alembic product-suggestion migration, environment example, endpoint reference, demo sequence, test instructions, limitations, and this handoff summary.

The delivered scope is a tested MVP ready for local demonstration and future ERP/POS integration.
