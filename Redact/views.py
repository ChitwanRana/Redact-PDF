import os
import io
import uuid
import fitz  # PyMuPDF
from django.conf import settings
from django.shortcuts import render
from django.http import FileResponse
from django.core.files.storage import default_storage
import json

TEMP_DIR = os.path.join(settings.MEDIA_ROOT, "temp")

def extract_highlight_images(pdf_path, terms):
    doc = fitz.open(pdf_path)
    image_paths = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        for term in terms:
            areas = page.search_for(term)
            for rect in areas:
                highlight = page.add_highlight_annot(rect)
                highlight.update()

        img_path = os.path.join(TEMP_DIR, f"preview_page_{page_num}.png")
        pix = page.get_pixmap()
        pix.save(img_path)
        image_paths.append(f"/media/temp/preview_page_{page_num}.png")

    return image_paths

def index(request):
    if request.method == "POST" and request.FILES.get("pdf"):
        pdf_file = request.FILES["pdf"]
        terms = [t.strip() for t in request.POST.get("terms", "").split(",") if t.strip()]
        session_id = str(uuid.uuid4())
        temp_pdf_path = os.path.join(TEMP_DIR, f"{session_id}.pdf")
        os.makedirs(TEMP_DIR, exist_ok=True)
        default_storage.save(temp_pdf_path, pdf_file)

        request.session['temp_pdf'] = temp_pdf_path
        request.session['terms'] = terms

        # Create previews
        images = extract_highlight_images(temp_pdf_path, terms)
        return render(request, "preview.html", {"images": images})

    return render(request, "index.html")

def redact_confirm(request):
    temp_pdf = request.session.get('temp_pdf')
    terms = request.session.get('terms', [])

    if not temp_pdf or not os.path.exists(temp_pdf):
        return render(request, "redact/index.html", {"error": "No session data found."})

    doc = fitz.open(temp_pdf)

    # Manual redaction boxes from canvas
    if request.method == "POST":
        boxes_json = request.POST.get("boxes_json")
        if boxes_json:
            drawings = json.loads(boxes_json)
            for page_index, boxes in drawings.items():
                page = doc[int(page_index)]
                pix = page.get_pixmap()
                scale_x = page.rect.width / pix.width
                scale_y = page.rect.height / pix.height

                for b in boxes:
                    rect = fitz.Rect(
                        b["x"] * scale_x,
                        b["y"] * scale_y,
                        (b["x"] + b["w"]) * scale_x,
                        (b["y"] + b["h"]) * scale_y
                    )
                    page.add_redact_annot(rect, fill=(0, 0, 0))

        # Apply search-based redaction too (if needed)
        for page in doc:
            for term in terms:
                for rect in page.search_for(term):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return FileResponse(output, as_attachment=True, filename="redacted.pdf")
