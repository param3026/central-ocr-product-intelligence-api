from __future__ import annotations

from io import BytesIO
import re
from typing import Protocol


class InvoiceProvider(Protocol):
    def extract_invoice(self, content: bytes, filename: str) -> dict: ...


class OcrProvider(Protocol):
    def extract(self, content: bytes, filename: str) -> dict: ...


class VisualRecognitionProvider(Protocol):
    def compare(self, content: bytes, reference: bytes) -> dict: ...


class DocumentClassifierProvider(Protocol):
    def classify(self, content: bytes, filename: str) -> dict: ...


class BarcodeDecoderProvider(Protocol):
    def decode(self, content: bytes, filename: str) -> dict: ...


class LabReportProvider(Protocol):
    def extract_lab_report(self, content: bytes, filename: str) -> dict: ...


class ErpPosSyncProvider(Protocol):
    def sync_inventory(self, payload: dict) -> dict: ...


class ProviderNotConfigured:
    def __getattr__(self, name: str):
        raise NotImplementedError(f"Provider method '{name}' is not configured")


class LocalPdfInvoiceProvider:
    """Extract text and stable numeric/header fields from text-based PDFs.

    This is deliberately conservative: it never invents product names or
    identifiers when a PDF's embedded font makes them unreadable.
    """

    def extract_invoice(self, content: bytes, filename: str) -> dict:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise ProviderNotConfigured("pypdf is not installed") from exc

        try:
            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValueError("The uploaded file is not a readable PDF") from exc
        if not text.strip():
            raise ValueError("The PDF contains no extractable text; image OCR is not configured")

        def first(pattern: str) -> str | None:
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1) if match else None

        def money(pattern: str) -> float | None:
            value = first(pattern)
            if not value:
                return None
            try:
                return float(value.replace(",", ""))
            except ValueError:
                return None

        # Header fields
        invoice_number = first(r"(?:invoice|bill)\s*(?:no|number|#)\s*[:]?\s*([A-Z0-9\-\/]+)")
        invoice_date = first(r"(?:invoice|bill)\s*date\s*[:]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})")
        vendor_name = first(r"(?:vendor|supplier|sold by)\s*[:]?\s*([A-Za-z0-9\s\.\-]+)")
        vendor_address = first(r"(?:vendor|supplier)\s*address\s*[:]?\s*([A-Za-z0-9\s\.\,\-]+)")
        gstin = first(r"GSTIN/UIN\s*:?\s*([0-9A-Z]{15})")
        fssai = first(r"FSSI\s*NO\.\s*-\s*([0-9]{14})")
        taxable = money(r"Total\s*\n?Amount Chargeable.*?([0-9][0-9,]*\.\d{2})")
        total = money(r"Total\s+([0-9][0-9,]*\.\d{2})")
        cgst = money(r"TotalSGST/UTGSTCGST.*?\n.*?([0-9][0-9,]*\.\d{2})")
        sgst = money(r"SGST\s*[:]?\s*([0-9][0-9,]*\.\d{2})")
        igst = money(r"IGST\s*[:]?\s*([0-9][0-9,]*\.\d{2})")

        # Some Indian invoice PDFs have broken ToUnicode maps, so labels and
        # line breaks disappear. Recover only the final tax-summary pattern.
        amounts = [float(value.replace(",", "")) for value in re.findall(r"\d[\d,]*\.\d{2}", text)]
        if amounts and taxable is None:
            taxable = amounts[-1]
        if cgst is None and len(amounts) >= 5:
            candidate = amounts[-5]
            if candidate != 2.5 and candidate < (taxable or float("inf")):
                cgst = candidate
        if total is None and taxable is not None and cgst is not None:
            total = round(taxable + (cgst * 2), 2)

        # Extract line items with all required fields
        lines = []
        raw_lines = text.splitlines()
        for index, line in enumerate(raw_lines):
            # Try to find product description (text before numbers)
            desc_match = re.search(r"^([A-Za-z\s\.\-]+?)\s+\d", line)
            description = desc_match.group(1).strip() if desc_match else None
            
            # Unit and rate
            unit_match = re.search(r"\b(Ltr|Nos|kgs|pcs|boxes)\s*([\d,]+\.\d{2})", line, re.IGNORECASE)
            values = re.findall(r"\d[\d,]*\.\d{2}", line)
            
            if not unit_match or len(values) < 5:
                continue
                
            quantity_match = re.search(r"([\d,]+(?:\.\d+)?)\s+(?:Ltr|Nos|kgs|pcs|boxes)\b", line, re.IGNORECASE)
            if not quantity_match and index + 1 < len(raw_lines):
                quantity_match = re.search(r"([\d,]+(?:\.\d+)?)\s+(?:Ltr|Nos|kgs|pcs|boxes)\b", raw_lines[index + 1], re.IGNORECASE)
            
            # Try to extract product code/SKU/barcode from the line or nearby lines
            barcode_match = re.search(r"\b(\d{12,14})\b", line)
            sku_match = re.search(r"(?:sku|code)\s*[:]?\s*([A-Z0-9\-]+)", line, re.IGNORECASE)
            hsn_match = re.search(r"\b(\d{4,8})\b", line)
            
            # Free quantity
            free_qty_match = re.search(r"(?:free|foc)\s*[:]?\s*(\d+)", line, re.IGNORECASE)
            
            # Discount
            discount_match = re.search(r"(?:disc|discount)\s*[:]?\s*([\d,]+\.?\d*)", line, re.IGNORECASE)
            
            # Batch, mfg, expiry
            batch_match = re.search(r"(?:batch|btch|bt\.?no)\s*[:]?\s*([A-Z0-9\-]+)", line, re.IGNORECASE)
            mfg_match = re.search(r"(?:mfg|manufacture)\s*[:]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", line, re.IGNORECASE)
            exp_match = re.search(r"(?:exp|expiry)\s*[:]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", line, re.IGNORECASE)
            
            lines.append({
                "description": description,
                "product_code": sku_match.group(1) if sku_match else None,
                "barcode": barcode_match.group(1) if barcode_match else None,
                "hsn": hsn_match.group(1) if hsn_match else None,
                "quantity": float(quantity_match.group(1).replace(",", "")) if quantity_match else None,
                "free_quantity": int(free_qty_match.group(1)) if free_qty_match else 0,
                "unit": unit_match.group(1),
                "rate": float(unit_match.group(2).replace(",", "")),
                "discount": float(discount_match.group(1).replace(",", "")) if discount_match else 0,
                "totalAmount": float(values[0].replace(",", "")),
                "taxableValue": float(values[-2].replace(",", "")),
                "cgst": float(values[1].replace(",", "")) if len(values) > 1 else 0,
                "sgst": float(values[3].replace(",", "")) if len(values) > 3 else 0,
                "igst": 0,
                "mrp": None,
                "batch_number": batch_match.group(1) if batch_match else None,
                "manufacturing_date": mfg_match.group(1) if mfg_match else None,
                "expiry_date": exp_match.group(1) if exp_match else None,
                "confidence": 35.0,
                "source": "pdf_text",
                "requiresReview": True,
            })

        degraded_text = "\x00" in text or any(ord(ch) < 9 for ch in text)
        warnings = []
        if degraded_text:
            warnings.append("Some PDF text uses an unreadable embedded font; product names need review")
        if taxable is None or total is None:
            warnings.append("One or more invoice totals could not be read confidently")
        if not lines:
            warnings.append("No line items could be extracted from the invoice")

        return {
            "success": True,
            "documentType": "invoice",
            "filename": filename,
            "pageCount": len(reader.pages),
            "invoiceNumber": {"value": invoice_number, "confidence": 90.0, "source": "pdf_text"} if invoice_number else None,
            "invoiceDate": {"value": invoice_date, "confidence": 85.0, "source": "pdf_text"} if invoice_date else None,
            "vendorName": {"value": vendor_name, "confidence": 85.0, "source": "pdf_text"} if vendor_name else None,
            "vendorAddress": {"value": vendor_address, "confidence": 70.0, "source": "pdf_text"} if vendor_address else None,
            "vendorGstin": {"value": gstin, "confidence": 99.0, "source": "pdf_text"} if gstin else None,
            "fssaiNumber": {"value": fssai, "confidence": 99.0, "source": "pdf_text"} if fssai else None,
            "taxableValue": {"value": taxable, "confidence": 80.0, "source": "pdf_text"} if taxable is not None else None,
            "totalAmount": {"value": total, "confidence": 80.0, "source": "pdf_text"} if total is not None else None,
            "cgst": {"value": cgst, "confidence": 70.0, "source": "pdf_text"} if cgst is not None else None,
            "sgst": {"value": sgst, "confidence": 70.0, "source": "pdf_text"} if sgst is not None else None,
            "igst": {"value": igst, "confidence": 70.0, "source": "pdf_text"} if igst is not None else None,
            "lines": lines,
            "warnings": warnings,
            "requiresReview": bool(warnings) or len(lines) == 0,
        }


