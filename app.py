import streamlit as st
import gspread
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import unicodedata
import os
import base64
import pytz

# --- KONFIGURACE ---
st.set_page_config(layout="wide")
st.markdown("""<style>.stApp { background-color: #121212; color: #e0e0e0; } h1, h2, h3, div, p { color: #e0e0e0 !important; } .block-container { max-width: 1100px !important; padding: 2rem !important; } .stExpander { border: 1px solid #333 !important; margin-top: -5px !important; border-radius: 0 0 8px 8px !important; } .stExpanderContent { background-color: #1a1a1a !important; padding: 20px !important; } .lb-row { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid #333; color: #e0e0e0; } .lb-rank { font-size: 20px; font-weight: bold; width: 40px; } .lb-name { flex-grow: 1; font-weight: 500; } .lb-points { font-weight: bold; color: #4CAF50; } [data-testid="stPopover"] { display: none; } @media (max-width: 800px) { [data-testid="stPopover"] { display: flex !important; position: fixed; bottom: 20px; left: 20px; z-index: 1000; } button[data-testid="stBaseButton-secondary"] { width: 50px !important; height: 50px !important; border-radius: 50% !important; padding: 0 !important; background-color: #4CAF50 !important; box-shadow: 0 4px 10px rgba(0,0,0,0.5); } }</style>""", unsafe_allow_html=True)
def get_gspread_client():
    return gspread.service_account_from_dict(st.secrets["gcp"])

def get_image_as_base64(path):
    if not os.path.exists(path): return None
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

@st.cache_data(ttl=60)
def load_data_frames():
    client = get_gspread_client()
    sh = client.open("MS2026_Tipovacka")
    return pd.DataFrame(sh.worksheet("Zápasy").get_all_records()), \
           pd.DataFrame(sh.worksheet("Uživatelé").get_all_records()), \
           pd.DataFrame(sh.worksheet("Tipy").get_all_records()), \
           pd.DataFrame(sh.worksheet("Soupisky").get_all_records())

df_zapas, df_uzivatele, df_tipy, df_soupisky = load_data_frames()
df_zapas['DateTime'] = pd.to_datetime(df_zapas['Datum'] + ' ' + df_zapas['Cas'], format='%d.%m.%Y %H:%M')
df_soupisky['Tým_Clean'] = df_soupisky['Tým'].astype(str).str.strip().str.lower()

# --- FUNKCE PRO VÝPOČET (Musí být před použitím) ---
def remove_accents(input_str):
    if not isinstance(input_str, str): return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

def get_base_body(row, z):
    skore_d = int(z['Skore_D']) if str(z['Skore_D']).isdigit() else 0
    skore_h = int(z['Skore_H']) if str(z['Skore_H']).isdigit() else 0
    tip_d = int(row.get('Tip_D', 0)) if str(row.get('Tip_D', 0)).isdigit() else 0
    tip_h = int(row.get('Tip_H', 0)) if str(row.get('Tip_H', 0)).isdigit() else 0
    body = 0
    if (tip_d == skore_d and tip_h == skore_h):
        body += 3
        if skore_d == 0 and skore_h == 0: body += 1
    elif ((tip_d > tip_h and skore_d > skore_h) or (tip_d < tip_h and skore_h > skore_d) or (tip_d == tip_h and skore_d == skore_h)):
        body += 1
    if not (skore_d == 0 and skore_h == 0) and "Střelec" in z and str(z['Střelec']).strip():
        skutecni_strelci = [remove_accents(s.strip()) for s in str(z['Střelec']).split(",")]
        surovy_tip = str(row.get('Střelec', '')).split("(")[0]
        if remove_accents(surovy_tip.strip()) in skutecni_strelci: body += 1
    return body

PARY = {"Terezka": "Vojtin", "Vojtin": "Terezka", "Mladej Tono": "Míša", "Míša": "Mladej Tono", "Lukáš": "Kačaba", "Kačaba": "Lukáš", "Starší Tono":"Džáma", "Džáma":"Starší Tono"}

def calc_body(row):
    z = df_zapas[df_zapas['ID'] == int(row['ID_Zapasu'])]
    if z.empty: return 0
    z = z.iloc[0]
    if str(z.get('Skore_D', '')).strip() in ["", "nan", "None"]: return 0
    body = get_base_body(row, z)
    if int(row['ID_Zapasu']) == 25:
        partner = PARY.get(row['Jméno'])
        if partner:
            tip_partnera = df_tipy[(df_tipy['ID_Zapasu'] == 25) & (df_tipy['Jméno'] == partner)]
            if not tip_partnera.empty: body += get_base_body(tip_partnera.iloc[0], z)
    return body

