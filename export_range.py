import sys
import os
import pandas as pd
from sqlalchemy import create_engine

# Add parent dir to path to import configs
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from configs.settings import get_settings

def export_range(start_id, end_id, table, output_prefix):
    settings = get_settings()
    engine = create_engine(settings.sqlalchemy_url)
    
    query = f"SELECT * FROM {table} WHERE run_id BETWEEN {start_id} AND {end_id}"
    
    print(f"Exporting {table} for run_id {start_id} to {end_id}...")
    try:
        csv_file = f"{output_prefix}_{start_id}_{end_id}.csv"
        excel_file = f"{output_prefix}_{start_id}_{end_id}.xlsx"
        
        # Use chunking for memory efficiency
        chunksize = 50000
        first_chunk = True
        
        for df_chunk in pd.read_sql(query, engine, chunksize=chunksize):
            mode = 'w' if first_chunk else 'a'
            header = True if first_chunk else False
            df_chunk.to_csv(csv_file, index=False, mode=mode, header=header, encoding='utf-8-sig')
            first_chunk = False
            print(f"Exported chunk of {len(df_chunk)} rows...")

        print(f"Success! Full export to {csv_file}")
        
        # Export to Excel only if it's small (Features table usually is)
        if table == "minute_features":
            df_full = pd.read_csv(csv_file)
            df_full.to_excel(excel_file, index=False)
            print(f"Exported to {excel_file}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python export_range.py <start_id> <end_id>")
        sys.exit(1)
        
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    
    # Export features
    export_range(start, end, "minute_features", "CHZZK_Features")
    
    # Export chats
    export_range(start, end, "chat_messages_raw", "CHZZK_Chats")
