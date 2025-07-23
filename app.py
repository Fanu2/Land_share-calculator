import streamlit as st
import pandas as pd
import io
from fractions import Fraction
from openpyxl import Workbook

# Constants
KANAL_TO_MARLA = 20
MARLA_TO_SARSAI = 9
KANAL_TO_ACRE = 0.125
KILAS_IN_KANAL = 8

st.set_page_config(page_title="Land Share Calculator", layout="wide")
st.title("🧮 Punjab Rural Land Share Calculator")

# Area breakdown utility
def breakdown_area(share_kanal):
    kila = int(share_kanal // KILAS_IN_KANAL)
    kanal_remain = share_kanal % KILAS_IN_KANAL
    kanal = int(kanal_remain)
    marla_fraction = (kanal_remain - kanal) * KANAL_TO_MARLA
    marla = int(marla_fraction)
    sarshai = round((marla_fraction - marla) * MARLA_TO_SARSAI)
    return kila, kanal, marla, sarshai

# Excel exporter
def to_excel_bytes(df1, df2):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df1.to_excel(writer, index=False, sheet_name='Detailed Output')
    df2.to_excel(writer, index=False, sheet_name='Owner Summary')
    writer.close()
    output.seek(0)
    return output

# Input mode
input_method = st.radio("Choose input method", ["Manual Entry", "Upload Excel File"])
data_rows = []
df_uploaded = pd.DataFrame()

if input_method == "Upload Excel File":
    uploaded_file = st.file_uploader("Upload your Excel file (.xlsx)", type=["xlsx"])
    if uploaded_file:
        df_uploaded = pd.read_excel(uploaded_file)
        st.dataframe(df_uploaded)

else:
    st.subheader("Manual Land Entry")
    num_rows = st.number_input("Number of entries", min_value=1, max_value=50, value=3)
    for i in range(num_rows):
        cols = st.columns(7)
        with cols[0]: khewat = st.text_input(f"Khewat No {i+1}", key=f"khewat_{i}")
        with cols[1]: marba = st.text_input(f"Marba No {i+1}", key=f"marba_{i}")
        with cols[2]: killa = st.text_input(f"Killa No {i+1}", key=f"killa_{i}")
        with cols[3]: kanal = st.number_input(f"Total Area (Kanal) {i+1}", 0.0, 1000.0, step=0.1, key=f"kanal_{i}")
        with cols[4]: marla = st.number_input(f"Total Area (Marla) {i+1}", 0.0, 19.0, step=0.1, key=f"marla_{i}")
        with cols[5]: owner = st.text_input(f"Owner Name {i+1}", key=f"owner_{i}")
        with cols[6]: share_frac = st.text_input(f"Share Fraction {i+1} (e.g. 1/2)", key=f"share_{i}")

        if share_frac:
            try:
                frac = float(Fraction(share_frac))
                area_kanal = kanal + (marla / KANAL_TO_MARLA)
                share_area = area_kanal * frac
                kila, kanal_out, marla_out, sarshai_out = breakdown_area(share_area)
                data_rows.append({
                    "Khewat": khewat,
                    "Marba": marba,
                    "Killa": killa,
                    "Owner": owner,
                    "Share Fraction": share_frac,
                    "Share Area (Kanal)": share_area,
                    "Kila": kila,
                    "Kanal": kanal_out,
                    "Marla": marla_out,
                    "Sarshai": sarshai_out,
                    "Acre": round(share_area * KANAL_TO_ACRE, 3)
                })
            except Exception as e:
                st.error(f"Invalid fraction in row {i+1}: {e}")

# Uploaded file logic
if not df_uploaded.empty:
    for idx, row in df_uploaded.iterrows():
        try:
            kanal = float(row["Total Area (Kanals)"])
            marla = float(row["Total Area (Marlas)"])
            share_frac = str(row["Share Fraction"])
            frac = float(Fraction(share_frac))
            area_kanal = kanal + (marla / KANAL_TO_MARLA)
            share_area = area_kanal * frac
            kila, kanal_out, marla_out, sarshai_out = breakdown_area(share_area)
            data_rows.append({
                "Khewat": row["Khewat No"],
                "Marba": row["Marba No"],
                "Killa": row["Killa No"],
                "Owner": row["Owner Name"],
                "Share Fraction": share_frac,
                "Share Area (Kanal)": share_area,
                "Kila": kila,
                "Kanal": kanal_out,
                "Marla": marla_out,
                "Sarshai": sarshai_out,
                "Acre": round(share_area * KANAL_TO_ACRE, 3)
            })
        except Exception as e:
            st.error(f"Error in row {idx+1}: {e}")

# Output section
if data_rows:
    df = pd.DataFrame(data_rows)

    st.subheader("🔍 Individual Share Calculations")
    st.dataframe(df)

    st.subheader("📊 Owner-wise Summary")
    summary = df.groupby("Owner")["Share Area (Kanal)"].sum().reset_index()
    summary[["Kila", "Kanal", "Marla", "Sarshai", "Acre"]] = summary["Share Area (Kanal)"].apply(
        lambda x: pd.Series(list(breakdown_area(x)) + [round(x * KANAL_TO_ACRE, 3)])
    )
    st.dataframe(summary)

    # Download button
    xlsx = to_excel_bytes(df, summary)
    st.download_button("📥 Download Results (Excel)", data=xlsx, file_name="land_share_results.xlsx")
