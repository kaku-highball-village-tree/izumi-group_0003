"""SQLiteから取得したデータを標準出力とCSVへ出力し、Excelで確認できるようにする最小サンプル。"""

import csv
import sqlite3
from pathlib import Path
from sqlite3 import Connection, Cursor


def main() -> None:
    # データベースファイルとCSVファイルのパスを設定する。
    pszDbFilePath: str = str(Path(__file__).resolve().parent / "sample_0002.db")
    pszCsvFilePath: str = str(Path(__file__).resolve().parent / "person_0002.csv")

    # データベース接続オブジェクトの初期値を設定する。
    objConnection: Connection | None = None

    try:
        # SQLiteデータベースへ接続する。
        objConnection = sqlite3.connect(pszDbFilePath)
        objCursor: Cursor = objConnection.cursor()

        # personテーブルを存在しない場合のみ作成する。
        objCursor.execute(
            """
            CREATE TABLE IF NOT EXISTS person (
                id INTEGER,
                name TEXT
            )
            """
        )

        # 1件のデータをINSERTする。
        iId: int = 1
        pszName: str = "Taro"
        objCursor.execute(
            "INSERT INTO person (id, name) VALUES (?, ?)",
            (iId, pszName),
        )
        objConnection.commit()

        # SELECT * FROM person を実行して全件取得する。
        objCursor.execute("SELECT * FROM person")
        objRows: list[tuple[int, str]] = objCursor.fetchall()

        # SELECT結果を標準出力へ1行ずつ表示する。
        objRow: tuple[int, str]
        for objRow in objRows:
            print(objRow)

        # SELECT結果をUTF-8 with BOMのCSVファイルへ出力する。
        with open(pszCsvFilePath, mode="w", newline="", encoding="utf-8-sig") as objCsvFile:
            objWriter: csv.writer = csv.writer(objCsvFile)
            objHeaderRow: list[str] = ["id", "name"]
            objWriter.writerow(objHeaderRow)

            for objRow in objRows:
                objWriter.writerow(objRow)

    except sqlite3.Error as objError:
        # 発生したSQLiteエラーを表示する。
        print(objError)
    except Exception as objError:
        # 発生したその他のエラーを表示する。
        print(objError)
    finally:
        # データベース接続を必ず終了する。
        if objConnection is not None:
            objConnection.close()


if __name__ == "__main__":
    main()
