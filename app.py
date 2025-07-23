from flask import Flask, render_template, request
from fractions import Fraction

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    result = ""
    if request.method == 'POST':
        try:
            khewat_no = request.form.get('khewat', '')
            total_kanals = int(request.form.get('kanals', 0))
            total_marlas = int(request.form.get('marlas', 0))
            total_marlas_full = total_kanals * 20 + total_marlas

            result += f"Khewat No: {khewat_no}<br>"
            result += f"Total Area: {total_kanals} Kanals, {total_marlas} Marlas ({total_marlas_full} Marlas)<br><br>"

            total_owner_marlas = 0
            rows = []
            for i in range(10):
                name = request.form.get(f'name{i}', '').strip()
                share = request.form.get(f'share{i}', '').strip()
                remarks = request.form.get(f'remarks{i}', '').strip()
                if name and share:
                    share_fraction = Fraction(share)
                    owner_marlas = total_marlas_full * share_fraction
                    total_owner_marlas += owner_marlas
                    killas = int(owner_marlas // 160)
                    rem = owner_marlas % 160
                    kanals = int(rem // 20)
                    rem = rem % 20
                    marlas = int(rem)
                    sarshai = round((rem - marlas) * 9)
                    area_str = f"{killas}K-{kanals}K-{marlas}M" + (f"-{sarshai}S" if sarshai else "")
                    rows.append((name, str(share_fraction), area_str, remarks))

            for row in rows:
                result += f"{row[0]} — {row[1]} — {row[2]} — {row[3]}<br>"

        except Exception as e:
            result = f"Error: {str(e)}"
    return render_template("index.html", result=result)

if __name__ == '__main__':
    app.run()

