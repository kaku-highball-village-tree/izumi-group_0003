"""SQLiteの基本操作として、データベース作成、テーブル作成、1件登録、1件取得と表示を行うサンプル。"""

import sqlite3
from pathlib import Path
from sqlite3 import Connection, Cursor


def main() -> None:
    # データベースファイルのパスを設定する。
    pszDbFilePath: str = str(Path(__file__).resolve().parent / "sample_0001.db")

    # 接続オブジェクトの初期値を設定する。
    objConnection: Connection | None = None

    try:
        # SQLiteデータベースへ接続する。
        objConnection = sqlite3.connect(pszDbFilePath)

        # カーソルオブジェクトを生成する。
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

        # 指定された1件のデータを登録する。
        iPersonId: int = 1
        pszPersonName: str = "Taro"
        objCursor.execute(
            "INSERT INTO person (id, name) VALUES (?, ?)",
            (iPersonId, pszPersonName),
        )
        objConnection.commit()

        # 登録済みデータを全件取得する。
        objCursor.execute("SELECT * FROM person")
        objRows: list[tuple[int, str]] = objCursor.fetchall()

        # 取得した全レコードを1行ずつ表示する。
        objRow: tuple[int, str]
        for objRow in objRows:
            print(objRow)

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