df_tipy['ID_Zapasu'] = pd.to_numeric(df_tipy['ID_Zapasu'], errors='coerce')
df_tipy['Body'] = df_tipy.apply(calc_body, axis=1)

# --- QUERY PARAM ---
query_user = st.query_params.get("user")
if query_user and query_user in df_uzivatele["Jméno"].tolist():
    st.session_state.jmeno_hrace = query_user
    st.query_params.clear()
    st.rerun()

FOTKY_UZIVATELU = {"Vojtin": "static/images/vojtin.jpg", "Terezka": "static/images/terezka.jpg", "Kačaba": "static/images/kacaba.jpg", "Lukáš": "static/images/lukas.jpg", "Mladej Tono": "static/images/mladejtono.jpg", "Míša": "static/images/misa.jpg", "Džáma":  "static/images/dzama.jpg", "Starší Tono": "static/images/starsitono.jpg"}

# --- PŘIHLAŠOVACÍ BLOK ---
if 'jmeno_hrace' not in st.session_state:
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'>Kdo si právě tipuje?</h1>", unsafe_allow_html=True)

    # --- PŘIDANÝ POPOVER PRO MOBILNÍ ZOBRAZENÍ POŘADÍ ---
    with st.popover("📊 Průběžné pořadí"):
        st.subheader("🏆 Aktuální pořadí")
        lb = df_tipy.groupby('Jméno')['Body'].sum().sort_values(ascending=False).reset_index()
        for i, row in lb.iterrows():
            medal = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "👤")
            st.markdown(f'''
                <div class="lb-row">
                    <div class="lb-rank">{medal}</div>
                    <div class="lb-name">{row["Jméno"]}</div>
                    <div class="lb-points">{int(row["Body"])} b</div>
                </div>
            ''', unsafe_allow_html=True)
    # ---------------------------------------------------

    c_p1, c_p2 = st.columns([2, 1])
    with c_p1:
        uzivatele_list = df_uzivatele["Jméno"].tolist()
        st.markdown("<style>[data-testid='column'] { padding-left: 2px !important; padding-right: 2px !important; }</style>", unsafe_allow_html=True)
        for i in range(0, len(uzivatele_list), 4):
            chunk = uzivatele_list[i:i+4]
            cols = st.columns([1, 1, 1, 1, 1, 1, 1])
            col_indices = [0, 2, 4, 6]
            for j, name in enumerate(chunk):
                with cols[col_indices[j]]:
                    img_path = FOTKY_UZIVATELU.get(name, FOTKY_UZIVATELU.get("Výchozí", ""))
                    img_base64 = get_image_as_base64(img_path)
                    if img_base64:
                        st.markdown(f'<div style="text-align: center; margin-bottom: 5px;"><a href="?user={name}" style="text-decoration: none;"><img src="data:image/jpeg;base64,{img_base64}" style="width: 100%; max-width: 80px; aspect-ratio: 1/1; border-radius: 8px; border: 2px solid #333; cursor: pointer; object-fit: cover; display: block; margin: 0 auto;"><b style="color: white; font-size: 0.75em; display: block; margin-top: 2px;">{name}</b></a></div>', unsafe_allow_html=True)
    st.stop()

# --- ZBYTEK APLIKACE ---


def get_flag_html(country_name):
    iso_codes = {"Česko": "cz", "Slovensko": "sk", "Jižní Korea": "kr", "Německo": "de", "Francie": "fr", "Anglie": "gb-eng", "Španělsko": "es", "Itálie": "it", "Brazílie": "br", "Argentina": "ar", "Mexiko": "mx", "Kanada": "ca", "Bosna a Hercegovina": "ba", "USA": "us", "Paraguay": "py", "Katar": "qa", "Švýcarsko": "ch", "Maroko": "ma", "Jihoafrická republika": "za", "Jar": "za", "Haiti": "ht", "Skotsko": "gb-sct", "Austrálie": "au", "Turecko": "tr", "Curacao": "cw", "Japonsko": "jp", "Nizozemsko": "nl", "Pobřeží slonoviny": "ci", "Ekvádor": "ec", "Švédsko": "se", "Tunisko": "tn", "Belgie": "be", "Egypt": "eg", "Kapverdy": "cv", "Saúdská Arábie": "sa", "Uruguay": "uy", "Írán": "ir", "Nový Zéland": "nz", "Senegal": "sn", "Irák": "iq", "Norsko": "no", "Alžírsko": "dz", "Rakousko": "at", "Jordánsko": "jo", "Portugalsko": "pt", "DR Kongo": "cd", "Chorvatsko": "hr", "Ghana": "gh", "Panama": "pa", "Uzbekistán": "uz", "Kolumbie": "co"}
    iso = "xx"
    for name, code in iso_codes.items():
        if name.lower() in str(country_name).lower(): iso = code; break
    return f'<img src="https://flagcdn.com/24x18/{iso}.png" style="width: 24px; height: 18px; vertical-align: middle; border-radius: 2px;">'

