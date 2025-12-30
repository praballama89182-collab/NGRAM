import streamlit as st
import pandas as pd
import io

# --- 1. PAGE CONFIGURATION (MUST BE FIRST) ---
st.set_page_config(
    page_title="Prabal Ecommerce Analyzer",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. THEME-NEUTRAL CSS ---
st.markdown("""
    <style>
    .stMetric { 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def normalize_match_type(val):
    if pd.isna(val): return 'UNKNOWN'
    val = str(val).upper()
    if 'EXACT' in val: return 'EXACT'
    if 'PHRASE' in val: return 'PHRASE'
    if 'BROAD' in val: return 'BROAD'
    return 'AUTO/OTHER'

def generate_ngrams(text, n):
    words = str(text).lower().split()
    if len(words) < n:
        return []
    return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]

def process_ngrams(df, n_value):
    ngram_data = []
    for _, row in df.iterrows():
        term = row['Search Term']
        grams = generate_ngrams(term, n_value)
        for gram in grams:
            ngram_data.append({
                'N-Gram': gram,
                'Spend': row['Spend'],
                'Sales': row['Sales'],
                'Orders': row['Orders'],
                'Clicks': row['Clicks']
            })
    if not ngram_data: return pd.DataFrame()
    ng_df = pd.DataFrame(ngram_data)
    ng_agg = ng_df.groupby('N-Gram', as_index=False).sum()
    ng_agg['ROAS'] = ng_agg.apply(lambda x: x['Sales']/x['Spend'] if x['Spend'] > 0 else 0, axis=1)
    ng_agg['ACOS'] = ng_agg.apply(lambda x: (x['Spend']/x['Sales'])*100 if x['Sales'] > 0 else 0, axis=1)
    ng_agg['Count'] = ng_df.groupby('N-Gram').size().values 
    return ng_agg.sort_values(by='Spend', ascending=False).round(2)

def to_excel(dfs):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for sheet_name, df in dfs.items():
            if not df.empty: df.to_excel(writer, sheet_name=sheet_name[:31], index=False) 
    return output.getvalue()

# --- MAIN APP ---
def main():
    with st.sidebar:
        st.title("🛒 Prabal Analyzer")
        uploaded_file = st.file_uploader("Upload Search Term Report", type=["csv", "xlsx"])
        df = None
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'): df_raw = pd.read_csv(uploaded_file)
                else: df_raw = pd.read_excel(uploaded_file)
                df_raw.columns = df_raw.columns.str.strip()
                port_col = next((c for c in df_raw.columns if 'Portfolio' in c), None)
                if port_col:
                    all_portfolios = df_raw[port_col].dropna().unique().tolist()
                    selected_ports = st.multiselect("Select Portfolios", options=all_portfolios, default=all_portfolios)
                    df = df_raw[df_raw[port_col].isin(selected_ports)].copy() if selected_ports else df_raw.copy()
                else:
                    df = df_raw.copy()
            except Exception as e: st.error(f"Error: {e}")

    if df is not None:
        try:
            # Column Mapping & Cleaning
            col_map = {
                'term': next((c for c in df.columns if 'Customer Search Term' in c or 'Matched product' in c), 'Search Term'),
                'spend': next((c for c in df.columns if 'Spend' in c), 'Spend'),
                'sales': next((c for c in df.columns if 'Sales' in c), 'Sales'),
                'orders': next((c for c in df.columns if 'Orders' in c), 'Orders'),
                'clicks': next((c for c in df.columns if 'Clicks' in c), 'Clicks')
            }
            
            # Clean numeric data
            for key in ['spend', 'sales', 'orders', 'clicks']:
                df[col_map[key]] = pd.to_numeric(df[col_map[key]], errors='coerce').fillna(0)

            # Aggregation for Dashboard
            df_agg = df.groupby(col_map['term'], as_index=False).agg({
                col_map['spend']: 'sum', col_map['sales']: 'sum', col_map['orders']: 'sum', col_map['clicks']: 'sum'
            }).rename(columns={col_map['term']: 'Search Term', col_map['spend']: 'Spend', col_map['sales']: 'Sales', col_map['orders']: 'Orders', col_map['clicks']: 'Clicks'})
            
            df_agg['ROAS'] = (df_agg['Sales'] / df_agg['Spend']).fillna(0).round(2)
            df_agg['ACOS'] = (df_agg['Spend'] / df_agg['Sales'] * 100).fillna(0).round(2)
            
            # --- DASHBOARD TABS ---
            st.title("Prabal Ecommerce Analyzer")
            tabs = st.tabs(["📊 Overview", "🔠 N-Gram Analysis", "💸 Wasted Spend"])
            
            with tabs[0]:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Spend", f"₹{df_agg['Spend'].sum():,.2).format(df_agg['Spend'].sum())}")
                c2.metric("Total Sales", f"₹{df_agg['Sales'].sum():,.2).format(df_agg['Sales'].sum())}")
                total_acos = (df_agg['Spend'].sum() / df_agg['Sales'].sum() * 100) if df_agg['Sales'].sum() > 0 else 0
                c3.metric("Account ACOS", f"{total_acos:.2f}%")
                st.dataframe(df_agg.sort_values(by='Spend', ascending=False), use_container_width=True)

            with tabs[1]:
                n_val = st.radio("Gram Size", [1, 2, 3, 4], horizontal=True)
                ngram_df = process_ngrams(df_agg, n_val)
                st.dataframe(ngram_df, use_container_width=True)

            with tabs[2]:
                waste = df_agg[(df_agg['Orders'] == 0) & (df_agg['Spend'] > 0)].sort_values(by='Spend', ascending=False)
                st.dataframe(waste, use_container_width=True)

            # Export
            st.download_button("📥 Download Master Report", data=to_excel({"Summary": df_agg, "N-Grams": ngram_df}), file_name="PPC_Report.xlsx")

        except Exception as e: st.error(f"Processing Error: {e}")
    else:
        st.info("👋 Welcome! Please upload your report in the sidebar to begin.")

if __name__ == "__main__":
    main()