class LocalDocumentClassifier:
    """Classify document type from PDF/image content using keyword heuristics."""

    DOCUMENT_TYPES = {
        "invoice": ["invoice", "bill", "tax invoice", "gst invoice", "purchase bill", "vendor"],
        "product_box": ["product", "packaging", "box", "label", "mfg", "exp", "batch", "mrp"],
        "barcode_label": ["barcode", "qr code", "ean", "upc", "gtin", "code 128", "code 39"],
        "lab_report": ["lab report", "laboratory", "test report", "analysis", "certificate of analysis", "coa"],
        "certificate": ["certificate", "certification", "iso", "fssai", "halal", "organic"],
        "product_id": ["product id", "product code", "sku", "item code"],
        "warranty_card": ["warranty", "guarantee", "service card"],
        "shipping_label": ["shipping", "courier", "tracking", "consignment", "waybill"],
    }

    def classify(self, content: bytes, filename: str) -> dict:
        # Try to extract text from PDF first
        text = ""
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            pass

        # If no text extracted, assume image - will need OCR
        if not text.strip():
            return {
                "success": True,
                "documentType": "unknown",
                "filename": filename,
                "confidence": 10.0,
                "source": "no_text_extracted",
                "requiresReview": True,
                "suggestedTypes": list(self.DOCUMENT_TYPES.keys()),
            }

        text_lower = text.lower()
        scores = {}
        for doc_type, keywords in self.DOCUMENT_TYPES.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[doc_type] = score

        if not scores:
            return {
                "success": True,
                "documentType": "unknown",
                "filename": filename,
                "confidence": 15.0,
                "source": "pdf_text",
                "requiresReview": True,
                "suggestedTypes": list(self.DOCUMENT_TYPES.keys()),
            }

        best_type = max(scores, key=scores.get)
        max_score = scores[best_type]
        confidence = min(90.0, 40.0 + max_score * 10)

        return {
            "success": True,
            "documentType": best_type,
            "filename": filename,
            "confidence": confidence,
            "source": "pdf_text_keywords",
            "allScores": scores,
            "requiresReview": confidence < 70,
        }


