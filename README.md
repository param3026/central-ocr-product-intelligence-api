# Central OCR & Product Intelligence API

> Local-first FastAPI MVP for OCR, product intelligence, inventory, billing, audit logging, and new-product approval.

This repository is ready for a local demonstration and API handoff. The application lives in `central_product_api/`; the commands below are written for a clean macOS, Debian, or Ubuntu setup.

## Fastest safe install

This is the recommended boss/demo path. It keeps the database on the local machine, uses development-only credentials, and exposes the API on `127.0.0.1` only.

### Prerequisites

Install these first:

- Git
- Docker Desktop with Docker Compose
- Python 3.11 or newer
- macOS: Homebrew
- Debian/Ubuntu: `sudo` access for system packages

Install the OCR and barcode tools once:

```bash
# macOS
brew install tesseract zbar

# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y tesseract-ocr libzbar0
```

### Copy, paste, and run

```bash
git clone https://github.com/param3026/central-ocr-product-intelligence-api.git
cd central-ocr-product-intelligence-api/central_product_api

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

docker compose up -d db
until docker compose exec -T db pg_isready -U central -d central_product >/dev/null 2>&1; do sleep 1; done
alembic upgrade head
python seed.py

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave that terminal running. Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive API documentation.

### Verify the installation

In a second terminal, from `central_product_api/`:

```bash
source .venv/bin/activate
pytest -q
curl -f http://127.0.0.1:8000/docs >/dev/null && echo "API is running"
```

The current handoff test run passes 10 tests.

## Database and configuration

The default database is local PostgreSQL started by Docker Compose. No hosted database is required.

| Setting | Default |
| --- | --- |
| Host | `localhost` |
| Port | `5432` |
| Database | `central_product` |
| User | `central` |
| Password | `central` |

The example configuration is in `central_product_api/.env.example`. For another database, set `DATABASE_URL` in the shell before starting the API.

## Development credentials

`python seed.py` creates this local development client:

```text
client_id: demo-pos
client_secret: change-me-in-development
```

These values are for local demonstration only. Replace them with environment-managed secrets before any shared or production deployment.

Request a token:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"client_id":"demo-pos","client_secret":"change-me-in-development"}'
```

Use the returned value as `Authorization: Bearer <TOKEN>` for protected endpoints.

## Main capabilities

- Product master creation, listing, duplicate prevention, barcode lookup, and weighted matching.
- Invoice PDF extraction with confidence, provenance, review warnings, and line-item fields.
- Product image OCR through Tesseract and barcode/QR decoding through zbar/OpenCV.
- Product analysis combining classification, OCR, barcode, visual comparison, and matching.
- Inventory synchronization with negative-stock protection and idempotent invoice references.
- API-based product suggestion workflow: create, list, approve, reject, and add to the master.
- Billing-ready product responses and audit records for protected operations.

## Important endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/token` | Issue a bearer token |
| `POST` | `/api/ocr/invoice` | Extract invoice data from a PDF |
| `POST` | `/api/ocr/product` | Extract product fields from an image |
| `POST` | `/api/barcode/decode` | Decode barcodes or QR codes |
| `POST` | `/api/product/analyze` | Run the product analysis pipeline |
| `POST` | `/api/product/suggestion` | Create a new-product suggestion |
| `POST` | `/api/product/suggestion/{id}/review` | Approve or reject a suggestion |
| `POST` | `/api/invoice/process` | Review or approve invoice stock updates |
| `POST` | `/api/inventory/sync` | Apply an inventory change |
| `GET` | `/api/product/barcode/{barcode}` | Return billing-ready product data |
| `GET` | `/api/billing/product/{product_id}` | Return verified billing data |

## Safe operating notes

- The quick-start command binds the API to `127.0.0.1`, so it is not publicly reachable by default.
- Do not commit `.env` files, real client secrets, invoice files, or database dumps.
- The repository contains only development sample credentials and source/configuration files.
- Review OCR results before using them for billing or inventory decisions.
- Keep Docker and the operating system updated before presenting the demo.

## Troubleshooting

**Docker is not running**

Start Docker Desktop, then rerun `docker compose up -d db`.

**The migration says PostgreSQL is unavailable**

Run `docker compose ps`, wait until the `db` service is healthy, then run `alembic upgrade head` again.

**`tesseract` or barcode decoding is unavailable**

Confirm the system install above, then run `tesseract --version` and `zbarimg --version`.

**The API port is already in use**

Start on another local port, for example `uvicorn app.main:app --host 127.0.0.1 --port 8001`, and open the matching `/docs` URL.

## Stop or reset the local demo

Stop the API with `Ctrl-C`. Stop PostgreSQL while keeping its local data with:

```bash
docker compose down
```

To intentionally delete the local demo database and its Docker volume, use `docker compose down -v`. This is destructive to the local demo data.

## Verification

From `central_product_api/`:

```bash
source .venv/bin/activate
pytest -q
python -m compileall app tests alembic
```

The verified handoff run passes 10 tests covering authentication, product behavior, duplicate prevention, matching, inventory, billing, upload validation, invoice approval/idempotency, invoice response fields, and product-suggestion review.

## Future work

- Stronger table extraction and scanned/image-only invoice support.
- Normalized batch, serial, and inventory tables.
- Advanced logo, colour, and model-based visual recognition.
- ERP/POS connectors, background jobs, scopes, pagination, request IDs, and structured production logs.
- Web-based administration UI for review and approval.

## Handoff summary

Available: a public, tested, local PostgreSQL-backed MVP with authentication, product master, invoice OCR foundation, image OCR and barcode providers, matching, inventory, billing, audit logging, document analysis, and API-based product approval.

Updated: the README with a fast safe-install path, prerequisites, copy-paste commands, database details, verification, troubleshooting, safe operating notes, stop/reset instructions, endpoint reference, status notes, and future-work boundaries.

The repository is ready for a local boss demonstration and future ERP/POS integration.
