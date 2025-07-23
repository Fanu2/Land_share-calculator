from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from fractions import Fraction
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import re
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key in production
csrf = CSRFProtect(app)

# Constants
MARLAS_PER_KANAL = 20
KANALS_PER_KILA = 4
MARLAS_PER_KILA = MARLAS_PER_KANAL * KANALS_PER_KILA  # 80
SARSHAIS_PER_MARLA = 9

# Form for main inputs
class LandShareForm(FlaskForm):
    total_kanals = StringField('Total Kanals', validators=[DataRequired()])
    total_marlas = StringField('Total Marlas', validators=[DataRequired()])
    total_khewats = IntegerField('Total Khewats', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Calculate Shares')

def parse_fraction(frac_str: str) -> float:
    """Parse a fraction or decimal string to a float."""
    try:
        frac_str = frac_str.strip()
        if not frac_str:
            return 0.0
        if '/' in frac_str:
            num, denom = frac_str.split('/')
            return float(num) / float(denom)
        return float(frac_str)
    except (ValueError, ZeroDivisionError) as e:
        raise ValueError(f"Invalid fraction or number: {frac_str}. {str(e)}")

def area_to_marlas(kanals: float, marlas: float) -> float:
    """Convert kanals and marlas to total marlas."""
    if kanals < 0 or marlas < 0:
        raise ValueError("Kanals and marlas must be non-negative")
    return kanals * MARLAS_PER_KANAL + marlas

def format_land_units(total_marlas: float) -> dict:
    """Convert total marlas to kila, kanals, marlas, and sarshai."""
    if total_marlas < 0:
        raise ValueError("Total marlas cannot be negative")
    total_sarshai = round(total_marlas * SARSHAIS_PER_MARLA)

    kila = total_sarshai // (KANALS_PER_KILA * MARLAS_PER_KANAL * SARSHAIS_PER_MARLA)
    rem = total_sarshai % (KANALS_PER_KILA * MARLAS_PER_KANAL * SARSHAIS_PER_MARLA)
    kanal = rem // (MARLAS_PER_KANAL * SARSHAIS_PER_MARLA)
    rem = rem % (MARLAS_PER_KANAL * SARSHAIS_PER_MARLA)
    marla = rem // SARSHAIS_PER_MARLA
    sarshai = rem % SARSHAIS_PER_MARLA

    return {"kila": int(kila), "kanals": int(kanal), "marlas": int(marla), "sarshai": int(sarshai)}

@app.route("/", methods=["GET", "POST"])
def index():
    form = LandShareForm()
    result = None
    form_data = request.form if request.method == "POST" else {}

    if request.method == "POST" and form.validate_on_submit():
        try:
            # Parse total land
            total_kanals = parse_fraction(form.total_kanals.data)
            total_marlas = parse_fraction(form.total_marlas.data)
            total_land_marlas = area_to_marlas(total_kanals, total_marlas)

            # Parse khewats
            total_khewats = form.total_khewats.data
            khewats = {}
            for k in range(1, total_khewats + 1):
                k_kanals = parse_fraction(form_data.get(f"khewat_{k}_kanals", "0"))
                k_marlas = parse_fraction(form_data.get(f"khewat_{k}_marlas", "0"))
                owners_count = int(form_data.get(f"khewat_{k}_owners_count", "1"))
                khewat_total = area_to_marlas(k_kanals, k_marlas)
                khewats[k] = {
                    "no": k,
                    "total_marlas": khewat_total,
                    "area": format_land_units(khewat_total),
                    "owners": [],
                    "total_share_fraction": 0.0
                }
                # Parse owners for this khewat
                for o in range(1, owners_count + 1):
                    owner_name = form_data.get(f"khewat_{k}_owner_{o}_name", f"Owner{o}").strip()
                    remarks = form_data.get(f"khewat_{k}_owner_{o}_remarks", "").strip()
                    share_fraction = parse_fraction(form_data.get(f"khewat_{k}_owner_{o}_share", "0"))
                    owner_name = re.sub(r'[<>]', '', owner_name)  # Sanitize for XSS
                    if not owner_name:
                        owner_name = f"Owner{o}"
                    if share_fraction < 0:
                        raise ValueError(f"Share fraction for {owner_name} in Khewat {k} cannot be negative")
                    share_marlas = khewat_total * share_fraction
                    khewats[k]["owners"].append({
                        "name": owner_name,
                        "share_fraction": str(Fraction(share_fraction).limit_denominator()),
                        "share_marlas": share_marlas,
                        "share": format_land_units(share_marlas),
                        "remarks": remarks
                    })
                    khewats[k]["total_share_fraction"] += share_fraction

                # Validate khewat shares
                if abs(khewats[k]["total_share_fraction"] - 1.0) > 0.01:
                    flash(f"Total share fractions for Khewat {k} must sum to 1, got {khewats[k]['total_share_fraction']:.2f}.", "error")
                    return render_template("index.html", form=form, result=None, form_data=form_data)

            # Summarize owner-wise shares
            owners = {}
            for k, khewat in khewats.items():
                for owner in khewat["owners"]:
                    owner_name = owner["name"]
                    if owner_name not in owners:
                        owners[owner_name] = {
                            "khewats": {},
                            "total_share_marlas": 0.0,
                            "remarks": owner["remarks"]
                        }
                    owners[owner_name]["khewats"][k] = {
                        "share_fraction": owner["share_fraction"],
                        "share": owner["share"],
                        "khewat_area": khewat["area"]
                    }
                    owners[owner_name]["total_share_marlas"] += owner["share_marlas"]

            # Format owner totals
            for owner in owners.values():
                owner["total"] = format_land_units(owner["total_share_marlas"])

            # Validate total land
            total_share_marlas = sum(owner["total_share_marlas"] for owner in owners.values())
            if abs(total_share_marlas - total_land_marlas) > 0.01:
                flash("Total owner shares do not match total land area.", "error")
                return render_template("index.html", form=form, result=None, form_data=form_data)

            result = {
                "owners": owners,
                "khewats": khewats,
                "total_share": format_land_units(total_land_marlas)
            }

        except ValueError as e:
            flash(str(e), "error")
            return render_template("index.html", form=form, result=None, form_data=form_data)

    return render_template("index.html", form=form, result=result, form_data=form_data)

@app.route("/download", methods=["POST"])
def download_pdf():
    try:
        data = json.loads(request.form.get("pdf_data", "{}"))
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 50

        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, y, "Land Share Report")
        y -= 30

        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"Total Land: {data['total_share']['kila']} Kila, {data['total_share']['kanals']} Kanals, {data['total_share']['marlas']} Marlas, {data['total_share']['sarshai']} Sarshai")
        y -= 20

        for khewat_num, khewat in data["khewats"].items():
            if y < 100:
                p.showPage()
                y = height - 50
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, y, f"Khewat #{khewat_num}: {khewat['area']['kila']} Kila, {khewat['area']['kanals']} Kanals, {khewat['area']['marlas']} Marlas, {khewat['area']['sarshai']} Sarshai")
            y -= 20
            p.setFont("Helvetica", 10)
            p.drawString(60, y, "Owners:")
            y -= 15
            for owner in khewat["owners"]:
                line = f"{owner['name']} | Share: {owner['share_fraction']} | Area: {owner['share']['kila']} Kila, {owner['share']['kanals']} Kanals, {owner['share']['marlas']} Marlas, {owner['share']['sarshai']} Sarshai"
                if owner['remarks']:
                    line += f" | Remarks: {owner['remarks']}"
                p.drawString(70, y, line)
                y -= 15
            y -= 15

        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "Owner-wise Summary")
        y -= 20
        for owner, details in data["owners"].items():
            if y < 100:
                p.showPage()
                y = height - 50
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, y, f"{owner} — Total Share: {details['total']['kila']} Kila, {details['total']['kanals']} Kanals, {details['total']['marlas']} Marlas, {details['total']['sarshai']} Sarshai")
            y -= 20
            if details.get("remarks"):
                p.setFont("Helvetica-Oblique", 10)
                p.drawString(60, y, f"Remarks: {details['remarks']}")
                y -= 15
            p.setFont("Helvetica", 10)
            for khewat_num, share in details["khewats"].items():
                line = f"Khewat #{khewat_num}: Share {share['share_fraction']} | Area: {share['share']['kila']} Kila, {share['share']['kanals']} Kanals, {share['share']['marlas']} Marlas, {share['share']['sarshai']} Sarshai"
                p.drawString(60, y, line)
                y -= 15
            y -= 15

        p.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="land_share_report.pdf", mimetype="application/pdf")
    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "error")
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
