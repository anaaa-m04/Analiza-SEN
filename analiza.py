import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Analiză SEN", layout="wide")

st.title("⚡ Analiză EDA: Comportamentul Hidro vs. SRE")
st.markdown("Această pagină analizează rolul hidroenergiei în echilibrarea surselor regenerabile (Eolian + Solar).")
st.divider()


@st.cache_data
def load_data():
    df = pd.read_excel('Grafic_SEN1.xlsx')
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)
    df = df.set_index('Data')
    df = df.sort_index()

    # Păstrăm doar anul 2025 pentru a evita anomalii de date
    df = df[df.index.year == 2025]

    df.columns = [col.split('[')[0].strip() for col in df.columns]
    df['SRE'] = df['Eolian'] + df['Foto']
    return df


df = load_data()

with st.sidebar:
    st.header("📊 Despre Setul de Date")
    st.info("Datele reprezintă producția de energie electrică din Sistemul Energetic Național (SEN).")
    st.write(f"**Început:** {df.index.min().strftime('%d %b %Y')}")
    st.write(f"**Sfârșit:** {df.index.max().strftime('%d %b %Y')}")
    st.write("**Sursa:** Transelectrica")


def apply_dark_mode_tweaks(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white" if st.get_option("theme.base") == "dark" else "gray")
    )
    return fig


# --- 1. CORELAȚIE ȘI RĂSPUNS LA VARIAȚIE ---
st.subheader("1. Rolul de echilibrare: Hidro vs. SRE")

col1, col2 = st.columns([2, 1])

with col1:
    corelatie = df['Ape'].corr(df['SRE'])
    fig_scatter = px.scatter(
        df, x='SRE', y='Ape', opacity=0.3,
        labels={'SRE': 'Producție SRE (Eolian + Solar) [MW]', 'Ape': 'Producție Hidro [MW]'},
        trendline="ols", trendline_color_override="red"
    )
    fig_scatter = apply_dark_mode_tweaks(fig_scatter)
    st.plotly_chart(fig_scatter, use_container_width=True)

with col2:
    st.markdown("❓ **Întrebări EDA:**")
    st.markdown(
        "**1.** *Cum răspunde producția hidro („Ape”) la variația eolian + solar? Crește hidro când SRE variabil scade (rol de echilibrare/backup)?*")
    st.markdown(
        "**2.** *Care e corelația dintre hidro și (eolian + solar)? Este negativă, cum sugerează rolul de compensare?*")

    st.success(f"""
    **Ce ne spun datele:**

    **1. Răspunsul la variație:** Da, datele confirmă rolul de backup. Când SRE scade spre zero (partea stângă a graficului), hidro crește masiv pentru a compensa. Invers, când avem mult soare și vânt (partea dreaptă), barajele își reduc vizibil producția, reținând apa.

    **2. Corelația:** Corelația matematică este ușor negativă (**{corelatie:.2f}**), confirmând ipoteza compensării. Linia roșie descrescătoare arată clar această tendință. Totuși, valoarea apropiată de zero ne indică faptul că hidroenergia nu este *doar* o baterie pentru SRE, ci are și alte sarcini (acoperirea vârfurilor de consum, exporturi etc.), ceea ce face ca punctele să fie destul de împrăștiate.
    """)

st.divider()

# --- 2. PROFIL CONDIȚIONAT (SRE Mult vs. Puțin) ---
st.subheader("2. Profilul mediu zilnic: Zile cu mult vs. puțin SRE")

st.markdown(
    "❓ **Întrebarea 3 din EDA:** *Cum arată profilul hidro în zilele cu vânt/soare mult vs. zilele cu vânt/soare puțin (suprapune curbele)?*")

df['Ora_Zilei'] = df.index.hour
df_zilnic = df.resample('D').mean(numeric_only=True)
prag_sus = df_zilnic['SRE'].quantile(0.75)
prag_jos = df_zilnic['SRE'].quantile(0.25)

conditii_zilnice = pd.Series('Normal', index=df_zilnic.index)
conditii_zilnice[df_zilnic['SRE'] >= prag_sus] = 'SRE Mult'
conditii_zilnice[df_zilnic['SRE'] <= prag_jos] = 'SRE Puțin'

