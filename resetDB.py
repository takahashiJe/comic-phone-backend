import os
from sqlalchemy import create_engine
from main import Base, engine  # main.py から Base と engine をインポート

DATABASE_FILE = "./comments.db"

def reset_database():
    # データベースファイルを削除
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)
        print(f"{DATABASE_FILE} was deleted.")
    else:
        print(f"{DATABASE_FILE} does not exist.")
    
    # テーブルスキーマを再作成
    Base.metadata.create_all(bind=engine)
    print("Database schema recreated.")

if __name__ == "__main__":
    reset_database()
