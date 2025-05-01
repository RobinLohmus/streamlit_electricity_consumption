import streamlit as st
import pandas as pd
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import requests
import io

API_BASE = "https://decision.cs.taltech.ee/electricity/api/"


def main():
    dataset_list = get_dataset_list()
    dataset_hashes = [d['dataset'] for d in dataset_list]

    selected_date = st.date_input("Pick a date to visualize", value=pd.to_datetime("2024-01-15").date())
    N = st.slider("How many datasets to visualize?", min_value=1, max_value=len(dataset_hashes), value=50)

    # Load all datasets ONCE and cache the result
    full_df = load_all_datasets()

    # Filter for selected date
    day_df = full_df[full_df['date'] == selected_date]

    if not day_df.empty:
        fig = px.line(day_df, x='hour', y='consumption', color='dataset',
                      title=f"Hourly Consumption on {selected_date} for {N} Datasets",
                      labels={'consumption': 'kWh', 'hour': 'Hour of Day'})
        st.plotly_chart(fig)

    # Static 100-day visualization from local CSV
    st.title("Electricity Consumption - 100 Days")

    df = pd.read_csv('tarbimine.csv', sep=';', skiprows=4, header=0)
    df.columns = ['Periood', 'consumption']
    df['Periood'] = pd.to_datetime(df['Periood'], dayfirst=True)
    df['consumption'] = df['consumption'].str.replace(',', '.').astype(float)
    df['date'] = df['Periood'].dt.date
    df['hour'] = df['Periood'].dt.hour

    pt = df.pivot_table(index='date', columns='hour', values='consumption', aggfunc='mean').sort_index()
    pt = pt.dropna()
    dates = list(pt.index)[:100]
    df = df[df['date'].isin(dates)]

    min_date, max_date = min(dates), max(dates)
    selected_range = st.slider("Select date range", min_value=min_date, max_value=max_date, value=(min_date, max_date))
    filtered_df = df[(df['date'] >= selected_range[0]) & (df['date'] <= selected_range[1])]

    fig = px.line(filtered_df.groupby('date')['consumption'].mean().reset_index(),
                  x='date', y='consumption', title='Filtered Daily Consumption')
    st.plotly_chart(fig)

    st.subheader("Hourly Consumption Heatmap (100 Days)")
    fig2, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(pt.loc[dates], cmap='YlOrRd', ax=ax)
    st.pyplot(fig2)

    avg_hourly = df.groupby('hour')['consumption'].mean().reset_index()
    fig3 = px.bar(avg_hourly, x='hour', y='consumption', title='Average Consumption by Hour of Day')
    st.plotly_chart(fig3)


def get_dataset_list():
    response = requests.get(API_BASE)
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch dataset list.")
        return []


@st.cache_data(show_spinner="Downloading and caching all datasets...")
def load_all_datasets():
    dataset_list = get_dataset_list()
    all_dfs = []
    for i, d in enumerate(dataset_list):
        df = download_and_clean_dataset(d['dataset'])
        if df is not None and not df.empty:
            df['dataset'] = f"DS_{i+1}"
            all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


def download_and_clean_dataset(dataset_hash):
    url = f"https://decision.cs.taltech.ee/electricity/data/{dataset_hash}.csv"
    response = requests.get(url)
    if response.status_code != 200:
        return None

    try:
        df = pd.read_csv(io.StringIO(response.text), sep=';', skiprows=4, header=0)
        if df.shape[1] < 2:
            return None

        df.columns = ['Periood', 'consumption']
        df['Periood'] = pd.to_datetime(df['Periood'], dayfirst=True, errors='coerce')

        df['consumption'] = (
            df['consumption']
            .astype(str)
            .str.replace(',', '.', regex=False)
            .str.replace(r'[^0-9\.]', '', regex=True)
            .str.replace(r'\.+', '.', regex=True)
        )
        df['consumption'] = pd.to_numeric(df['consumption'], errors='coerce')
        df = df.dropna(subset=['Periood', 'consumption'])
        df['hour'] = df['Periood'].dt.hour
        df['date'] = df['Periood'].dt.date

        return df

    except Exception as e:
        print(f"Failed to parse dataset {dataset_hash}: {e}")
        return None


if __name__ == '__main__':
    main()
