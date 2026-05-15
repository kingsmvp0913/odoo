"""
====================================================================
Odoo 自動更新工具
====================================================================
作者：
    stevenLin
開發環境：
    windows
功能：
    1. 修改View直接F5，需要upgrade的時候直接重啟，不須額外操作
    2. 和直接-u差在不用手動設定模組名稱，也會減少不必要的升級
使用方式：
    1. 把檔案放到專案下
    2. 設定參數
    3. vscode 的 launch.json 內把啟動程式(program)改成 auto_upgrade.py
注意事項：
    1. 此工具為「開發用途」，不可用於 production、測試環境
    2. auto -u 會觸發 module upgrade（可能影響資料）
    3. 後續可以加上git diff來判斷是否有實際code變更，加快檢查速度

====================================================================
"""

import os
import subprocess
import glob
import configparser
import time
import xml.etree.ElementTree as ET


# =========================================================
# 基本設定
# =========================================================

# Python 虛擬環境（必須）
PYTHON = "C:/odoo/venv_odoo18/Scripts/python.exe"
# Odoo 主程式
ODOO_BIN = "C:/odoo/odoo-18.0/odoo-bin"
# Odoo 設定檔
ODOO_CONF = "C:/odoo/odoo-18.0/odoo.conf"
# 客製模組資料夾（只掃這裡做 auto upgrade 判斷）
ADDONS_PATH = "C:/online_addons/18"
# 指定資料庫（可以用環境變數 ODOO_DB 設定）
DB_NAME = os.getenv("ODOO_DB", "")  # 預設空白代表不指定資料庫
# 時間判斷，按自己的習慣調整（秒）
CHECK_WINDOW = 60

# =========================================================
# 判斷是否是view xml
# =========================================================
def is_view_xml(file):
    try:
        tree = ET.parse(file)
        root = tree.getroot()
        for record in root.findall("record"):
            model = record.get("model")
            if model == "ir.ui.view":
                return True
        return False
    except Exception:
        # 解析失敗 → 保守當作 schema（比較安全）
        return False

# =========================================================
# 偵測 module 是否有變更
# 只掃 custom addons
# 判斷檔案修改時間（mtime）
# 判斷「最近幾秒內有變更」才算需要 upgrade，可按照自身習慣調整
# =========================================================
def detect_changed_modules():

    modules = set()
    now = time.time()

    for addons_dir in ADDONS_PATH.split(','):
        addons_dir = addons_dir.strip() # 去除可能存在的空格
        if not os.path.isdir(addons_dir):
            continue

        # ====================================================================
        # 【關鍵修正 1】用 * 展開這一層 addons 目錄底下的所有子資料夾（如 idx_project）
        # ====================================================================
        for path in glob.glob(f"{addons_dir}/*"):
            if not os.path.isdir(path):
                continue

            # 排除 git 等系統隱藏資料夾，避免 Windows 遍歷卡死
            if os.path.basename(path).startswith('.'):
                continue

            # 【關鍵修正 2】此時取得的才是真正的 Odoo 模組名稱（如 idx_project）
            module = os.path.basename(path)

            has_strong_change = False   # python / schema
            has_soft_change = False     # csv / data

            # =================================================
            # Python + schema XML（一定要upgrade）
            # =================================================
            for pattern in ("**/*.py", "**/*.xml"):
                for file in glob.glob(f"{path}/{pattern}", recursive=True):
                    # 排除 git 歷史紀錄檔案，大幅提升 Windows 掃描效能
                    if '.git' in file:
                        continue
                    try:
                        if now - os.path.getmtime(file) > CHECK_WINDOW:
                            continue
                        if is_view_xml(file):
                            continue
                        
                        has_strong_change = True
                    except:
                        pass

            # =================================================
            # CSV / data（要看類型）
            # =================================================
            for file in glob.glob(f"{path}/**/*.csv", recursive=True):
                if '.git' in file:
                    continue
                try:
                    if now - os.path.getmtime(file) > CHECK_WINDOW:
                        continue

                    filename = file.lower()
                    if "ir.model.access" in filename or "security" in filename:
                        has_strong_change = True
                    else:
                        has_soft_change = True
                except:
                    pass

            if has_strong_change:
                modules.add(module)
            if has_soft_change and module not in modules:
                modules.add(module)
            
    return list(modules)

changed_modules = detect_changed_modules()


# =========================================================
# 組合 Odoo 啟動參數
# =========================================================
args = [
    PYTHON,
    ODOO_BIN,
    "-c", ODOO_CONF,
]

# 指定資料庫（如果有設定 DB_NAME）
if DB_NAME:
    args += ["-d", DB_NAME]

# =========================================================
# 開發模式：
# xml      → view 即時 reload
# qweb     → report/template 更新
# assets   → JS/CSS 不打包
# =========================================================
args += [
    "--dev=xml,qweb,assets"
]

# =========================================================
# Auto Upgrade 邏輯
# =========================================================
AUTO_UPGRADE = os.getenv("ODOO_AUTO_UPGRADE", "1")

if AUTO_UPGRADE == "1" and changed_modules:
    args += ["-u", ",".join(changed_modules)]

# =========================================================
# Debug 輸出
# =========================================================
print("\n==========================================================================================\n")
print("自動升級工具")
print("有修改的模組:", changed_modules)
print("CMD:")
print(" ".join(args))
print("\n==========================================================================================\n\n\n")

# =========================================================
# 執行 Odoo
# =========================================================
subprocess.run(args)