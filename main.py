import requests
import configparser
import re
import os
from natsort import natsorted
from typing import List, Dict, Any, Optional, Tuple

config = configparser.ConfigParser()
if os.path.exists('key.ini'):
    config.read('key.ini')

ANNICT_TOKEN = config['API']['key'] if 'API' in config and 'key' in config['API'] else ''
BASE_URL = "https://api.annict.com/v1/"

def extract_episode_number(text: str) -> Optional[int]:
    """number_textからエピソードの数値を抽出する。"""
    match = re.search(r'(\d+)(?:\.\d+)?', text)
    if match:
        return int(match.group(1))
    return None

def getEpisodes(work_id: int) -> List[Tuple[int, str]]:
    """作品IDに基づいてエピソード一覧を取得し、連番とタイトルのリストを返す。"""
    if not ANNICT_TOKEN:
        print("エラー: key.ini に Annict API トークンが設定されていません。")
        return []

    url = BASE_URL + "episodes"
    headers = {
        "Authorization": "Bearer " + ANNICT_TOKEN
    }
    params = {
        "filter_work_id": work_id,
        "page": 1,
        "per_page": 50,
        "sort_sort_number": "asc"
    }
    r = requests.get(url, headers=headers, params=params)
    
    episode_list = []

    if r.status_code == 200:
        data = r.json()
        print("-" * 30)
        print(f"作品ID {work_id} のエピソード一覧")
        
        for episode in data.get("episodes", []):
            episode_num_raw = episode["number"]
            
            if isinstance(episode_num_raw, (int, float)):
                episode_num = int(episode_num_raw)
            else:
                episode_num = extract_episode_number(episode["number_text"] or "")
            
            episode_title = episode["title"] or '（タイトルなし）'
            
            print(f"NUM: {episode_num if episode_num is not None else 'N/A'} | Title: {episode_title}")

            if episode_num is not None:
                 # ファイル名に使用できない文字を除去
                 safe_title = re.sub(r'[\\/:*?"<>|]', '_', episode_title)
                 episode_list.append((episode_num, safe_title))
                 
        print("-" * 30)
        return episode_list
    else:
        print(f"Error: {r.status_code}")
        try:
            print(r.json())
        except requests.exceptions.JSONDecodeError:
            print(r.text)
        return []


def getWork(query: str) -> List[Dict[str, Any]]:
    """Annict APIで作品を検索し、一覧表示してリストを返す。"""
    if not ANNICT_TOKEN:
        print("エラー: key.ini に Annict API トークンが設定されていません。")
        return []

    url = BASE_URL + "works"
    headers = {
        "Authorization": "Bearer " + ANNICT_TOKEN
    }
    params = {
        "filter_title": query,
        "page": 1,
        "per_page": 30,
        "sort_season": "asc"
    }
    r = requests.get(url=url, headers=headers, params=params)
    
    if r.status_code == 200:
        data = r.json()
        works = data.get("works", [])
        
        if not works:
            print("検索結果は見つかりませんでした。")
            return []
            
        print("-" * 30)
        print("検索結果:")
        for i, work in enumerate(works):
            print(f"[{i+1}] ID: {work['id']} | Title: {work['title']}")
        print("-" * 30)
        
        return works
    else:
        print(f"Error: {r.status_code}")
        try:
            print(r.json())
        except requests.exceptions.JSONDecodeError:
            print(r.text)
        return []