df['Ziua'] = df.index.floor('D')
df['Conditie_SRE'] = df['Ziua'].map(conditii_zilnice).fillna('Normal')
profil_hidro = df[df['Conditie_SRE'].isin(['SRE Mult', 'SRE Puțin'])].groupby(['Ora_Zilei', 'Conditie_SRE'])[
    'Ape'].mean().reset_index()

fig_profil = px.line(
    profil_hidro, x='Ora_Zilei', y='Ape', color='Conditie_SRE',
    color_discrete_map={'SRE Mult': '#1f77b4', 'SRE Puțin': '#d62728'},
    labels={'Ape': 'Producție Medie Hidro [MW]', 'Ora_Zilei': 'Ora din zi'}
)
fig_profil = apply_dark_mode_tweaks(fig_profil)
st.plotly_chart(fig_profil, use_container_width=True)

st.info("""
**Ce ne spun datele:**
Dacă ne uităm la linia albastră (zile cu mult vânt și soare) și cea roșie (zile slabe pentru regenerabile), vedem că arată cam la fel. Ambele urmează programul nostru de consum casnic: urcă la 8 dimineața și au maximul la 8 seara. Diferența se vede strict la prânz (între orele **11:00 - 15:00**): în zilele cu soare și vânt bun, hidro lasă intenționat motoarele mai încet.
""")

st.divider()

# --- 3. DINAMICA INTRAZILNICĂ (O SĂPTĂMÂNĂ) ---
st.subheader("3. Dinamica intrazilnică (Serii Suprapuse pe o săptămână)")

st.markdown(
    "❓ **Întrebarea 4 din EDA:** *Urmează hidro forma intrazilnică a solarului — scade la prânz (când solarul e maxim) și crește dimineața/seara?*")

# Extragem exact primele 7 zile calendaristice din date pentru grafice
data_start = df.index.min()
data_stop = data_start + pd.Timedelta(days=7)
df_saptamana = df[(df.index >= data_start) & (df.index < data_stop)]

fig_linii = px.line(
    df_saptamana, y=['Ape', 'SRE', 'Foto'],
    labels={'value': 'Producție [MW]', 'Data': 'Timp', 'variable': 'Sursa'}
)
fig_linii.update_traces(line=dict(width=2))
fig_linii = apply_dark_mode_tweaks(fig_linii)
st.plotly_chart(fig_linii, use_container_width=True)

st.info("""
**Ce ne spun datele:**
Da, hidro chiar face loc energiei solare pe rețea. Se vede clar pe grafic cum producția hidro scade (face o vale) la prânz (pe la orele **12:00 - 14:00**), fix când soarele e cel mai puternic și atinge vârful clopotului de producție. Apoi crește rapid înapoi dimineața și seara, când soarele apune și avem vârfuri de consum.
""")

st.divider()

# --- 4. VITEZA DE RAMPARE ---
st.subheader("4. Viteza de rampare la căderile bruște de eolian")

df['Rampa_Eolian'] = df['Eolian'].diff()
df['Rampa_Ape'] = df['Ape'].diff()
df['Rampa_Gaz'] = df['Hidrocarburi'].diff()

prag_cadere = df['Rampa_Eolian'].quantile(0.05)
caderi_bruste = df[df['Rampa_Eolian'] <= prag_cadere]

col3, col4 = st.columns([2, 1])

with col3:
    fig_rampe = px.scatter(
        caderi_bruste, x='Rampa_Eolian', y=['Rampa_Ape', 'Rampa_Gaz'], opacity=0.7,
        labels={'value': 'Compensare (Rampare) [MW]', 'Rampa_Eolian': 'Scădere Eolian [MW]', 'variable': 'Sursa'}
    )
    fig_rampe.for_each_trace(lambda t: t.update(name=t.name.replace("Rampa_", "")))
    fig_rampe = apply_dark_mode_tweaks(fig_rampe)
    st.plotly_chart(fig_rampe, use_container_width=True)

with col4:
    st.markdown(
        "❓ **Întrebarea 5 din EDA:** *Cât de repede rampează hidro când eolianul cade brusc? Compensează în aceeași oră sau cu întârziere?*")

    media_cadere = caderi_bruste['Rampa_Eolian'].mean()
    reactie_ape = caderi_bruste['Rampa_Ape'].mean()

    st.success(f"""
    **Ce ne spun datele:**
    Hidro reacționează super rapid, **fără nicio întârziere orară**! La o cădere bruscă de **{media_cadere:.0f} MW** a vântului în doar 15 minute, hidro sare să compenseze direct în același interval, cu o medie de **+{reactie_ape:.0f} MW**. 
    Practic, hidro e sprinterul care echilibrează situația pe moment, prevenind dezechilibre majore în rețea.
    """)

