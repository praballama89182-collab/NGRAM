import streamlit as st
import pandas as pd
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Prabal Ecommerce Analyzer",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME-NEUTRAL CSS ---
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
    if len(words) < n: return []
    return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]

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
        st.markdown("---")
        uploaded_file = st.file_uploader("Upload Search Term Report", type=["csv", "xlsx"])
        
        df = None
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'): df_raw = pd.read_csv(uploaded_file)
                else: df_raw = pd.read_excel(uploaded_file, engine='openpyxl')
                df_raw.columns = df_raw.columns.str.strip()
                df = df_raw.copy()
            except Exception as e: st.error(f"Error: {e}")

        if df is not None:
            st.markdown("### ⚙️ Thresholds")
            acos_limit = st.slider("ACOS Friendly Threshold (%)", 5, 50, 20, 5)
            waste_threshold = st.number_input("Wasted Spend Min ($/₹)", 50, 5000, 200)

    if df is not None:
        try:
            # Column Mapping
            col_map = {
                'term': next((c for c in df.columns if 'Customer Search Term' in c or 'Matched product' in c), 'Search Term'),
                'camp': next((c for c in df.columns if 'Campaign Name' in c), 'Campaign'),
                'adg': next((c for c in df.columns if 'Ad Group Name' in c), 'Ad Group'),
                'match': next((c for c in df.columns if 'Match Type' in c), 'Match Type'),
                'spend': next((c for c in df.columns if 'Spend' in c), 'Spend'),
                'sales': next((c for c in df.columns if 'Sales' in c), 'Sales'),
                'orders': next((c for c in df.columns if 'Orders' in c), 'Orders'),
                'clicks': next((c for c in df.columns if 'Clicks' in c), 'Clicks')
            }
            
            for key in ['spend', 'sales', 'orders', 'clicks']:
                df[col_map[key]] = pd.to_numeric(df[col_map[key]], errors='coerce').fillna(0)
            df['norm_match'] = df[col_map['match']].apply(normalize_match_type)

            # Aggregation including Campaign/AdGroup for Wasted Spend
            df_agg = df.groupby([col_map['term'], col_map['camp'], col_map['adg'], 'norm_match'], as_index=False).agg({
                col_map['spend']: 'sum', col_map['sales']: 'sum', col_map['orders']: 'sum', col_map['clicks']: 'sum'
            }).rename(columns={
                col_map['term']: 'Search Term', col_map['camp']: 'Campaign', col_map['adg']: 'Ad Group',
                col_map['spend']: 'Spend', col_map['sales']: 'Sales', col_map['orders']: 'Orders', col_map['clicks']: 'Clicks'
            })
            
            df_agg['ACOS'] = (df_agg['Spend'] / df_agg['Sales'] * 100).fillna(0).round(1)
            df_agg['ROAS'] = (df_agg['Sales'] / df_agg['Spend']).fillna(0).round(1)

            # --- TABS ---
            st.title("Prabal Ecommerce Analyzer")
            tabs = st.tabs(["📊 Overview", "🚀 Strategy Center", "🔠 N-Gram Analysis", "💸 Wasted Spend"])
            
            with tabs[0]:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Spend", f"₹{df_agg['Spend'].sum():,.1f}")
                c2.metric("Total Sales", f"₹{df_agg['Sales'].sum():,.1f}")
                total_acos = (df_agg['Spend'].sum() / df_agg['Sales'].sum() * 100) if df_agg['Sales'].sum() > 0 else 0
                c3.metric("Account ACOS", f"{total_acos:.1f}%")
                st.dataframe(df_agg.sort_values(by='Sales', ascending=False), use_container_width=True)

            with tabs[1]:
                st.subheader("🏆 Top Performers by Match Type")
                st.caption(f"Showing Top 10 terms with ACOS $\le$ {acos_limit}%")
                
                for mt in ['EXACT', 'PHRASE', 'BROAD']:
                    st.markdown(f"#### 🎯 {mt.title()} Match")
                    mt_df = df_agg[df_agg['norm_match'] == mt]
                    
                    t1, t2 = st.columns(2)
                    with t1:
                        st.markdown("**💰 Top 10 Grossing (Sales)**")
                        st.dataframe(mt_df.nlargest(10, 'Sales')[['Search Term', 'Sales', 'ACOS', 'Orders']], use_container_width=True)
                    with t2:
                        st.markdown(f"**🌱 Top 10 ACOS Friendly ($\le$ {acos_limit}%)**")
                        st.dataframe(mt_df[(mt_df['Sales'] > 0) & (mt_df['ACOS'] <= acos_limit)].nsmallest(10, 'ACOS')[['Search Term', 'Sales', 'ACOS', 'Orders']], use_container_width=True)

            with tabs[2]:
                n_val = st.radio("Gram Size", [1, 2, 3, 4], horizontal=True)
                ngram_data = []
                for _, row in df_agg.iterrows():
                    grams = generate_ngrams(row['Search Term'], n_val)
                    for g in grams:
                        ngram_data.append({'N-Gram': g, 'Spend': row['Spend'], 'Sales': row['Sales'], 'Orders': row['Orders']})
                if ngram_data:
                    ng_df = pd.DataFrame(ngram_data).groupby('N-Gram', as_index=False).sum()
                    ng_df['ACOS'] = (ng_df['Spend'] / ng_df['Sales'] * 100).fillna(0).round(1)
                    st.dataframe(ng_df.sort_values(by='Spend', ascending=False), use_container_width=True)

            with tabs[3]:
                st.subheader("💸 Wasted Spend (Zero Orders)")
                waste = df_agg[(df_agg['Orders'] == 0) & (df_agg['Spend'] >= waste_threshold)].sort_values(by='Spend', ascending=False)
                st.dataframe(waste[['Search Term', 'Campaign', 'Ad Group', 'Spend', 'Clicks']], use_container_width=True)

            # Export
            st.download_button("📥 Download Master Report", data=to_excel({"Summary": df_agg}), file_name="Prabal_Report.xlsx")

        except Exception as e: st.error(f"Error: {e}")
    else:
        st.info("👋 Welcome! Please upload your report to start the analyzer.")

if __name__ == "__main__":
    main()