def rename_files_with_titles(episode_titles: List[Tuple[int, str]], work_title: str):
    """
    Annictから取得したエピソードタイトルと連番を使用してリネームを実行する。
    ファイル形式: [連番] - [エピソードタイトル].[拡張子]
    """
    if not episode_titles:
        print("エラー: エピソード情報が取得できなかったため、リネームを実行できません。")
        return
        
    folder_path = input("リネーム対象フォルダのパスを入力: ")
    folder_path = os.path.normpath(folder_path)

    if not os.path.isdir(folder_path):
        print(f"エラー: 指定されたパス '{folder_path}' は無効なフォルダです。")
        return

    # 1. ファイルのフィルタリング
    all_files = os.listdir(folder_path)
    video_files = []
    for file_name in all_files:
        if file_name.lower().endswith(('.mp4', '.mkv')):
            video_files.append(file_name)

    if not video_files:
        print("指定されたフォルダ内に .mp4 または .mkv ファイルが見つかりませんでした。")
        return
    
    # 2. ファイルのソート (natsortによる自然順ソート)
    sorted_files_all = natsorted(video_files)
    
    print("-" * 30)
    print("【ソートされたファイル一覧】")
    for i, file_name in enumerate(sorted_files_all):
        print(f"[{i+1}] {file_name}")
    print("-" * 30)

    # 3. オフセット（開始ファイル番号）の入力
    start_file_num_input = input(f"何番目のファイルからリネームを適用しますか？ (1から, デフォルト: 1): ")
    try:
        start_file_index = int(start_file_num_input) - 1 if start_file_num_input else 0
        if start_file_index < 0 or start_file_index >= len(sorted_files_all):
             raise ValueError
    except ValueError:
        print("エラー: 開始ファイル番号は1以上の整数で、ファイルリストの範囲内で入力してください。")
        return

    # リネーム対象のファイルリストをスライス
    sorted_files = sorted_files_all[start_file_index:]
    
    # ファイル数チェック
    if len(sorted_files) > len(episode_titles):
        print(f"⚠️ 警告: リネーム対象のファイル数 ({len(sorted_files)}) が、取得したエピソード数 ({len(episode_titles)}) よりも多いです。")
        print("続行すると、超過分のファイルはリネームされません。")
        confirmation = input("続行しますか？ (y/N): ").lower()
        if confirmation != 'y':
            print("リネームをキャンセルしました。")
            return
    
    # 4. リネーム計画の作成と表示
    rename_plan = []
    print("\n【リネーム計画】")
    
    limit = min(len(sorted_files), len(episode_titles))
    
    for i in range(limit):
        old_name = sorted_files[i]
        episode_num, episode_title = episode_titles[i]
        
        _, ext = os.path.splitext(old_name)
        
        num_str = str(episode_num).zfill(2)
        
        # 新しい形式: [連番] - [エピソードタイトル].[拡張子]
        new_name = f"{num_str} - {episode_title}{ext}"
        
        rename_plan.append((old_name, new_name))
        
        print(f"'{old_name}' -> '{new_name}'")

    print("-" * 30)
    
    # 5. 実行確認
    confirmation = input("上記の計画でリネームを実行しますか？ (y/N): ").lower()
    
    if confirmation == 'y':
        print("\nリネームを実行します...")
        for old_name, new_name in rename_plan:
            old_path = os.path.join(folder_path, old_name)
            new_path = os.path.join(folder_path, new_name)
            
            try:
                os.rename(old_path, new_path)
                print(f"  リネーム成功: '{old_name}' から '{new_name}' に変更しました。")
            except OSError as e:
                print(f"  ❌ リネームエラー: {old_name} -> {new_name} ({e})")
        print("\nリネームが完了しました。")
    else:
        print("リネームをキャンセルしました。")


def main():
    """メイン処理。モード選択と処理の実行を行う。"""
    print("Annict API クライアント")
    mode = input("モードを選択\n[1] 作品をタイトルで検索\n[2] エピソードをIDで取得\n番号を入力 (1-2):\t")
    
    if mode == "1":
        query = input("検索キーワードを入力: ")
        works_list = getWork(query)
        
        if not works_list:
            return

        try:
            selection = input("表示したい作品の番号を入力 (1から): ")
            selection_index = int(selection) - 1
        except ValueError:
            print("入力が無効です。（数値を入力してください）")
            return
        
        if 0 <= selection_index < len(works_list):
            selected_work = works_list[selection_index]
            work_id = selected_work["id"]
            work_title = selected_work["title"]
            
            print(f"選択された作品: {work_title}")
            
            episode_titles_list = getEpisodes(work_id)
            
            print("-" * 30)
            rename_confirm = input("続けてファイルリネームを実行しますか？ (y/N): ").lower()
            
            if rename_confirm == 'y':
                if episode_titles_list:
                    print("\n【ファイルリネームモードに移行】")
                    rename_files_with_titles(episode_titles_list, work_title)
                else:
                    print("エピソード情報が取得できなかったため、リネームをスキップしました。")
            else:
                print("ファイルリネームをスキップしました。")
            
        else:
            print("入力が無効です。（リストの範囲外の番号です）")
            
    elif mode == "2":
        id_input = input("作品IDを入力: ")
        try:
            work_id = int(id_input)
            getEpisodes(work_id)
        except ValueError:
            print("入力が無効です。（IDは数値で入力してください）")
            
    else:
        print("入力が無効です。\n終了します。")

if __name__ == "__main__":
    if not os.path.exists('key.ini'):
        print("⚠️ 'key.ini' が見つかりません。Annict API機能を利用する場合は、実行前に API キーを設定してください。")
    
    main()
