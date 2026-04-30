"""
members.txt を読み込んで index.html のメンバーデータを更新するスクリプト
使い方: python update_members.py
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
MEMBERS_FILE = BASE_DIR / "members.txt"
HTML_FILE = BASE_DIR / "index.html"


def parse_members(txt_path):
    """members.txt を解析して {male: [...], female: [...]} を返す"""
    male = []
    female = []
    current_section = None

    for raw_line in txt_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[男性]":
            current_section = "male"
        elif line == "[女性]":
            current_section = "female"
        elif current_section == "male":
            male.append(line)
        elif current_section == "female":
            female.append(line)

    return male, female


def build_raw_js(male, female):
    """JS の RAW 定数を生成する"""
    def format_names(names):
        chunks = [names[i:i+6] for i in range(0, len(names), 6)]
        lines = []
        for chunk in chunks:
            lines.append("                " + ", ".join(f"'{n}'" for n in chunk))
        return ",\n".join(lines)

    return (
        "const RAW = {\n"
        f"            male: [{format_names(male)}],\n"
        f"            female: [{format_names(female)}]\n"
        "        };"
    )


def update_html(html_path, new_raw_js):
    """index.html 内の RAW 定数を置き換える"""
    html = html_path.read_text(encoding="utf-8")

    pattern = r"const RAW = \{.*?\};"
    new_html, count = re.subn(pattern, new_raw_js, html, flags=re.DOTALL)

    if count == 0:
        print("エラー: index.html 内に RAW 定数が見つかりませんでした。")
        return False

    html_path.write_text(new_html, encoding="utf-8")
    return True


def main():
    print("=== KALIDIAメンバー更新ツール ===\n")

    # 1. members.txt を読み込む
    print(f"読み込み: {MEMBERS_FILE}")
    male, female = parse_members(MEMBERS_FILE)
    print(f"  男性: {len(male)}名 → {', '.join(male)}")
    print(f"  女性: {len(female)}名 → {', '.join(female)}")

    if not male and not female:
        print("エラー: メンバーが0人です。members.txt を確認してください。")
        return

    # 2. JS コードを生成
    new_raw_js = build_raw_js(male, female)

    # 3. index.html を更新
    print(f"\n更新: {HTML_FILE}")
    if update_html(HTML_FILE, new_raw_js):
        print("完了: index.html のメンバーデータを更新しました。")
    else:
        print("更新に失敗しました。")


if __name__ == "__main__":
    main()