def get_user_color(name):
    color_map = {"Vojtin": "#1EC9B2", "Terezka": "#C047C0", "Lukáš": "#6C70B3"}
    if name not in color_map:
        hash_val = int(hashlib.md5(name.encode()).hexdigest(), 16)
        return f"#{hash_val % 0xFFFFFF:06x}"
    return color_map[name]

def get_pozice_label(row):
    p = str(row.get('Pozice', '')).strip()
    if p in ["", "nan", "None"]:
        val = str(row.get('Pozice_import', '')).strip()
        if "GK" in val: return "B"
        if "DF" in val: return "O"
        if "MF" in val: return "Z"
        if "FW" in val: return "ÚT"
        return "" 
    return p

st.markdown("""<div style="background: #1a1a1a; padding: 15px; border-radius: 12px; border: 1px solid #333; margin: 0 auto 20px auto; max-width: 1100px; text-align: center;"><h2 style="margin: 0; color: #4CAF50 !important;">Tipovačka MS 2026 🏆</h2></div>""", unsafe_allow_html=True)

with st.popover("📊"):
    st.subheader("🏆 Aktuální pořadí")
    lb = df_tipy.groupby('Jméno')['Body'].sum().sort_values(ascending=False).reset_index()
    for i, row in lb.iterrows():
        medal = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "👤")
        st.markdown(f'<div class="lb-row"><div class="lb-rank">{medal}</div><div class="lb-name">{row["Jméno"]}</div><div class="lb-points">{int(row["Body"])} b</div></div>', unsafe_allow_html=True)

