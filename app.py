import streamlit as st
from streamlit_gsheets import GSheetsConnection
import sqlite3
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

# --- KONFIGURÁCIÓ ---
st.set_page_config(page_title="V-Tel GSM Szerviz", layout="wide")

# Kapcsolódás a Google Táblázathoz
conn = st.connection("gsheets", type=GSheetsConnection)

# --- KOMPAKT STÍLUS BEÁLLÍTÁSA ---
st.markdown("""
    <style>
    /* Gombok mérete és szoros elhelyezése */
    div.stButton > button, div.stDownloadButton > button {
        height: 2.8em;
        width: 100%;
        border-radius: 6px;
        font-weight: 500;
        margin: 0px;
    }
    /* Oszlopok közötti rés csökkentése a műveleti panelnél */
    [data-testid="column"] {
        padding-left: 5px !important;
        padding-right: 5px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ADATBÁZIS ---
def init_db():
    conn = sqlite3.connect("szerviz.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS telefonok 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       ugyfel TEXT, email TEXT, tipus TEXT, imei TEXT, hiba TEXT, statusz TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- ÉKEZETKEZELŐ (PDF-HEZ) ---
def encode_hu(text):
    if not isinstance(text, str): text = str(text)
    try: return text.encode('cp1250').decode('latin-1')
    except: return text

# --- PDF OSZTÁLY ---
class VTelPDF(FPDF):
    def header(self):
        self.set_fill_color(255, 105, 180) 
        self.rect(0, 0, 210, 45, 'F')
        self.set_y(12)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 28)
        self.cell(0, 15, encode_hu("V-Tel GSM"), ln=True, align='C')
        self.set_font("Arial", '', 11)
        self.cell(0, 5, encode_hu("Dunaújváros, Dózsa György út 30."), ln=True, align='C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", 'I', 9)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, encode_hu(f"V-Tel GSM - {datetime.now().year}"), 0, 0, 'C')

def create_pdf(row):
    pdf = VTelPDF()
    pdf.add_page()
    pdf.set_y(55)
    pdf.set_text_color(255, 20, 147)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, encode_hu(f"SZERVIZ MUNKALAP: #{row[0]}"), ln=True, align='C')
    pdf.ln(10)
    labels = ["Ügyfél neve:", "Email cím:", "Készülék típusa:", "IMEI szám:", "Hiba leírása:", "Státusz:"]
    pdf.set_x(15)
    for i in range(1, 7):
        fill = i % 2 == 0
        pdf.set_fill_color(255, 240, 245)
        pdf.set_font("Arial", 'B', 11)
        pdf.set_text_color(255, 20, 147)
        pdf.cell(50, 12, encode_hu(labels[i-1]), 'B', 0, 'L', fill=fill)
        pdf.set_font("Arial", '', 11)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(130, 12, encode_hu(str(row[i])), 'B', 1, 'L', fill=fill)
        pdf.set_x(15)
    pdf.ln(15)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 10, encode_hu("Az elveszett adatokért nem vállalunk felelősséget."), ln=True, align='C')
    fname = f"munkalap_{row[0]}.pdf"
    pdf.output(fname)
    return fname

# --- FŐOLDAL ---
st.title("V-Tel GSM Szervizkezelő")

# 1. ÚJ SZERVIZ GOMB (Balra)
if "show_form" not in st.session_state: st.session_state.show_form = False
col_top1, _ = st.columns([1, 2])
with col_top1:
    if st.button("➕ Új szerviz rögzítése"):
        st.session_state.show_form = not st.session_state.show_form

if st.session_state.show_form:
    with st.form("uj_szerviz_form", clear_on_submit=True):
        st.subheader("Adatbevitel")
        c1, c2 = st.columns(2)
        with c1:
            u_n = st.text_input("Ügyfél neve"); u_e = st.text_input("Email cím")
        with c2:
            u_t = st.text_input("Készülék típusa"); u_i = st.text_input("IMEI szám")
        u_h = st.text_area("Hiba leírása")
        u_s = st.selectbox("Állapot", ["Alkatrészre vár", "Folyamatban", "Elkészült", "Átvéve"])
        if st.form_submit_button("Mentés"):
            if u_n and u_t:
                conn.execute("INSERT INTO telefonok (ugyfel, email, tipus, imei, hiba, statusz) VALUES (?,?,?,?,?,?)", (u_n, u_e, u_t, u_i, u_h, u_s))
                conn.commit(); st.success("Sikeresen rögzítve!"); st.session_state.show_form = False; st.rerun()

st.divider()

# 2. ADATBÁZIS ÉS KERESŐ
df_all = pd.read_sql_query("SELECT * FROM telefonok", conn)
st.subheader("Szerviz Napló")
kereses = st.text_input("🔍 Keresés:", placeholder="Név, IMEI vagy Email...")

if not df_all.empty:
    df_display = df_all[df_all['ugyfel'].str.contains(kereses, case=False, na=False) | 
                        df_all['imei'].str.contains(kereses, case=False, na=False) |
                        df_all['email'].str.contains(kereses, case=False, na=False)] if kereses else df_all

    edited_df = st.data_editor(df_display, use_container_width=True, hide_index=True)
    if st.button("Módosítások mentése"):
        for _, row in edited_df.iterrows():
            conn.execute("UPDATE telefonok SET ugyfel=?, email=?, tipus=?, imei=?, hiba=?, statusz=? WHERE id=?", 
                         (row['ugyfel'], row['email'], row['tipus'], row['imei'], row['hiba'], row['statusz'], row['id']))
        conn.commit(); st.success("Adatbázis frissítve!")

    st.divider()
    
    # 3. MŰVELETI PANEL - SZOROSAN EGYMÁS MELLÉ AZ ID ALÁ
    st.subheader("Műveletek")
    
    # Két fő oszlop: a bal oldaliban lesz az ID és alatta a gombok
    main_col1, _ = st.columns([2, 2])
    
    with main_col1:
        # ID Választó fent
        sel_id = st.selectbox("Munkalap ID kiválasztása:", df_display['id'].tolist())
        target_data = df_display[df_display['id'] == sel_id].iloc[0].tolist()
        
        # Gombok szorosan egymás mellett közvetlenül az ID alatt
        btn_c1, btn_c2, btn_c3 = st.columns(3)
        
        with btn_c1:
            fn = create_pdf(target_data)
            with open(fn, "rb") as f:
                st.download_button("📄 PDF letöltése", f, file_name=fn)
        
        with btn_c2:
            if st.button("🚀 Email küldése"):
                S_EMAIL = st.secrets["email_settings"]["sender_email"]; S_PASS = st.secrets["email_settings"]["app_password"]
                if "@" in str(target_data[2]):
                    try:
                        pdf_file = create_pdf(target_data)
                        msg = MIMEMultipart()
                        msg['From'], msg['To'] = S_EMAIL, target_data[2]
                        msg['Subject'] = encode_hu(f"V-Tel GSM Munkalap - {target_data[1]}")
                        msg.attach(MIMEText("Mellékelten küldjük a munkalapot. V-Tel GSM", 'plain'))
                        with open(pdf_file, "rb") as f:
                            part = MIMEBase("application", "octet-stream"); part.set_payload(f.read())
                            encoders.encode_base64(part); part.add_header("Content-Disposition", f"attachment; filename={pdf_file}")
                            msg.attach(part)
                        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                        server.login(S_EMAIL, S_PASS); server.send_message(msg); server.quit()
                        st.success("Küldve!")
                    except Exception as e: st.error(f"Hiba: {e}")
                else: st.error("Nincs email!")
        
        with btn_c3:
            if st.button("🗑️ Munkalap törlése", type="primary"):
                conn.execute("DELETE FROM telefonok WHERE id=?", (sel_id,))
                conn.commit(); st.rerun()
else:
    st.info("Nincs adat.")
