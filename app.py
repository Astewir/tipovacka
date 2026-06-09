import streamlit as st
import gspread
import pandas as pd
from datetime import datetime

# --- KONFIGURACE ---
st.set_page_config(layout="centered")

st.markdown("""
    <style>
    /* Globální tmavý mód */
    .stApp { background-color: #121212; color: #e0e0e0; }
    
    /* Úprava textů a nadpisů */
    h1, h2, h3, div, p { color: #e0e0e0 !important; }
    
    .block-container { max-width: 1100px !important; padding: 2rem !important; }
    
    /* Expander a vstupy */
    .stExpander { border: 1px solid #333 !important; margin-top: -5px !important; border-radius: 0 0 8px 8px !important; }
    .stExpanderContent { background-color: #1a1a1a !important; padding: 20px !important; }
    
    .score-box { font-size: 20px; font-weight: bold; color: #4CAF50; text-align: center; padding: 10px; border: 2px solid #4CAF50; background: #121212; }
    
    /* Leaderboard styly */
    .lb-row { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid #333; color: #e0e0e0; }
    .lb-rank { font-size: 20px; font-weight: bold; width: 40px; }
    .lb-name { flex-grow: 1; font-weight: 500; }
    .lb-points { font-weight: bold; color: #4CAF50; }
    
    /* Úprava vstupních polí a selectboxu pro tmavé pozadí */
    .stSelectbox, .stNumberInput { color: #e0e0e0 !important; }
    </style>
""", unsafe_allow_html=True)

# --- FUNKCE ---
def get_gspread_client():
    return gspread.service_account_from_dict(st.secrets["gcp"])

@st.cache_data(ttl=60)
def load_data_frames():
    client = get_gspread_client()
    sh = client.open("MS2026_Tipovacka")
    return pd.DataFrame(sh.worksheet("Zápasy").get_all_records()), \
           pd.DataFrame(sh.worksheet("Uživatelé").get_all_records()), \
           pd.DataFrame(sh.worksheet("Tipy").get_all_records())

df_zapas, df_uzivatele, df_tipy = load_data_frames()
df_zapas['DateTime'] = pd.to_datetime(df_zapas['Datum'] + ' ' + df_zapas['Cas'], format='%d.%m.%Y %H:%M')

def calc_body(row):
    z = df_zapas[df_zapas['ID'] == row['ID_Zapasu']]
    if z.empty: return 0
    z = z.iloc[0]
    if pd.isna(z['Skore_D']) or str(z['Skore_D']) == "": return 0
    if int(row['Tip_D']) == int(z['Skore_D']) and int(row['Tip_H']) == int(z['Skore_H']): return 3
    if (int(row['Tip_D']) > int(row['Tip_H']) and int(z['Skore_D']) > int(z['Skore_H'])) or \
       (int(row['Tip_D']) < int(row['Tip_H']) and int(z['Skore_D']) < int(z['Skore_H'])) or \
       (int(row['Tip_D']) == int(row['Tip_H']) and int(z['Skore_D']) == int(z['Skore_H'])): return 1
    return 0

def get_user_color(name):
    # Můžeš si definovat vlastní barvy pro konkrétní lidi
    color_map = {
        "Vojtin": "#FF5733",
        "Terezka": "#33FF57"
    }
    # Pokud jméno není v mapě, vygeneruje se barva z jména (vždy stejná pro stejné jméno)
    if name not in color_map:
        import hashlib
        hash_val = int(hashlib.md5(name.encode()).hexdigest(), 16)
        return f"#{hash_val % 0xFFFFFF:06x}"
    return color_map[name]

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
        
        st.markdown(f"""
        <div style="background-color: #1e1e1e; padding: 15px; border-radius: 8px 8px 0 0; border-bottom: 4px solid {border_color}; display: flex; justify-content: space-between; align-items: center; color: white; margin-top: 15px;">
            <div style="width: 35%; text-align: left; font-weight:bold;">{zapas['Domaci']}</div>
            <div style="width: 30%; text-align: center;">{middle_content}</div>
            <div style="width: 35%; text-align: right; font-weight:bold;">{zapas['Hoste']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("Detaily a tipy"):
            c1, c2 = st.columns(2)
            with c1:
                if is_closed:
                    st.error("Tipování uzavřeno.")
                else:
                    with st.form(f"f_{zapas['ID']}"):
                        user = st.selectbox("Hráč:", df_uzivatele["Jméno"], key=f"u_{zapas['ID']}")
                        t1, t2 = st.columns(2)
                        td = t1.number_input("Góly D", 0, key=f"d_{zapas['ID']}")
                        th = t2.number_input("Góly H", 0, key=f"h_{zapas['ID']}")
                        if st.form_submit_button("ULOŽIT TIP"):
                            ws = get_gspread_client().open("MS2026_Tipovacka").worksheet("Tipy")
                            exist = df_tipy[(df_tipy['ID_Zapasu'] == zapas['ID']) & (df_tipy['Jméno'] == user)]
                            if not exist.empty: ws.update(f"C{exist.index[0]+2}", [[td, th]])
                            else: ws.append_row([user, zapas['ID'], td, th])
                            st.cache_data.clear(); st.rerun()
            with c2:
                st.markdown("<h5 style='margin-bottom: 15px;'>👥 Tipy ostatních</h5>", unsafe_allow_html=True)
                tipy = df_tipy[df_tipy['ID_Zapasu'] == zapas['ID']]
                
                if tipy.empty:
                    st.caption("Zatím žádné tipy.")
                else:
                    for _, tip in tipy.iterrows():
                        user_color = get_user_color(tip['Jméno'])
                        st.markdown(f"""
                        <div style="
                            background-color: #262730; 
                            padding: 10px 15px; 
                            margin-bottom: 8px; 
                            border-radius: 10px; 
                            border-left: 4px solid {user_color};
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
                        ">
                            <span style="font-weight: 500; color: {user_color};">{tip['Jméno']}</span>
                            <span style="font-family: monospace; font-size: 1.1em; font-weight: bold; color: #ffffff;">
                                {tip['Tip_D']} : {tip['Tip_H']}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
with col_side:
    st.subheader("🏆 Pořadí")
    if 'Body' in df_tipy.columns:
        lb = df_tipy.groupby('Jméno')['Body'].sum().sort_values(ascending=False).reset_index()
        for i, row in lb.iterrows():
            medal = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "👤")
            st.markdown(f"""
            <div class="lb-row">
                <div class="lb-rank">{medal}</div>
                <div class="lb-name">{row['Jméno']}</div>
                <div class="lb-points">{int(row['Body'])} b</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.write("Čekáme na výsledky...")
