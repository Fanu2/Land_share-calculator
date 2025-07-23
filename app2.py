from flask import Flask, render_template, request
from fractions import Fraction

app = Flask(__name__)

# Constants
MARLAS_PER_KANAL = 20
KANALS_PER_KILA = 4
MARLAS_PER_KILA = MARLAS_PER_KANAL * KANALS_PER_KILA  # 80
SARSHAIS_PER_MARLA = 9

def parse_fraction(frac_str):
    try:
        if '/' in frac_str:
            return float(Fraction(frac_str))
        else:
            return float(frac_str)
    except:
        return 0.0

def format_area(marlas_float):
    # Convert total marlas (including fractions) to Kila, Kanal, Marla, Sarshai
    total_sarshai = round(marlas_float * SARSHAIS_PER_MARLA)  # convert marlas to sarshai for precision

    kila = total_sarshai // (KANALS_PER_KILA * MARLAS_PER_KANAL * SARSHAIS_PER_MARLA)
    rem = total_sarshai % (KANALS_PER_KILA * MARLAS_PER_KANAL * SARSHAIS_PER_MARLA)

    kanal = rem // (MARLAS_PER_KANAL * SARSHAIS_PER_MARLA)
    rem = rem % (MARLAS_PER_KANAL * SARSHAIS_PER_MARLA)

    marla = rem // SARSHAIS_PER_MARLA
    sarshai = rem % SARSHAIS_PER_MARLA

    parts = []
    if kila > 0:
        parts.append(f"{kila} Kila")
    if kanal > 0:
        parts.append(f"{kanal} Kanal")
    if marla > 0:
        parts.append(f"{marla} Marla")
    if sarshai > 0:
        parts.append(f"{sarshai} Sarshai")

    return ", ".join(parts) if parts else "0 Marla"

@app.route("/", methods=["GET", "POST"])
def index():
    result = None

    if request.method == "POST":
        owners = {}
        # Collect form data keys and parse owners & khewats
        for key, val in request.form.items():
            # key example: owner0_name, owner0_khewat0_no, owner0_khewat0_kanals ...
            if key.startswith("owner") and val.strip():
                parts = key.split('_')
                owner_id = parts[0]
                if owner_id not in owners:
                    owners[owner_id] = {"name": None, "khewats": []}

                if len(parts) == 2 and parts[1] == "name":
                    owners[owner_id]["name"] = val.strip()

        # Parse khewats for each owner
        for owner_id in owners:
            khewat_index = 0
            while True:
                base = f"{owner_id}_khewat{khewat_index}_no"
                if base not in request.form:
                    break  # no more khewats for this owner

                # Gather khewat details
                khewat_no = request.form.get(base, "").strip()
                kanals = request.form.get(f"{owner_id}_khewat{khewat_index}_kanals", "0").strip()
                marlas = request.form.get(f"{owner_id}_khewat{khewat_index}_marlas", "0").strip()
                share_frac_str = request.form.get(f"{owner_id}_khewat{khewat_index}_share", "0").strip()

                try:
                    kanals = int(kanals)
                except:
                    kanals = 0
                try:
                    marlas = int(marlas)
                except:
                    marlas = 0

                # Calculate total marlas for this khewat
                total_marlas = kanals * MARLAS_PER_KANAL + marlas
                share_frac = parse_fraction(share_frac_str)

                owners[owner_id]["khewats"].append({
                    "khewat_no": khewat_no,
                    "area_str": format_area(total_marlas),
                    "share_fraction": share_frac_str,
                    "raw_marlas": total_marlas  # store raw marlas for calculation
                })

                khewat_index += 1

        # Calculate owner's total shares
        final_result = {}
        for owner_data in owners.values():
            total_owner_marlas = 0
            for k in owner_data["khewats"]:
                share = parse_fraction(k["share_fraction"])
                owner_share_marlas = share * k["raw_marlas"]
                total_owner_marlas += owner_share_marlas
                k["owner_share_marlas"] = owner_share_marlas
                k["owner_share_str"] = format_area(owner_share_marlas)

            final_result[owner_data["name"]] = {
                "khewats": owner_data["khewats"],
                "total_share_str": format_area(total_owner_marlas),
                "total_marlas": total_owner_marlas
            }

        result = final_result

    return render_template("index.html", result=result)

if __name__ == "__main__":
    app.run(debug=True)