col_main, col_side = st.columns([2.5, 1])
with col_main:
    mask_dohrane = df_zapas['Skore_D'].notna() & (df_zapas['Skore_D'].astype(str) != "") & (df_zapas['Skore_D'].astype(str) != "nan")
    df_dohrane = df_zapas[mask_dohrane].sort_values('DateTime', ascending=False)
    df_nedohrane = df_zapas[~mask_dohrane].sort_values('DateTime', ascending=True)

    def render_zapas(zapas):
        aktualni_cas = datetime.utcnow() + timedelta(hours=2)
        is_closed = aktualni_cas > pd.to_datetime(zapas['DateTime'])
        skore_zadane = str(zapas.get('Skore_D', '')).strip() not in ["", "None", "nan"]
        if zapas['ID'] == 25:
            border_color, bg_color = ("#FFD700", "#4A148C") 
            badge_html = '<div style="text-align: center; font-size: 10px; color: #FFD700; margin-bottom: 5px; font-weight: bold;">✨ PÁROVÉ KOLO ✨</div>'
        else:
            border_color, bg_color = ("#e74c3c", "#1a0a0a") if is_closed else ("#2ecc71", "#1e1e1e")
            badge_html = ""
        middle = f'<div style="font-size:24px; font-weight:bold; color:#fff;">{zapas["Skore_D"]} : {zapas["Skore_H"]}</div>' if (is_closed and skore_zadane) else (f'<div style="font-size:12px; font-weight:bold; color:#FFD700; text-transform: uppercase;">PRÁVĚ SE HRAJE</div>' if is_closed else f'<div style="font-size:18px; font-weight:bold; color:#fff;">{zapas["Cas"]}</div>')
        strel_info = f'<div style="font-size: 0.85em; color: #4CAF50; margin-top: 5px;">⚽ Střelci: <b>{str(zapas.get("Střelec", "")).replace(",", ", ")}</b></div>' if (is_closed and str(zapas.get("Střelec", "")).strip() not in ["", "nan"]) else ""
        st.markdown(badge_html + f"""<div style="background-color: {bg_color}; padding: 15px; border-radius: 8px 8px 0 0; border-bottom: 4px solid {border_color}; color: white; margin-top: 15px;"><div style="display: flex; justify-content: space-between; align-items: center;"><div style="width: 40%; text-align: left; font-weight:bold; font-size: 1.1em;">{get_flag_html(zapas['Domaci'])} {zapas['Domaci']}</div><div style="width: 20%; text-align: center;">{middle}</div><div style="width: 40%; text-align: right; font-weight:bold; font-size: 1.1em;">{zapas['Hoste']} {get_flag_html(zapas['Hoste'])}</div></div>{strel_info}</div>""", unsafe_allow_html=True)
        with st.expander("Detaily a tipy"):
            c1, c2 = st.columns(2)
            with c1:
                if is_closed: st.error("Tipování uzavřeno.")
                else:
                    with st.form(f"f_{zapas['ID']}"):
                        st.write(f"Tipuješ jako: **{st.session_state.jmeno_hrace}**")
                        t1, t2 = st.columns(2)
                        td, th = t1.number_input("Góly D", 0, key=f"d_{zapas['ID']}"), t2.number_input("Góly H", 0, key=f"h_{zapas['ID']}")
                        hraci_df = df_soupisky[df_soupisky['Tým_Clean'].isin([str(zapas['Domaci']).strip().lower(), str(zapas['Hoste']).strip().lower()])]
                        moznosti = [f"({get_pozice_label(r)}) {r['Hráč']} ({r['Tým']})".replace("()", "") for _, r in hraci_df.iterrows() if get_pozice_label(r) != "B"]
                        vyber_strelec = st.selectbox("Tip na střelce:", moznosti, key=f"s_{zapas['ID']}")
                        if st.form_submit_button("ULOŽIT TIP"):
                            ciste_jmeno = "" if (td == 0 and th == 0) else (vyber_strelec[vyber_strelec.find(")")+2:] if ")" in vyber_strelec else vyber_strelec)
                            ws = get_gspread_client().open("MS2026_Tipovacka").worksheet("Tipy")
                            exist = df_tipy[(df_tipy['ID_Zapasu'] == zapas['ID']) & (df_tipy['Jméno'] == st.session_state.jmeno_hrace)]
                            if not exist.empty: ws.update(f"C{exist.index[0]+2}:E{exist.index[0]+2}", [[td, th, ciste_jmeno]])
                            else: ws.append_row([st.session_state.jmeno_hrace, zapas['ID'], td, th, ciste_jmeno])
                            st.cache_data.clear()
                            st.rerun()
            with c2:
                st.markdown("<h5 style='margin-bottom: 15px;'>👥 Tipy ostatních</h5>", unsafe_allow_html=True)
                for _, tip in df_tipy[df_tipy['ID_Zapasu'] == zapas['ID']].iterrows():
                    user_color = get_user_color(tip['Jméno'])
                    st.markdown(f'<div style="background-color: #262730; padding: 10px 15px; margin-bottom: 8px; border-radius: 10px; border-left: 4px solid {user_color};"><div style="display: flex; justify-content: space-between;"><span style="font-weight: 500; color: {user_color};">{tip["Jméno"]}</span><span>{tip["Tip_D"]} : {tip["Tip_H"]}</span></div><div style="font-size: 0.8em; color: #aaa;">⚽ Střelec: {str(tip.get("Střelec", "Nezadáno")).replace(",", ", ")}</div></div>', unsafe_allow_html=True)

    def get_herni_den(dt):
        if dt.hour < 10: return (dt - timedelta(days=1)).date()
        return dt.date()

    tab1, tab2 = st.tabs(["📅 Nedohrané zápasy", "🏁 Odehrané zápasy"])
    with tab1:
        df_nedohrane_copy = df_nedohrane.copy()
        df_nedohrane_copy['Herni_Den'] = df_nedohrane_copy['DateTime'].apply(get_herni_den)
        for datum, grupa in df_nedohrane_copy.groupby('Herni_Den'):
            st.markdown(f'<div style="text-align: center; margin: 40px 0 15px 0; font-size: 1.4em; font-weight: bold; color: #4CAF50;">{datum.strftime("%d. %m. %Y")}</div>', unsafe_allow_html=True)
            with st.expander(f"Zobrazit {len(grupa)} zápas(y) tohoto dne", expanded=True):
                for _, zapas in grupa.sort_values('DateTime').iterrows(): render_zapas(zapas)
    with tab2:
        df_dohrane_copy = df_dohrane.copy()
        df_dohrane_copy['Herni_Den'] = df_dohrane_copy['DateTime'].apply(get_herni_den)
        for datum, grupa in df_dohrane_copy.groupby('Herni_Den', sort=False):
            st.markdown(f'<div style="text-align: center; margin: 40px 0 15px 0; font-size: 1.4em; font-weight: bold; color: #e74c3c;">{datum.strftime("%d. %m. %Y")}</div>', unsafe_allow_html=True)
            with st.expander(f"Zobrazit {len(grupa)} zápas(y) tohoto dne", expanded=False):
                for _, zapas in grupa.sort_values('DateTime', ascending=False).iterrows(): render_zapas(zapas)

with col_side:
    st.subheader("🏆 Pořadí")
    lb = df_tipy.groupby('Jméno')['Body'].sum().sort_values(ascending=False).reset_index()
    for i, row in lb.iterrows():
        medal = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "👤")
        st.markdown(f'<div class="lb-row"><div class="lb-rank">{medal}</div><div class="lb-name">{row["Jméno"]}</div><div class="lb-points">{int(row["Body"])} b</div></div>', unsafe_allow_html=True)
