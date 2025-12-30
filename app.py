import pandas as pd
import io

def analyze_search_terms(uploaded_file, brand_name=""):
    # Load File (CSV or Excel)
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # Standardize column names
    df.columns = df.columns.str.strip()
    
    # 1. NEW FIELD: ASIN vs Text Filter
    # Detects alphanumeric ASINs vs standard text
    df['Term Type'] = df['Customer Search Term'].apply(
        lambda x: 'ASIN' if str(x).startswith('b0') and len(str(x)) == 10 else 'Keyword'
    )
    
    # 2. NEW FIELD: Word Count Analysis
    # Useful to find long-tail opportunities
    df['Word Count'] = df['Customer Search Term'].apply(lambda x: len(str(x).split()))
    
    # 3. NEW FIELD: Brand vs Non-Brand
    if brand_name:
        df['Brand Category'] = df['Customer Search Term'].apply(
            lambda x: 'Brand' if brand_name.lower() in str(x).lower() else 'Generic'
        )

    # 4. N-GRAM ANALYSIS LOGIC
    def get_ngrams(text, n):
        words = str(text).lower().split()
        return [" ".join(words[i:i+n]) for i in range(len(words)-n+1)]

    ngram_results = []
    for n in [1, 2, 3]: # Generate 1-gram, 2-gram, 3-gram
        ngram_list = []
        for _, row in df.iterrows():
            grams = get_ngrams(row['Customer Search Term'], n)
            for g in grams:
                ngram_list.append({'N-Gram': g, 'Spend': row['Spend'], 'Sales': row['7 Day Total Sales '], 'Orders': row['7 Day Total Orders ']})
        
        # Aggregate N-Gram performance
        n_df = pd.DataFrame(ngram_list).groupby('N-Gram').sum().reset_index()
        n_df['ACOS'] = (n_df['Spend'] / n_df['Sales']).fillna(0)
        n_df['Gram Type'] = f"{n}-Gram"
        ngram_results.append(n_df)

    final_ngram_df = pd.concat(ngram_results)

    # EXPORT RESULTS
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Master_Analysis', index=False)
        final_ngram_df.to_excel(writer, sheet_name='NGram_Analysis', index=False)
        
        # Word Count Summary
        df.groupby('Word Count')[['Spend', '7 Day Total Sales ']].sum().to_excel(writer, sheet_name='WordCount_Summary')
    
    return output.getvalue()
