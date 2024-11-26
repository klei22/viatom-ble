import argparse
import datetime
import numpy as np
import pandas as pd
import seaborn as sns
import os
import matplotlib.pyplot as plt
from influxdb_client import InfluxDBClient, Point

def parse_arguments():
    parser = argparse.ArgumentParser(description='Create a heatmap of SpO₂ vs BPM from InfluxDB data.')
    parser.add_argument('--days', type=int, default=1, help='Number of days ago to start data retrieval.')
    parser.add_argument('--output', type=str, help='Path to save the heatmap image (e.g., heatmap.png).')
    return parser.parse_args()

def query_data(client, bucket, org, start_time, stop_time):
    query_api = client.query_api()

    # Flux query to get spo2 data
    spo2_query = f'''
    from(bucket: "{bucket}")
      |> range(start: {start_time}, stop: {stop_time})
      |> filter(fn: (r) => r._field == "spo2")
      |> keep(columns: ["_time", "_value"])
    '''

    # Flux query to get bpm data
    bpm_query = f'''
    from(bucket: "{bucket}")
      |> range(start: {start_time}, stop: {stop_time})
      |> filter(fn: (r) => r._field == "bpm")
      |> keep(columns: ["_time", "_value"])
    '''

    # Query spo2 data
    spo2_result = query_api.query(org=org, query=spo2_query)
    spo2_records = []
    for table in spo2_result:
        for record in table.records:
            spo2_records.append({'_time': record.get_time(), 'spo2': record.get_value()})
    spo2_df = pd.DataFrame(spo2_records)

    # Query bpm data
    bpm_result = query_api.query(org=org, query=bpm_query)
    bpm_records = []
    for table in bpm_result:
        for record in table.records:
            bpm_records.append({'_time': record.get_time(), 'bpm': record.get_value()})
    bpm_df = pd.DataFrame(bpm_records)

    return spo2_df, bpm_df

def process_data(spo2_df, bpm_df):
    # Merge dataframes on timestamp
    merged_df = pd.merge_asof(spo2_df.sort_values('_time'), bpm_df.sort_values('_time'),
                              on='_time', direction='nearest', tolerance=pd.Timedelta('1m'))

    # Drop rows with NaN values
    merged_df = merged_df.dropna(subset=['spo2', 'bpm'])

    # Bin the spo2 and bpm values
    spo2_bins = np.arange(90, 101, 1)  # SpO₂ bins from 90% to 100%
    bpm_bins = np.arange(40, 201, 10)  # BPM bins from 40 to 200 in steps of 10

    merged_df['spo2_bin'] = pd.cut(merged_df['spo2'], bins=spo2_bins, include_lowest=True, right=False)
    merged_df['bpm_bin'] = pd.cut(merged_df['bpm'], bins=bpm_bins, include_lowest=True, right=False)

    # Create a pivot table for the heatmap
    heatmap_data = merged_df.pivot_table(index='spo2_bin', columns='bpm_bin', values='_time', aggfunc='count', fill_value=0)

    return heatmap_data

def plot_heatmap(heatmap_data, output_path=None):
    # Set up the matplotlib figure
    plt.figure(figsize=(12, 8))

    # Create a heatmap
    sns.heatmap(heatmap_data, cmap='YlGnBu')

    # Customize plot
    plt.title('SpO₂ vs BPM Heatmap')
    plt.xlabel('BPM Bins')
    plt.ylabel('SpO₂ Bins')
    plt.tight_layout()

    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha='right')

    # Show or save the plot
    if output_path:
        plt.savefig(output_path)
        print(f'Heatmap saved to {output_path}')
    else:
        plt.show()

def main():
    args = parse_arguments()
    
    INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
    INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN")
    INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "chromebook")
    INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "health_data")

    # Calculate time range
    now = datetime.datetime.utcnow()
    start_time = now - datetime.timedelta(days=args.days)
    start_time_str = start_time.isoformat() + 'Z'
    stop_time_str = now.isoformat() + 'Z'

    # Connect to InfluxDB
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)

    # Query data
    spo2_df, bpm_df = query_data(client, INFLUXDB_BUCKET, INFLUXDB_ORG, start_time_str, stop_time_str)

    if spo2_df.empty or bpm_df.empty:
        print('No data found for the specified time range.')
        return

    # Process data
    heatmap_data = process_data(spo2_df, bpm_df)

    if heatmap_data.empty:
        print('No overlapping SpO₂ and BPM data found.')
        return

    # Plot heatmap
    plot_heatmap(heatmap_data, args.output)

if __name__ == '__main__':
    main()

