import sys

sys.path.insert(0, ".")

from app.main import ApiClient, Product, engine, hash_secret
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import date

CLIENT_ID = "demo-pos"
CLIENT_SECRET = "change-me-in-development"

with Session(engine) as session:
    client = session.scalar(select(ApiClient).where(ApiClient.client_id == CLIENT_ID))
    if not client:
        session.add(ApiClient(client_id=CLIENT_ID, secret_hash=hash_secret(CLIENT_SECRET)))

    product = session.scalar(select(Product).where(Product.product_id == "PRD-1025"))
    if not product:
        session.add(Product(
            product_id="PRD-1025",
            sku="COKE-500",
            product_name="Coca-Cola 500ml",
            brand="Coca-Cola",
            category="Soft Drinks",
            barcode="8901234567890",
            hsn="2202",
            gst_rate=18,
            mrp=250,
            selling_price=225,
            purchase_price=200,
            unit="bottle",
            pack_size="500ml",
            weight="500g",
            description="Carbonated soft drink",
            available_stock=42,
            manufacturing_date=date(2025, 1, 15),
            expiry_date=date(2026, 1, 15),
            serial_number=None,
            license_certificate_info=None,
            ingredients_attributes="Carbonated water, sugar, caramel color, phosphoric acid, natural flavors, caffeine",
            product_image=None,
            product_box_image=None,
            logo=None,
            primary_color="#FF0000",
            secondary_color="#FFFFFF",
            custom_fields=None,
        ))
    session.commit()

print(f"Seed ready. client_id={CLIENT_ID} client_secret={CLIENT_SECRET}")
