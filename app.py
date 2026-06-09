import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import hashlib

# --- KONFIGURACE ---
st.set_page_config(layout="centered")

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
    </style>
""", unsafe_allow_html=True)

# --- FUNKCE ---
def get_gspread_client():
    return gspread.service_account_from_dict(st.secrets["gcp"])

def get_flag_html(country_name):
    iso_codes = {
        "Česko": "cz", "Slovensko": "sk", "Jižní Korea": "kr", 
        "Německo": "de", "Francie": "fr", "Anglie": "gb", 
        "Španělsko": "es", "Itálie": "it", "Brazílie": "br", 
        "Argentina": "ar", "Mexiko": "mx", "Kanada": "ca",
        "Bosna a Hercegovina": "ba", "USA": "us", "Paraguay": "py",
        "Katar": "qa", "Švýcarsko": "ch", "Maroko": "ma",
        "Jihoafrická republika": "za", "Jar": "za"
    }
    iso = "xx"
    for name, code in iso_codes.items():
        if name.lower() in str(country_name).lower():
            iso = code
            break
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

def calc_body(row):
    z = df_zapas[df_zapas['ID'] == row['ID_Zapasu']]
    if z.empty: return 0
    z = z.iloc[0]
    
    body = 0
    
    # 1. Body za výsledek (3b přesně, 1b vítěz/remíza)
    if not pd.isna(z['Skore_D']) and str(z['Skore_D']) != "":
        if int(row['Tip_D']) == int(z['Skore_D']) and int(row['Tip_H']) == int(z['Skore_H']):
            body += 3
        elif (int(row['Tip_D']) > int(row['Tip_H']) and int(z['Skore_D']) > int(z['Skore_H'])) or \
             (int(row['Tip_D']) < int(row['Tip_H']) and int(z['Skore_D']) < int(z['Skore_H'])) or \
             (int(row['Tip_D']) == int(row['Tip_H']) and int(z['Skore_D']) == int(z['Skore_H'])):
            body += 1
            
    # 2. Bod za střelce (pokud je tipnutý střelec v seznamu střelců zápasu)
    if "Střelec" in z and not pd.isna(z['Střelec']) and z['Střelec'] != "":
        # Rozdělíme seznam střelců z tabulky podle čárky
        skutecni_strelci = [s.strip() for s in str(z['Střelec']).split(",")]
        # Zkontrolujeme, zda tip hráče odpovídá některému ze střelců
        if str(row.get('Střelec', '')) in skutecni_strelci:
            body += 1
            
    return body

if not df_tipy.empty and 'Skore_D' in df_zapas.columns:
    df_tipy['Body'] = df_tipy.apply(calc_body, axis=1)

# --- UI ---
st.title("⚽ MS 2026 ")
col_main, col_side = st.columns([2.5, 1])

with col_main:
    st.subheader("🗓️ Program zápasů")
    last_date = None
    for _, zapas in df_zapas.iterrows():
        if zapas['Datum'] != last_date:
            st.markdown(f'<div style="text-align: center; margin: 30px 0 20px 0; color: #4CAF50; font-weight: bold; display: flex; align-items: center;"><div style="flex: 1; height: 1px; background: #444;"></div><div style="padding: 0 15px; color: #aaa;">{zapas["Datum"]}</div><div style="flex: 1; height: 1px; background: #444;"></div></div>', unsafe_allow_html=True)
            last_date = zapas['Datum']

        is_closed = zapas['DateTime'] < datetime.now()
        border_color = "#e74c3c" if is_closed else "#2ecc71"
        middle_content = f'<div style="font-size:24px; font-weight:bold; color:#fff;">{zapas["Skore_D"]} : {zapas["Skore_H"]}</div>' if (is_closed and str(zapas.get('Skore_D', '')).strip() != "") else f'<div style="font-size:18px; font-weight:bold; color:#fff;">{zapas["Cas"]}</div>'
        
        strelci_zapas = str(zapas.get("Střelec", "")).replace(",", ", ")
        strel_info = f'<div style="font-size: 0.85em; color: #4CAF50; margin-top: 5px;">⚽ Střelci zápasu: <b>{strelci_zapas}</b></div>' if (is_closed and "Střelec" in zapas and zapas["Střelec"]) else ""

        st.markdown(f"""
        <div style="background-color: #1e1e1e; padding: 15px; border-radius: 8px 8px 0 0; border-bottom: 4px solid {border_color}; color: white; margin-top: 15px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="width: 40%; text-align: left; font-weight:bold; font-size: 1.1em;">{get_flag_html(zapas['Domaci'])} {zapas['Domaci']}</div>
                <div style="width: 20%; text-align: center;">{middle_content}</div>
                <div style="width: 40%; text-align: right; font-weight:bold; font-size: 1.1em;">{zapas['Hoste']} {get_flag_html(zapas['Hoste'])}</div>
            </div>
            {strel_info}
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
                        
                        hraci_d = df_soupisky[df_soupisky['Tým'] == zapas['Domaci']]['Hráč'].tolist()
                        hraci_h = df_soupisky[df_soupisky['Tým'] == zapas['Hoste']]['Hráč'].tolist()
                        střelec = st.selectbox("Tip na střelce:", hraci_d + hraci_h, key=f"s_{zapas['ID']}")

                        if st.form_submit_button("ULOŽIT TIP"):
                            ws = get_gspread_client().open("MS2026_Tipovacka").worksheet("Tipy")
                            exist = df_tipy[(df_tipy['ID_Zapasu'] == zapas['ID']) & (df_tipy['Jméno'] == user)]
                            if not exist.empty: ws.update(f"C{exist.index[0]+2}:E{exist.index[0]+2}", [[td, th, střelec]])
                            else: ws.append_row([user, zapas['ID'], td, th, střelec])
                            st.cache_data.clear(); st.rerun()
            with c2:
                st.markdown("<h5 style='margin-bottom: 15px;'>👥 Tipy ostatních</h5>", unsafe_allow_html=True)
                for _, tip in df_tipy[df_tipy['ID_Zapasu'] == zapas['ID']].iterrows():
                    user_color = get_user_color(tip['Jméno'])
                    tip_strelec = str(tip.get('Střelec', 'Nezadáno')).replace(",", ", ")
                    st.markdown(f"""
                    <div style="background-color: #262730; padding: 10px 15px; margin-bottom: 8px; border-radius: 10px; border-left: 4px solid {user_color};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 500; color: {user_color};">{tip['Jméno']}</span>
                            <span style="font-family: monospace; font-size: 1.1em; font-weight: bold; color: #ffffff;">{tip['Tip_D']} : {tip['Tip_H']}</span>
                        </div>
                        <div style="font-size: 0.8em; color: #aaa; margin-top: 5px;">⚽ Střelec: {tip_strelec}</div>
                    </div>
                    """, unsafe_allow_html=True)

with col_side:
    st.subheader("🏆 Pořadí")
    if 'Body' in df_tipy.columns:
        lb = df_tipy.groupby('Jméno')['Body'].sum().sort_values(ascending=False).reset_index()
        for i, row in lb.iterrows():
            medal = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "👤")
            st.markdown(f'<div class="lb-row"><div class="lb-rank">{medal}</div><div class="lb-name">{row["Jméno"]}</div><div class="lb-points">{int(row["Body"])} b</div></div>', unsafe_allow_html=True)