class LocalBarcodeDecoder:
    """Decode barcodes and QR codes from images.
    
    Requires: pip install pyzbar opencv-python-headless
    And system-level: brew install zbar (macOS) / apt-get install libzbar0 (Linux)
    """

    def decode(self, content: bytes, filename: str) -> dict:
        try:
            import cv2
            import numpy as np
            from pyzbar.pyzbar import decode
        except ImportError as exc:
            raise ProviderNotConfigured("pyzbar and opencv-python-headless are required for barcode decoding") from exc

        # Convert bytes to OpenCV image
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Uploaded file is not a valid image")

        try:
            decoded_objects = decode(img)
        except Exception as exc:
            raise ProviderNotConfigured("zbar shared library not found. Install system-level: brew install zbar (macOS) / apt-get install libzbar0 (Linux)") from exc

        if not decoded_objects:
            return {
                "success": True,
                "barcodes": [],
                "filename": filename,
                "message": "No barcode/QR code found in image",
            }

        barcodes = []
        for obj in decoded_objects:
            barcodes.append({
                "data": obj.data.decode("utf-8"),
                "type": obj.type,
                "rect": {
                    "left": obj.rect.left,
                    "top": obj.rect.top,
                    "width": obj.rect.width,
                    "height": obj.rect.height,
                },
                "confidence": 95.0,
            })

        return {
            "success": True,
            "barcodes": barcodes,
            "filename": filename,
        }


