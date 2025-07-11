import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
import calendar
import json
import os

# --- 関数定義 ---
def load_and_prepare_data(data_file_path):
    """CSVデータを読み込み、ファイル名と共にDataFrameを返す"""
    try:
        with open(data_file_path, 'r', encoding='utf-8') as f:
            csv_data = f.read()
    except FileNotFoundError:
        st.error(f"シフトデータファイル ({data_file_path}) が見つかりません。")
        return None, data_file_path

    df = pd.read_csv(io.StringIO(csv_data.strip()), header=None)
    df.columns = ['週', 'イ', 'ロ', 'ハ', 'ニ', 'ホ', 'ヘ', 'ト']
    df = df.set_index('週')
    df = df.sort_index()
    return df, data_file_path

def flatten_shift_data(shift_df):
    """DataFrameのシフトデータを1次元のリストに変換する"""
    if shift_df is None:
        return []
    group_list = ['イ', 'ロ', 'ハ', 'ニ', 'ホ', 'ヘ', 'ト']
    flat_list = []
    for week_num in sorted(shift_df.index):
        for group in group_list:
            flat_list.append(shift_df.loc[week_num, group])
    return flat_list

def get_daily_kinmu(target_date, ref_date, ref_shift_index, flat_shift_list):
    """基準日と基準シフトからの日数差で、指定日の勤務、週、グループを計算して返す"""
    if not flat_shift_list:
        return "データなし", "-", "-"  # Return a tuple

    group_list = ['イ', 'ロ', 'ハ', 'ニ', 'ホ', 'ヘ', 'ト']
    day_difference = (target_date - ref_date).days
    total_shifts = len(flat_shift_list)

    # Calculate the target index in the flattened list (0-251)
    target_index = (ref_shift_index + day_difference) % total_shifts

    # From the target index, derive the week and group
    shift_table_week = (target_index // len(group_list)) + 1
    current_group_index = target_index % len(group_list)
    current_group = group_list[current_group_index]

    kinmu = flat_shift_list[target_index]

    return kinmu, shift_table_week, current_group

def create_calendar_html(year, month, get_kinmu_func):
    """指定された月のカレンダーHTMLを、スタイル付きで動的に生成する"""
    cal = calendar.Calendar(firstweekday=0)
    
    # HTMLの各部分をリストとして構築
    html_parts = [
        """
        <style>
        .month-table { border-collapse: collapse; width: 100%; }
        .month-table th { text-align: center; height: 40px; border: 1px solid #ddd; background-color: #f2f2f2; }
        .month-table td { width: 14.2%; height: 120px; vertical-align: top; padding: 5px; border: 1px solid #ddd; }
        .day-number { font-weight: bold; font-size: 1.3em; }
        .week-info { font-size: 0.9em; color: #888; display: block; }
        .kinmu { font-size: 1.1em; display: block; margin-top: 5px; }
        .other-month { background-color: #f9f9f9; }
        .other-month .day-number { color: #ccc; }
        .weekend-day { background-color: #f0f8ff; } /* 土曜日の薄い背景色 */
        .sunday-day { background-color: #ffe0e6; } /* 日曜日の薄いピンク系背景色 */
        </style>
        """,
        '<table class="month-table">',
        '<tr>'
    ]
    
    headers = ["月", "火", "水", "木", "金", "土", "日"]
    for day in headers:
        html_parts.append(f"<th>{day}</th>")
    html_parts.append('</tr>')

    for week in cal.monthdatescalendar(year, month):
        html_parts.append('<tr>')
        for day_date in week:
            td_class = []
            if day_date.month != month:
                td_class.append("other-month")
            
            if day_date.weekday() == 5: # 土曜日
                td_class.append("weekend-day")
            elif day_date.weekday() == 6: # 日曜日
                td_class.append("sunday-day")
            
            class_attr = f' class="{' '.join(td_class)}"' if td_class else ''

            if day_date.month != month:
                html_parts.append(f'<td{class_attr}><span class="day-number">{day_date.day}</span></td>')
            else:
                kinmu, shift_week, shift_group = get_kinmu_func(day_date)
                
                color = "black" # デフォルトの色を黒に設定

                if str(kinmu) == "公" or str(kinmu) == "休":
                    color = "red"
                elif "泊" in str(kinmu):
                    color = "blue"
                elif "明" in str(kinmu):
                    color = "green"
                
                html_parts.append(f'<td{class_attr}><span class="day-number">{day_date.day}</span>')
                html_parts.append(f'<span class="week-info">W{shift_week} {shift_group}</span>')
                html_parts.append(f'<span class="kinmu" style="color:{color};">{kinmu}</span></td>')
        html_parts.append('</tr>')
        
    html_parts.append("</table>")
    return "".join(html_parts)

# --- Streamlitアプリのメイン処理 ---
st.set_page_config(page_title="交代番シフトカレンダー", layout="wide")

col1, col2 = st.columns([0.7, 0.3]) # タイトルとサブヘッダーの幅を調整
with col1:
    st.title("交代番シフトカレンダー")
with col2:
    st.subheader("月間シフト")

# グローバル印刷用CSS
st.markdown("""
<style>
@media print {
    /* サイドバーを非表示にする */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    /* メインコンテンツを全幅にする */
    .main {
        width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    /* アプリ全体のパディングをなくす */
    .stApp {
        padding: 0 !important;
        margin: 0 !important;
    }
    /* タイトルとヘッダーの余白を調整 */
    h1, h2, h3, h4, h5, h6 {
        margin-top: 0 !important; /* ヘッダーの上マージンをゼロに */
        margin-bottom: 0 !important; /* ヘッダーの下マージンをゼロに */
    }
    h1 {
        font-size: 1.0em !important; /* タイトルのフォントサイズをさらに調整 */
    }
    h2 {
        font-size: 0.8em !important; /* サブヘッダーのフォントサイズをさらに調整 */
    }
    /* Streamlitのタイトルとサブヘッダーのコンテナのパディングを調整 */
    div[data-testid="stVerticalBlock"] > div:first-child > div:first-child {
        padding-bottom: 0 !important;
    }
    /* カレンダーテーブル全体のフォントサイズを調整 */
    .month-table {
        font-size: 0.8em !important;
    }
    .month-table th {
        height: 25px !important; /* ヘッダーの高さをさらに調整 */
    }
    .month-table td {
        height: 55px !important; /* セルの高さをさらに調整 */
        padding: 1px !important; /* パディングをさらに減らす */
    }
    .day-number {
        font-size: 0.8em !important;
    }
    .week-info {
        font-size: 0.5em !important;
    }
    .kinmu {
        font-size: 0.7em !important;
    }
}
</style>
""", unsafe_allow_html=True)

# --- 1. データと設定の準備 (サイドバーに配置) ---
st.sidebar.header("個人設定")
st.sidebar.info("カレンダー上の特定の日が、シフト表のどの勤務に対応するかを設定してください。")

CONFIG_FILE = "settings.json"
config = {}
try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    pass

ref_date_input = st.sidebar.date_input(
    "① 基準日",
    value=datetime.strptime(config.get("ref_date", "2025-07-14"), "%Y-%m-%d"),
    format="YYYY-MM-DD"
)
ref_week_input = st.sidebar.number_input(
    "② 基準日の週番号 (1-36)",
    min_value=1, max_value=36, value=config.get("ref_week", 9)
)
group_list = ['イ', 'ロ', 'ハ', 'ニ', 'ホ', 'ヘ', 'ト']
try:
    default_group_index = group_list.index(config.get("ref_group", "ハ"))
except ValueError:
    default_group_index = 0
ref_group_input = st.sidebar.selectbox(
    "③ 基準日の担当グループ",
    group_list,
    index=default_group_index
)

# プログラムフォルダ内のCSVファイルを取得
csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
if not csv_files:
    st.error("プログラムフォルダ内にCSVファイルが見つかりません。")
    st.stop()

default_selected_csv = config.get("selected_csv", "")
if default_selected_csv not in csv_files:
    default_selected_csv = csv_files[0]

selected_csv_file = st.sidebar.selectbox(
    "CSVファイルを選択",
    csv_files,
    index=csv_files.index(default_selected_csv)
)

shift_df, loaded_filename = load_and_prepare_data(selected_csv_file)
st.sidebar.markdown(
    f"""
    <div style="
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        margin-top: 10px; /* 上の要素との隙間を調整 */
        margin-bottom: 10px; /* 下の要素との隙間を調整 */
        background-color: #f9f9f9;
    ">
        <small>データソース:</small><br>
        <strong>{loaded_filename}</strong>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.write("") # ボタンを少し下に離すための空行

if st.sidebar.button("この設定を保存"):
    new_config = {
        "selected_csv": selected_csv_file,
        "ref_date": ref_date_input.strftime("%Y-%m-%d"),
        "ref_week": ref_week_input,
        "ref_group": ref_group_input
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_config, f, indent=4)
    st.sidebar.success("設定を保存しました！")

# --- 2. 表示する年月を選択 ---
current_date = datetime.now()
col_year, col_month = st.columns(2)
with col_year:
    target_year = st.number_input("年", min_value=2020, max_value=2050, value=current_date.year)
with col_month:
    target_month = st.number_input("月", min_value=1, max_value=12, value=current_date.month)

# --- 3. カレンダーの生成と表示 ---
try:
    # shift_df, loaded_filename = load_and_prepare_data(data_file_path_input) # この行は不要になる
    if shift_df is not None:
        # st.caption(f"データソース: {loaded_filename}") # この行は不要になる

        flat_shift_list = flatten_shift_data(shift_df)
        
        try:
            week_row_index = sorted(shift_df.index).index(ref_week_input)
        except ValueError:
            st.error(f"エラー: 指定された週番号 {ref_week_input} はデータに存在しません。")
            st.stop()
            
        group_col_index = group_list.index(ref_group_input)
        ref_shift_index = week_row_index * len(group_list) + group_col_index
        
        ref_date = ref_date_input

        # ラッパー関数を作成して、get_daily_kinmuに必要な引数を渡す
        def get_kinmu_for_calendar(target_date):
            return get_daily_kinmu(target_date, ref_date, ref_shift_index, flat_shift_list)

        # 新しい関数でHTMLを生成
        calendar_html = create_calendar_html(target_year, target_month, get_kinmu_for_calendar)
        
        st.markdown(calendar_html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"カレンダーの生成中にエラーが発生しました: {e}")