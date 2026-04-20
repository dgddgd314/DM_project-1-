import pandas as pd
import os

def convert_csv_to_excel(csv_path, excel_path):
    try:
        print(f"Reading {csv_path}...")
        # CHZZK crawler specifically uses utf-8-sig or utf-8
        try:
            df = pd.read_csv(csv_path)
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding='cp949') # fallback for some Korean encodings if needed

        print(f"Converting to {excel_path} (Rows: {len(df)})...")
        # Use openpyxl as engine
        df.to_excel(excel_path, index=False, engine='openpyxl')
        print(f"Successfully converted {csv_path} to {excel_path}")
    except Exception as e:
        print(f"Error converting {csv_path}: {e}")

if __name__ == "__main__":
    # Convert features again just in case, but primary focus is chat
    convert_csv_to_excel("run29_chats.csv", "CHZZK_Session_29_Raw_Chats.xlsx")