class LocalProductImageOcr:
    """Extract product information from product/package images using OCR.
    
    Requires: pip install pytesseract pillow
    Tesseract must be installed system-level: brew install tesseract (macOS) / apt-get install tesseract-ocr (Linux)
    """

    def extract(self, content: bytes, filename: str) -> dict:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise ProviderNotConfigured("pytesseract and pillow are required for image OCR") from exc

        try:
            img = Image.open(BytesIO(content))
        except Exception as exc:
            raise ValueError("Uploaded file is not a valid image") from exc

        try:
            text = pytesseract.image_to_string(img)
        except Exception as exc:
            raise ProviderNotConfigured("tesseract executable not found. Install system-level: brew install tesseract (macOS) / apt-get install tesseract-ocr (Linux)") from exc
        if not text.strip():
            return {
                "success": True,
                "fields": {},
                "filename": filename,
                "message": "No text found in image",
                "requiresReview": True,
            }

        # Extract common product fields using regex patterns
        fields = {}
        text_lower = text.lower()

        # Product name / brand (heuristic - first few lines often contain these)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if lines:
            fields["product_name"] = {"value": lines[0], "confidence": 60.0, "source": "ocr_text"}

        # MRP
        mrp_match = re.search(r"(?:mrp|m\.r\.p\.|maximum retail price)\s*[:\-]?\s*[₹$]?\s*(\d+(?:[.,]\d+)?)", text_lower)
        if mrp_match:
            fields["mrp"] = {"value": float(mrp_match.group(1).replace(",", "")), "confidence": 80.0, "source": "ocr_text"}

        # GST/HSN
        gst_match = re.search(r"gst\s*[:\-]?\s*(\d+(?:\.\d+)?)", text_lower)
        if gst_match:
            fields["gst_rate"] = {"value": float(gst_match.group(1)), "confidence": 75.0, "source": "ocr_text"}

        hsn_match = re.search(r"hsn\s*[:\-]?\s*(\d{4,8})", text_lower)
        if hsn_match:
            fields["hsn"] = {"value": hsn_match.group(1), "confidence": 80.0, "source": "ocr_text"}

        # Batch
        batch_match = re.search(r"(?:batch|btch|bt\.?no)\s*[:\-]?\s*([A-Z0-9\-]+)", text_lower)
        if batch_match:
            fields["batch_number"] = {"value": batch_match.group(1).upper(), "confidence": 70.0, "source": "ocr_text"}

        # Expiry date
        exp_match = re.search(r"(?:exp|expiry|mfg|manufacture)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", text_lower)
        if exp_match:
            fields["expiry_date"] = {"value": exp_match.group(1), "confidence": 70.0, "source": "ocr_text"}

        # Weight/Net weight
        weight_match = re.search(r"(?:net\s*wt|weight|net\s*weight)\s*[:\-]?\s*([\d.]+)\s*(g|kg|ml|l)", text_lower)
        if weight_match:
            fields["weight"] = {"value": f"{weight_match.group(1)}{weight_match.group(2)}", "confidence": 75.0, "source": "ocr_text"}

        # Pack size
        pack_match = re.search(r"(?:pack|size|qty)\s*[:\-]?\s*([\d.]+)\s*(g|kg|ml|l|pcs?|nos?)", text_lower)
        if pack_match:
            fields["pack_size"] = {"value": f"{pack_match.group(1)}{pack_match.group(2)}", "confidence": 65.0, "source": "ocr_text"}

        requires_review = any(v.get("confidence", 0) < 70 for v in fields.values())

        return {
            "success": True,
            "documentType": "product_box",
            "filename": filename,
            "fields": fields,
            "rawText": text[:500],
            "requiresReview": requires_review or len(fields) < 3,
        }


