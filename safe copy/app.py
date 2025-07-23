from flask import Flask, render_template, request, send_file
from fractions import Fraction
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)

def parse_fraction(fraction_str):
    try:
        return float(Fraction(fraction_str))
    except (ValueError, ZeroDivisionError):
        return None

def area_to_marlas(kanals, marlas):
    return int(kanals) * 20 + int(marlas)

def marlas_to_str(marlas):
    return f"{marlas // 20}K {marlas % 20}M"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        form = request.form
        khewat_data = {}
        owner_totals = {}
        owner_details = {}

        # Parse each khewat block
        for key in form:
            if key.startswith("khewat") and key.endswith("_no"):
                prefix = key[:-3]
                no = form[key]
                kanals = int(form.get(f"{prefix}_kanals", 0))
                marlas = int(form.get(f"{prefix}_marlas", 0))
                total_marlas = area_to_marlas(kanals, marlas)

                khewat_data[prefix] = {
                    "no": no,
                    "kanals": kanals,
                    "marlas": marlas,
                    "total_marlas": total_marlas,
                    "owners": [],
                }

        for kprefix, kdata in khewat_data.items():
            idx = 0
            while True:
                name_key = f"{kprefix}_owner{idx}_name"
                share_key = f"{kprefix}_owner{idx}_share"
                if name_key not in form:
                    break
                name = form.get(name_key).strip()
                share_str = form.get(share_key).strip()
                fraction = parse_fraction(share_str)
                if not name or fraction is None:
                    return render_template("index.html", result="Invalid owner name or share format.")

                share_marlas = int(kdata["total_marlas"] * fraction)
                share_pretty = marlas_to_str(share_marlas)

                kdata["owners"].append({
                    "name": name,
                    "share_str": share_str,
                    "fraction": fraction,
                    "share_marlas": share_marlas,
                    "share_pretty": share_pretty,
                })

                # Accumulate owner totals
                owner_totals[name] = owner_totals.get(name, 0) + share_marlas
                owner_details.setdefault(name, []).append({
                    "khewat_no": kdata["no"],
                    "area_str": marlas_to_str(kdata["total_marlas"]),
                    "share_fraction": share_str,
                    "owner_share_str": share_pretty,
                })
                idx += 1

        detailed_result = {
            name: {
                "total_share_str": marlas_to_str(owner_totals[name]),
                "khewats": owner_details[name],
            }
            for name in owner_totals
        }

        return render_template("index.html", result=detailed_result)

    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download_pdf():
    data = request.form.get("pdf_data")
    if not data:
        return "No data provided", 400

    import json
    parsed = json.loads(data)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, "Land Share Report")
    y -= 30

    p.setFont("Helvetica", 10)
    for owner, details in parsed.items():
        if y < 100:
            p.showPage()
            y = height - 50
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, f"{owner} — Total Share: {details['total_share_str']}")
        y -= 20

        p.setFont("Helvetica", 10)
        for k in details["khewats"]:
            line = f"Khewat #{k['khewat_no']} | Area: {k['area_str']} | Share: {k['share_fraction']} → {k['owner_share_str']}"
            p.drawString(60, y, line)
            y -= 15

        y -= 15

    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="land_share_report.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)
