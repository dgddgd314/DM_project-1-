import pandas as pd
import os
import glob

def aggregate_features(start, end, output_file):
    print(f"Aggregating features from run {start} to {end}...")
    all_dfs = []
    for run_id in range(start, end + 1):
        file_path = f"exports/Run_{run_id}_Features.xlsx"
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            all_dfs.append(df)
            print(f"  Added Run {run_id} ({len(df)} rows)")
        else:
            print(f"  WARNING: Run {run_id} features not found at {file_path}")
            
    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        combined_df.to_excel(output_file, index=False)
        print(f"Success! Saved to {output_file} ({len(combined_df)} total rows)")
        return combined_df
    return None

def aggregate_chats(start, end, output_file):
    print(f"Aggregating chats from run {start} to {end}...")
    headers_written = False
    total_rows = 0
    
    # We use a stream-like approach to avoid loading everything at once if memory is tight,
    # though 1M rows usually fits. But writing to CSV in chunks is safer.
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f_out:
        for run_id in range(start, end + 1):
            file_path = f"exports/Run_{run_id}_Chats.csv"
            if os.path.exists(file_path):
                # Read CSV
                df = pd.read_csv(file_path, low_memory=False)
                # Write to master file
                df.to_csv(f_out, index=False, header=(not headers_written))
                headers_written = True
                total_rows += len(df)
                print(f"  Added Run {run_id} ({len(df)} rows)")
            else:
                print(f"  WARNING: Run {run_id} chats not found at {file_path}")
                
    print(f"Success! Saved to {output_file} ({total_rows} total rows)")
    return total_rows

if __name__ == "__main__":
    start_run = 29
    end_run = 48
    
    # Aggregate Features
    feat_df = aggregate_features(start_run, end_run, "CHZZK_Features_29_48.xlsx")
    
    # Aggregate Chats
    chat_count = aggregate_chats(start_run, end_run, "CHZZK_Chats_29_48.csv")
    
    print("\nFinal Audit:")
    if feat_df is not None:
        print(f"Total Feature Rows: {len(feat_df)}")
        print(f"Unique Run IDs in Features: {feat_df['run_id'].nunique()}")
    print(f"Total Chat Rows: {chat_count}")
