import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import hashlib
import unicodedata
from datetime import datetime, timedelta
import pytz  # Přidejte tento import

# --- KONFIGURACE ---
st.set_page_config(layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #121212; color: #e0e0e0; }
    h1, h2, h3, div, p { color: #e0e0e0 !important; }
    .block-container { max-width: 1100px !important; padding: 2rem !important; }
    .stExpander { border: 1px solid #333 !important; margin-top: -5px !important; border-radius: 0 0 8px 8px !important; }
    .stExpanderContent { background-color: #1a1a1a !important; padding: 20px !important; }
    .lb-row { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid #333; color: #e0e0e0; }
    .lb-rank { font-size: 20px; font-weight: bold; width: 40px; }
    .lb-name { flex-grow: 1; font-weight: 500; }
    .lb-points { font-weight: bold; color: #4CAF50; }
    [data-testid="stPopover"] { display: none; }
    @media (max-width: 800px) {
        [data-testid="stPopover"] { display: flex !important; position: fixed; bottom: 20px; left: 20px; z-index: 1000; }
        button[data-testid="stBaseButton-secondary"] { width: 50px !important; height: 50px !important; border-radius: 50% !important; padding: 0 !important; background-color: #4CAF50 !important; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNKCE ---
def get_current_time():
    # Nastaví Pražskou časovou zónu
    prague_tz = pytz.timezone('Europe/Prague')
    return datetime.now(prague_tz).replace(tzinfo=None) # .replace odstraní zónu pro snadné porovnání

def remove_accents(input_str):
    if not isinstance(input_str, str): return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

def get_gspread_client():
    return gspread.service_account_from_dict(st.secrets["gcp"])

def get_flag_html(country_name):
    iso_codes = {
    # Původní + předchozí přidané
    "Česko": "cz", "Slovensko": "sk", "Jižní Korea": "kr", "Německo": "de", 
    "Francie": "fr", "Anglie": "gb-eng", "Španělsko": "es", "Itálie": "it", 
    "Brazílie": "br", "Argentina": "ar", "Mexiko": "mx", "Kanada": "ca", 
    "Bosna a Hercegovina": "ba", "USA": "us", "Paraguay": "py", "Katar": "qa", 
    "Švýcarsko": "ch", "Maroko": "ma", "Jihoafrická republika": "za", "Jar": "za",
    "Haiti": "ht", "Skotsko": "gb-sct", "Austrálie": "au", "Turecko": "tr", 
    "Curacao": "cw", "Japonsko": "jp", "Nizozemsko": "nl", "Pobřeží slonoviny": "ci", 
    "Ekvádor": "ec", "Švédsko": "se", "Tunisko": "tn", "Belgie": "be", 
    "Egypt": "eg", "Kapverdy": "cv",
    
    # Nově přidané
    "Saúdská Arábie": "sa", "Uruguay": "uy", "Írán": "ir", "Nový Zéland": "nz", 
    "Senegal": "sn", "Irák": "iq", "Norsko": "no", "Alžírsko": "dz", 
    "Rakousko": "at", "Jordánsko": "jo", "Portugalsko": "pt", "DR Kongo": "cd", 
    "Chorvatsko": "hr", "Ghana": "gh", "Panama": "pa", "Uzbekistán": "uz", 
    "Kolumbie": "co"
}
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

def get_pozice_label(row):
    # 1. Zkusíme vytáhnout hodnotu ze sloupce "Pozice"
    p = str(row.get('Pozice', '')).strip()
    
    # 2. Pokud je to prázdné, zkusíme najít pozici v textu (když tam je "1GK", "2DF" atd.)
    if p == "" or p == "nan" or p == "None":
        # Hledáme v celém řádku, nebo zkusíme vzít hodnotu z Pozice_import, 
        # pokud ji tam máš (i když jsi říkal, že ji nemáš, takhle to pojistíme):
        val = str(row.get('Pozice_import', '')).strip()
        
        if "GK" in val: return "B"
        if "DF" in val: return "O"
        if "MF" in val: return "Z"
        if "FW" in val: return "ÚT"
        return "" # Pokud není nic, vrátí prázdno (ale závorky už ošetříme)
        
    return p

def calc_body(row):
    # Najdeme odpovídající zápas
    z = df_zapas[df_zapas['ID'] == row['ID_Zapasu']]
    if z.empty: return 0
    z = z.iloc[0]
    
    # 1. KONTROLA UZAVŘENÍ: Pokud není vyplněné skóre, zápas se nepočítá
    skore_d_raw = str(z.get('Skore_D', ''))
    skore_h_raw = str(z.get('Skore_H', ''))
    
    # Pokud je skóre prázdné nebo "nan", zápas není uzavřený -> 0 bodů
    if skore_d_raw.strip() in ["", "nan", "None"] or skore_h_raw.strip() in ["", "nan", "None"]:
        return 0

    # Funkce pro bezpečný převod na int
    def safe_int(val):
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    # Načtení hodnot
    skore_d = safe_int(skore_d_raw)
    skore_h = safe_int(skore_h_raw)
    tip_d = safe_int(row.get('Tip_D'))
    tip_h = safe_int(row.get('Tip_H'))
    
    body = 0
    
    # 2. Bodování výsledku
    trefen_presny = (tip_d == skore_d and tip_h == skore_h)
    trefen_nepresny = (
        (tip_d > tip_h and skore_d > skore_h) or 
        (tip_d < tip_h and skore_d < skore_h) or 
        (tip_d == tip_h and skore_d == skore_h)
    )
    
    if trefen_presny:
        body += 3
        if skore_d == 0 and skore_h == 0:
            body += 1
    elif trefen_nepresny:
        body += 1
        
    # 3. Bodování střelce
    # 3. Bodování střelce
    je_vysledek_00 = (skore_d == 0 and skore_h == 0)
    
    if not je_vysledek_00 and "Střelec" in z and not pd.isna(z['Střelec']) and str(z['Střelec']).strip() != "":
        # Seznam střelců z tabulky
        skutecni_strelci = [remove_accents(s.strip()) for s in str(z['Střelec']).split(",")]
        
        # OČIŠTĚNÍ TIPU: Odstraníme vše od první závorky včetně
        surovy_tip = str(row.get('Střelec', ''))
        if "(" in surovy_tip:
            surovy_tip = surovy_tip.split("(")[0] # Vezme jen část před závorkou
        
        tipovany_strelec = remove_accents(surovy_tip.strip())
        
        # DEBUG: st.write(f"DEBUG: Tip '{tipovany_strelec}' vs Střelci {skutecni_strelci}")
        
        if tipovany_strelec != "" and tipovany_strelec in skutecni_strelci:
            body += 1
            
    return body

if not df_tipy.empty and 'Skore_D' in df_zapas.columns:
    df_tipy['Body'] = df_tipy.apply(calc_body, axis=1)

# --- UI ---
st.markdown(f"""
    <div style="
        background: #1a1a1a; 
        padding: 15px; 
        border-radius: 12px; 
        border: 1px solid #333; 
        margin: 0 auto 20px auto; 
        max-width: 1100px; 
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
        <h2 style="margin: 0; color: #4CAF50 !important;">Tipovačka MS 2026 🏆</h2>
    </div>
""", unsafe_allow_html=True)

with st.popover("📊"):
    st.subheader("🏆 Aktuální pořadí")
    if 'Body' in df_tipy.columns:
        lb = df_tipy.groupby('Jméno')['Body'].sum().sort_values(ascending=False).reset_index()
        for i, row in lb.iterrows():
            medal = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "👤")
            st.markdown(f'<div class="lb-row"><div class="lb-rank">{medal}</div><div class="lb-name">{row["Jméno"]}</div><div class="lb-points">{int(row["Body"])} b</div></div>', unsafe_allow_html=True)

col_main, col_side = st.columns([2.5, 1])

with col_main:
    # 1. Příprava dat
    df_zapas['DateTime'] = pd.to_datetime(df_zapas['DateTime'])
    mask_dohrane = df_zapas['Skore_D'].notna() & (df_zapas['Skore_D'].astype(str) != "") & (df_zapas['Skore_D'].astype(str) != "nan")
    df_dohrane = df_zapas[mask_dohrane].sort_values('DateTime', ascending=False)
    df_nedohrane = df_zapas[~mask_dohrane].sort_values('DateTime', ascending=True)

    # 2. Definice pomocné funkce pro vykreslení zápasu (aby se kód neopakoval)
    def render_zapas(zapas):
        aktualni_cas = datetime.utcnow() + timedelta(hours=2)
        zapas_dt = pd.to_datetime(zapas['DateTime'])
        is_closed = aktualni_cas > zapas_dt
        skore_zadane = str(zapas.get('Skore_D', '')).strip() not in ["", "0", "None", "nan", 0]
        
        middle_content = f'<div style="font-size:24px; font-weight:bold; color:#fff;">{zapas["Skore_D"]} : {zapas["Skore_H"]}</div>' if (is_closed and skore_zadane) else (f'<div style="font-size:12px; font-weight:bold; color:#FFD700; text-transform: uppercase;">PRÁVĚ SE HRAJE</div>' if is_closed else f'<div style="font-size:18px; font-weight:bold; color:#fff;">{zapas["Cas"]}</div>')
        border_color, bg_color = ("#e74c3c", "#1a0a0a") if is_closed else ("#2ecc71", "#1e1e1e")
        strel_info = f'<div style="font-size: 0.85em; color: #4CAF50; margin-top: 5px;">⚽ Střelci: <b>{str(zapas.get("Střelec", "")).replace(",", ", ")}</b></div>' if (is_closed and str(zapas.get("Střelec", "")) != "" and str(zapas.get("Střelec", "")) != "nan") else ""
        
        st.markdown(f"""
            <div style="background-color: {bg_color}; padding: 15px; border-radius: 8px 8px 0 0; border-bottom: 4px solid {border_color}; color: white; margin-top: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="width: 40%; text-align: left; font-weight:bold; font-size: 1.1em;">{get_flag_html(zapas['Domaci'])} {zapas['Domaci']}</div>
                    <div style="width: 20%; text-align: center;">{middle_content}</div>
                    <div style="width: 40%; text-align: right; font-weight:bold; font-size: 1.1em;">{zapas['Hoste']} {get_flag_html(zapas['Hoste'])}</div>
                </div>{strel_info}
            </div>
        """, unsafe_allow_html=True)
        
        with st.expander("Detaily a tipy"):
            c1, c2 = st.columns(2)
            with c1:
                if is_closed: st.error("Tipování uzavřeno.")
                else:
                    with st.form(f"f_{zapas['ID']}"):
                        user = st.selectbox("Hráč:", df_uzivatele["Jméno"], key=f"u_{zapas['ID']}")
                        t1, t2 = st.columns(2)
                        td = t1.number_input("Góly D", 0, key=f"d_{zapas['ID']}")
                        th = t2.number_input("Góly H", 0, key=f"h_{zapas['ID']}")
                        hraci_df = df_soupisky[df_soupisky['Tým_Clean'].isin([str(zapas['Domaci']).strip().lower(), str(zapas['Hoste']).strip().lower()])]
                        moznosti = [f"({get_pozice_label(r)}) {r['Hráč']} ({r['Tým']})".replace("()", "") for _, r in hraci_df.iterrows() if get_pozice_label(r) != "B"]
                        vyber_strelec = st.selectbox("Tip na střelce:", moznosti, key=f"s_{zapas['ID']}")
                        if st.form_submit_button("ULOŽIT TIP"):
                            ciste_jmeno = "" if (td == 0 and th == 0) else (vyber_strelec[vyber_strelec.find(")")+2:] if ")" in vyber_strelec else vyber_strelec)
                            ws = get_gspread_client().open("MS2026_Tipovacka").worksheet("Tipy")
                            exist = df_tipy[(df_tipy['ID_Zapasu'] == zapas['ID']) & (df_tipy['Jméno'] == user)]
                            if not exist.empty: ws.update(f"C{exist.index[0]+2}:E{exist.index[0]+2}", [[td, th, ciste_jmeno]])
                            else: ws.append_row([user, zapas['ID'], td, th, ciste_jmeno])
                            st.cache_data.clear(); st.rerun()
            with c2:
                st.markdown("<h5 style='margin-bottom: 15px;'>👥 Tipy ostatních</h5>", unsafe_allow_html=True)
                for _, tip in df_tipy[df_tipy['ID_Zapasu'] == zapas['ID']].iterrows():
                    user_color = get_user_color(tip['Jméno'])
                    st.markdown(f'<div style="background-color: #262730; padding: 10px 15px; margin-bottom: 8px; border-radius: 10px; border-left: 4px solid {user_color};"><div style="display: flex; justify-content: space-between;"><span style="font-weight: 500; color: {user_color};">{tip["Jméno"]}</span><span>{tip["Tip_D"]} : {tip["Tip_H"]}</span></div><div style="font-size: 0.8em; color: #aaa;">⚽ Střelec: {str(tip.get("Střelec", "Nezadáno")).replace(",", ", ")}</div></div>', unsafe_allow_html=True)

    # 3. Vykreslení Tabů
    tab1, tab2 = st.tabs(["📅 Nedohrané zápasy", "🏁 Odehrané zápasy"])
    
    with tab1:
        last_date = None
        for _, zapas in df_nedohrane.iterrows():
            if zapas['Datum'] != last_date:
                st.markdown(f'<div style="text-align: center; margin: 20px 0; color: #4CAF50; font-weight: bold;">{zapas["Datum"]}</div>', unsafe_allow_html=True)
                last_date = zapas['Datum']
            render_zapas(zapas)
            
    with tab2:
        for _, zapas in df_dohrane.iterrows():
            render_zapas(zapas)

with col_side:
    st.subheader("🏆 Pořadí")
    if 'Body' in df_tipy.columns:
        lb = df_tipy.groupby('Jméno')['Body'].sum().sort_values(ascending=False).reset_index()
        for i, row in lb.iterrows():
            medal = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "👤")
            st.markdown(f'<div class="lb-row"><div class="lb-rank">{medal}</div><div class="lb-name">{row["Jméno"]}</div><div class="lb-points">{int(row["Body"])} b</div></div>', unsafe_allow_html=True)