class LocalVisualRecognition:
    """Compare product/package images using perceptual hashing.
    
    Requires: pip install imagehash pillow
    """

    def compare(self, content: bytes, reference: bytes) -> dict:
        try:
            import imagehash
            from PIL import Image
        except ImportError as exc:
            raise ProviderNotConfigured("imagehash and pillow are required for visual recognition") from exc

        try:
            img1 = Image.open(BytesIO(content))
            img2 = Image.open(BytesIO(reference))
        except Exception as exc:
            raise ValueError("One or both files are not valid images") from exc

        # Perceptual hash comparison
        hash1 = imagehash.phash(img1)
        hash2 = imagehash.phash(img2)
        diff = hash1 - hash2
        max_diff = len(hash1.hash) ** 2
        similarity = 1.0 - (diff / max_diff)

        return {
            "success": True,
            "similarity": round(similarity * 100, 2),
            "hash1": str(hash1),
            "hash2": str(hash2),
            "difference": diff,
            "match": similarity > 0.85,
            "confidence": round(similarity * 100, 2),
        }


class LocalLabReportProvider:
    """Extract structured data from lab reports / certificates of analysis."""

    def extract_lab_report(self, content: bytes, filename: str) -> dict:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ProviderNotConfigured("pypdf is not installed") from exc

        try:
            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValueError("The uploaded file is not a readable PDF") from exc

        if not text.strip():
            raise ValueError("The PDF contains no extractable text")

        fields = {}
        text_lower = text.lower()

        # Report number
        report_match = re.search(r"(?:report|certificate)\s*(?:no|number|#)\s*[:\-]?\s*([A-Z0-9\-\/]+)", text_lower)
        if report_match:
            fields["report_number"] = {"value": report_match.group(1).upper(), "confidence": 85.0, "source": "pdf_text"}

        # Lab name
        lab_match = re.search(r"(?:laboratory|lab|tested by)\s*[:\-]?\s*([A-Za-z0-9\s\.\-]+)", text_lower)
        if lab_match:
            fields["lab_name"] = {"value": lab_match.group(1).strip(), "confidence": 75.0, "source": "pdf_text"}

        # Product/batch
        product_match = re.search(r"(?:product|sample)\s*[:\-]?\s*([A-Za-z0-9\s\.\-]+)", text_lower)
        if product_match:
            fields["product_name"] = {"value": product_match.group(1).strip(), "confidence": 70.0, "source": "pdf_text"}

        batch_match = re.search(r"(?:batch|lot)\s*(?:no|number)?\s*[:\-]?\s*([A-Z0-9\-]+)", text_lower)
        if batch_match:
            fields["batch_number"] = {"value": batch_match.group(1).upper(), "confidence": 80.0, "source": "pdf_text"}

        # Test date
        date_match = re.search(r"(?:test|analysis|report)\s*date\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", text_lower)
        if date_match:
            fields["test_date"] = {"value": date_match.group(1), "confidence": 80.0, "source": "pdf_text"}

        # Parameters/results - look for table-like patterns
        param_pattern = re.compile(r"([A-Za-z\s]+)\s+(\d+(?:\.\d+)?)\s+([A-Za-z\/%]+)\s+(\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?))?\s*(pass|fail|within limits)?", re.IGNORECASE)
        parameters = []
        for match in param_pattern.finditer(text):
            parameters.append({
                "parameter": match.group(1).strip(),
                "result": match.group(2),
                "unit": match.group(3),
                "reference_range": match.group(4) or "",
                "status": match.group(5) or "",
            })

        if parameters:
            fields["parameters"] = {"value": parameters, "confidence": 60.0, "source": "pdf_text"}

        requires_review = len(fields) < 3

        return {
            "success": True,
            "documentType": "lab_report",
            "filename": filename,
            "fields": fields,
            "requiresReview": requires_review,
        }


# Provider instances
invoice_provider = LocalPdfInvoiceProvider()
document_classifier = LocalDocumentClassifier()
barcode_decoder = LocalBarcodeDecoder()
product_image_ocr = LocalProductImageOcr()
visual_recognition = LocalVisualRecognition()
lab_report_provider = LocalLabReportProvider()