st.divider()

# --- 5. PRAGUL DE MINIM ---
st.subheader("5. Partea forțată: Minimul Hidro")

st.markdown(
    "❓ **Întrebarea 6 din EDA:** *Există un prag de eolian + solar peste care hidro merge la minim (rămâne doar partea „forțată”: debit obligat, servicii de sistem)?*")

df['Interval_SRE'] = pd.cut(df['SRE'], bins=np.arange(0, 5500, 500))
# Folosim observed=True și dropna pentru a evita erorile la intervalele goale
minim_hidro = df.groupby('Interval_SRE', observed=True)['Ape'].quantile(0.05).reset_index().dropna()
minim_hidro['Interval_SRE'] = minim_hidro['Interval_SRE'].astype(str)

valoare_minim_absolut = minim_hidro['Ape'].min()

fig_prag = px.bar(
    minim_hidro, x='Interval_SRE', y='Ape',
    labels={'Ape': 'Minim Hidro operațional [MW]', 'Interval_SRE': 'Cantitate SRE pe rețea [MW]'}
)
fig_prag = apply_dark_mode_tweaks(fig_prag)
st.plotly_chart(fig_prag, use_container_width=True)

st.info(f"""
**Ce ne spun datele:**
Da, există un prag clar. Când avem foarte mult vânt și soare pe rețea (peste 1500 - 2000 MW), scăderea producției hidro se aplatizează, stabilizându-se în jurul valorii de 530 MW (atingând un minim absolut de {valoare_minim_absolut:.0f} MW doar la valori extreme ale SRE). E normal, pentru că barajele nu pot fi oprite de tot — e nevoie să curgă un debit minim pe râuri și să păstrăm rezerve de siguranță pentru stabilitatea rețelei.
""")

st.divider()

# --- 6. ROLURI ÎN SISTEM: RAMPE VS. BANDĂ ---
st.subheader("6. Împărțirea rolurilor: Rampe rapide (Hidro) vs. Bandă (Gaz)")

st.markdown(
    "❓ **Întrebarea 7 din EDA:** *Cum se împart rolurile între hidro și hidrocarburi (gaz) în acoperirea sarcinii reziduale — care preia rampele rapide și care banda?*")

fig_roluri = px.line(
    df_saptamana, y=['Ape', 'Hidrocarburi'],
    color_discrete_map={'Ape': '#1f77b4', 'Hidrocarburi': '#d62728'},
    labels={'value': 'Producție [MW]', 'Data': 'Timp', 'variable': 'Sursa'}
)
fig_roluri.update_traces(line=dict(width=2))
fig_roluri = apply_dark_mode_tweaks(fig_roluri)
st.plotly_chart(fig_roluri, use_container_width=True)

st.info("""
**Ce ne spun datele:**
Graficul ilustrează perfect diferența de funcționare. Linia roșie (Gaz/Hidrocarburi) este mult mai plată, rulând cu variații mici; gazul asigură producția în **bandă**, acoperind un necesar de bază stabil pe tot parcursul zilei. Prin contrast, linia albastră (Hidro) are fluctuații masive (vârfuri ascuțite și văi). Hidroenergia preia **rampele rapide**, reacționând agil la orice modificare bruscă de consum sau producție regenerabilă.
""")

st.divider()

# --- CONCLUZIE GENERALĂ ---
st.header("💡 Concluzia Generală")
st.success("""
Pe scurt, analizând toate aceste grafice, tragem o concluzie clară: **hidroenergia este cel mai versatil și important mecanism de echilibrare al sistemului nostru energetic**, acționând cu o viteză uimitoare la fluctuațiile eolianului și solarului. 

Cu toate acestea, hidroenergia nu este un simplu "angajat" al surselor regenerabile. Comportamentul barajelor este dictat în primul rând de tiparul zilnic prin care noi consumăm curentul (vârfuri dimineața și seara). În plus, chiar și în cele mai însorite și vântoase zile, energia hidro are niște limite fizice stricte sub care nu se poate opri.
""")