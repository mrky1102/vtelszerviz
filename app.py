import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- KONFIGURÁCIÓ ---
st.set_page_config(page_title="V-Tel GSM Szerviz", layout="wide")

# Google Sheets kapcsolat
conn = st.connection("gsheets", type=GSheetsConnection)

# --- STÍLUS ---
st.markdown("""
    <style>
    div.stButton > button, div.stDownloadButton > button {
        height: 3em; width: 100%; border-radius: 8px; font-weight: 500;
    }
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- SEGÉDFÜGGVÉNYEK ---
def encode_hu(text):
    if not isinstance(text, str): text = str(text)
    try: return text.encode('cp1250').decode('latin-1')
    except: return text

class VTelPDF(FPDF):
    def header(self):
        self.set_fill_color(255, 105, 180); self.rect(0, 0, 210, 45, 'F')
        self.set_y(12); self.set_text_color(255, 255, 255); self.set_font("Arial", 'B', 28)
        self.cell(0, 15, encode_hu("V-Tel GSM"), ln=True, align='C')
        self.set_font("Arial", '', 11); self.cell(0, 5, encode_hu("Dunaújváros, Dózsa György út 30."), ln=True, align='C')
    def footer(self):
        self.set_y(-15); self.set_font("Arial", 'I', 9); self.set_text_color(150, 150, 150)
        self.cell(0, 10, encode_hu(f"V-Tel GSM - {datetime.now().year}"), 0, 0, 'C')

def create_pdf(row):
    pdf = VTelPDF(); pdf.add_page(); pdf.set_y(55)
    pdf.set_text_color(255, 20, 147); pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, encode_hu(f"SZERVIZ MUNKALAP: #{row['id']}"), ln=True, align='C')
    pdf.ln(10)
    labels = {"ugyfel": "Ügyfél neve:", "email": "Email cím:", "tipus": "Készülék típusa:", 
              "imei": "IMEI szám:", "hiba": "Hiba leírása:", "statusz": "Státusz:"}
    for col, label in labels.items():
        pdf.set_x(15); pdf.set_fill_color(255, 240, 245); pdf.set_font("Arial", 'B', 11)
        pdf.set_text_color(255, 20, 147); pdf.cell(50, 12, encode_hu(label), 'B', 0, 'L', fill=True)
        pdf.set_font("Arial", '', 11); pdf.set_text_color(40, 40, 40)
        pdf.cell(130, 12, encode_hu(str(row[col])), 'B', 1, 'L', fill=True)
    pdf.ln(15); pdf.set_font("Arial", 'I', 10); pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 10, encode_hu("Az elveszett adatokért nem vállalunk felelősséget."), ln=True, align='C')
    fname = f"munkalap_{row['id']}.pdf"; pdf.output(fname); return fname

# --- ADATOK BETÖLTÉSE ---
try:
    df = conn.read(ttl=0)
    # Biztonsági mentés: minden oszlopnevet kisbetűssé alakítunk
    df.columns = [str(c).lower() for c in df.columns]
    if not df.empty:
        df['id'] = pd.to_numeric(df['id'], errors='coerce')
except Exception as e:
    st.error("Hiba a táblázat beolvasásakor. Ellenőrizze a Secrets-t!")
    df = pd.DataFrame(columns=['id', 'ugyfel', 'email', 'tipus', 'imei', 'hiba', 'statusz'])

# --- FŐOLDAL ---
st.title("V-Tel GSM Szervizkezelő")

if "show_form" not in st.session_state: st.session_state.show_form = False
col_top1, _ = st.columns([1, 2])
with col_top1:
    if st.button("➕ Új szerviz rögzítése"): st.session_state.show_form = not st.session_state.show_form

if st.session_state.show_form:
    with st.form("uj_szerviz_form", clear_on_submit=True):
        st.subheader("Adatbevitel")
        c1, c2 = st.columns(2)
        with c1: u_n = st.text_input("Ügyfél neve"); u_e = st.text_input("Email cím")
        with c2: u_t = st.text_input("Készülék típusa"); u_i = st.text_input("IMEI szám")
        u_h = st.text_area("Hiba leírása")
        u_s = st.selectbox("Állapot", ["Alkatrészre vár", "Folyamatban", "Elkészült", "Átvéve"])
        
        if st.form_submit_button("Mentés"):
            if u_n and u_t:
                new_id = int(df['id'].max()) + 1 if not df.empty and not df['id'].isnull().all() else 1
                new_row = pd.DataFrame([{"id": new_id, "ugyfel": u_n, "email": u_e, "tipus": u_t, "imei": u_i, "hiba": u_h, "statusz": u_s}])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                try:
                    conn.update(data=updated_df)
                    st.success("Sikeres mentés!")
                    st.session_state.show_form = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Hiba az írásnál! Állítsa a táblázatot SZERKESZTŐ módba! {e}")

st.divider()

# 2. ADATBÁZIS ÉS KERESŐ
st.subheader("Szerviz Napló")
kereses = st.text_input("🔍 Keresés:", placeholder="Név, IMEI vagy Email...")

if not df.empty:
    df_display = df[df.apply(lambda row: row.astype(str).str.contains(kereses, case=False, na=False).any(), axis=1)] if kereses else df
    edited_df = st.data_editor(df_display, use_container_width=True, hide_index=True)
    
    if st.button("Módosítások mentése"):
        for index, row in edited_df.iterrows():
            df.loc[df['id'] == row['id']] = row
        conn.update(data=df)
        st.success("Adatok szinkronizálva!")
        st.rerun()

    st.divider()
    
    st.subheader("Műveletek")
    main_col1, _ = st.columns([2, 2])
    with main_col1:
        # ID-k listája a választóhoz
        valid_ids = df_display['id'].dropna().tolist()
        if valid_ids:
            sel_id = st.selectbox("Munkalap választása (ID):", valid_ids)
            target_row = df_display[df_display['id'] == sel_id].iloc[0]
            
            btn_c1, btn_c2, btn_c3 = st.columns(3)
            with btn_c1:
                try:
                    fn = create_pdf(target_row)
                    with open(fn, "rb") as f: st.download_button("📄 PDF", f, file_name=fn)
                except: st.error("PDF hiba.")
            
            with btn_c2:
                if st.button("🚀 Email"):
                    try:
                        if "email_settings" in st.secrets:
                            S_EMAIL = st.secrets["email_settings"]["sender_email"]
                            S_PASS = st.secrets["email_settings"]["app_password"]
                            if "@" in str(target_row['email']):
                                pdf_file = create_pdf(target_row)
                                msg = MIMEMultipart()
                                msg['From'], msg['To'] = S_EMAIL, target_row['email']
                                msg['Subject'] = encode_hu(f"Munkalap - {target_row['ugyfel']}")
                                msg.attach(MIMEText("Mellékelten küldjük a szervizlapot.", 'plain'))
                                with open(pdf_file, "rb") as f:
                                    part = MIMEBase("application", "octet-stream"); part.set_payload(f.read())
                                    encoders.encode_base64(part); part.add_header("Content-Disposition", f"attachment; filename={pdf_file}")
                                    msg.attach(part)
                                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                                server.login(S_EMAIL, S_PASS); server.send_message(msg); server.quit()
                                st.success("Küldve!")
                            else: st.error("Nincs email.")
                        else: st.error("Hiányzó Secrets!")
                    except Exception as e: st.error(f"Email hiba: {e}")
            
            with btn_c3:
                if st.button("🗑️ Törlés", type="primary"):
                    df = df[df['id'] != sel_id]
                    conn.update(data=df)
                    st.rerun()
else:
    st.info("Nincs adat.")
