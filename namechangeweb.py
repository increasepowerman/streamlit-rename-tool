import streamlit as st
import os
import shutil
import zipfile
import tempfile
import webbrowser
import threading
import time
from datetime import datetime
from pathlib import Path
import pandas as pd  # 强制导入pandas

# 页面配置
st.set_page_config(
    page_title="网页版批量改名工具（复制重命名）",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 修复：仅本地运行时自动打开浏览器
def auto_open_browser(port=8501):
    """启动后自动打开浏览器（仅本地运行时生效）"""
    if "STREAMLIT_SERVER_BASE_URL_PATH" in os.environ:
        return  # Cloud环境跳过
    def open_browser():
        time.sleep(2)
        url = f"http://localhost:{port}"
        webbrowser.open_new(url)
    thread = threading.Thread(target=open_browser, daemon=True)
    thread.start()

# 补全上下文（消除警告）
from streamlit.runtime.scriptrunner import get_script_run_ctx, add_script_run_ctx
ctx = get_script_run_ctx()
if ctx:
    add_script_run_ctx(ctx)

# 自定义样式
st.markdown("""
    <style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        font-size: 16px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #388E3C;
    }
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# 初始化会话状态
def init_session_state():
    default_state = {
        "temp_dir": "/tmp" if "STREAMLIT_SERVER_BASE_URL_PATH" in os.environ else tempfile.mkdtemp(),
        "original_files": [],
        "new_names": [],
        "renamed_folder": "",
        "zip_path": ""
    }
    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value
init_session_state()

# ---------------- 核心工具函数（修复Cloud兼容） ----------------
def copy_folder_to_temp(uploaded_files, temp_base_dir):
    """修复：适配Cloud的临时目录权限"""
    copy_dir = os.path.join(temp_base_dir, f"rename_copy_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(copy_dir, exist_ok=True, mode=0o777)  # 增加权限
    
    file_list = []
    for file in uploaded_files:
        # 修复：处理特殊字符文件名
        safe_filename = os.path.basename(file.name).replace(" ", "_").replace("/", "_").replace("\\", "_")
        file_path = os.path.join(copy_dir, safe_filename)
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        file_list.append({
            "original_name": file.name,
            "original_path": file_path,
            "new_name": file.name
        })
    return copy_dir, file_list

def batch_rename_files(file_list, copy_dir):
    """批量重命名（兼容Cloud）"""
    renamed_files = []
    fail_list = []
    new_names = st.session_state.new_names + [f["original_name"] for f in file_list[len(st.session_state.new_names):]]

    for idx, file_info in enumerate(file_list):
        old_name = file_info["original_name"]
        old_path = file_info["original_path"]
        new_name = new_names[idx].strip()

        if not new_name:
            fail_list.append(f"{old_name}：新名称不能为空")
            continue

        old_ext = Path(old_name).suffix
        new_name_full = new_name + old_ext if not new_name.endswith(old_ext) else new_name
        # 修复：Cloud路径拼接
        new_path = os.path.join(copy_dir, new_name_full.replace(" ", "_"))
        suffix = 1
        while os.path.exists(new_path) and new_path != old_path:
            new_path = os.path.join(copy_dir, f"{Path(new_name).stem}_{suffix}{old_ext}")
            suffix += 1

        try:
            os.rename(old_path, new_path)
            renamed_files.append({
                "original_name": old_name,
                "new_name": os.path.basename(new_path)
            })
        except Exception as e:
            fail_list.append(f"{old_name}：重命名失败 - {str(e)}")
    return renamed_files, fail_list

def zip_folder(folder_path, zip_output_path):
    """修复：Cloud压缩包权限"""
    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(folder_path))
                zipf.write(file_path, arcname)

# ---------------- 网页界面 ----------------
auto_open_browser(port=8501)

st.title("🔄 网页版批量文件重命名工具")
st.caption("✅ Streamlit Cloud 兼容版 | ✅ 复制原文件后重命名 | ✅ 下载压缩包")
st.divider()

# 第一步：上传文件
st.subheader("📤 第一步：上传需要重命名的文件（可多选）")
uploaded_files = st.file_uploader(
    "选择需要改名的文件（支持多选）",
    accept_multiple_files=True,
    help="注：所有操作仅处理副本，不会修改本地原文件"
)

if uploaded_files and st.button("📁 复制文件到临时目录并加载"):
    with st.spinner("正在复制文件..."):
        copy_dir, file_list = copy_folder_to_temp(uploaded_files, st.session_state.temp_dir)
        st.session_state.original_files = file_list
        st.session_state.new_names = [f["new_name"] for f in file_list]
        st.session_state.renamed_folder = copy_dir
        st.success(f"✅ 成功复制 {len(file_list)} 个文件到临时目录")
        st.session_state.zip_path = ""

# 第二步：编辑新文件名
if st.session_state.original_files:
    st.subheader("✏️ 第二步：编辑新文件名")
    table_data = {
        "序号": list(range(1, len(st.session_state.original_files) + 1)),
        "原文件名": [f["original_name"] for f in st.session_state.original_files],
        "新文件名": st.session_state.new_names
    }
    edited_df = st.data_editor(
        table_data,
        column_config={
            "序号": st.column_config.NumberColumn("序号", disabled=True),
            "原文件名": st.column_config.TextColumn("原文件名", disabled=True),
            "新文件名": st.column_config.TextColumn("新文件名", required=True)
        },
        hide_index=True,
        key="name_editor"
    )
    if not edited_df.empty and len(edited_df["新文件名"]) == len(st.session_state.new_names):
        st.session_state.new_names = edited_df["新文件名"].tolist()

    # 第三步：批量重命名+下载
    st.subheader("🚀 第三步：批量重命名并下载")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 执行批量重命名"):
            with st.spinner("正在重命名文件..."):
                renamed_files, fail_list = batch_rename_files(
                    st.session_state.original_files,
                    st.session_state.renamed_folder
                )
                if fail_list:
                    st.warning(f"⚠️ 重命名完成：成功 {len(renamed_files)} 个，失败 {len(fail_list)} 个")
                    st.text("失败详情：")
                    st.text("\n".join(fail_list))
                else:
                    st.success(f"🎉 全部重命名成功！共修改 {len(renamed_files)} 个文件")
                if renamed_files:
                    st.subheader("📋 重命名结果")
                    result_df = pd.DataFrame(renamed_files)
                    st.dataframe(result_df, hide_index=True)

    with col2:
        if st.session_state.renamed_folder and os.path.exists(st.session_state.renamed_folder):
            if not st.session_state.zip_path or not os.path.exists(st.session_state.zip_path):
                zip_filename = f"重命名文件_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                st.session_state.zip_path = os.path.join(st.session_state.temp_dir, zip_filename)
                zip_folder(st.session_state.renamed_folder, st.session_state.zip_path)
            if os.path.exists(st.session_state.zip_path):
                with open(st.session_state.zip_path, "rb") as f:
                    st.download_button(
                        label="📥 下载重命名后的文件（ZIP）",
                        data=f,
                        file_name=zip_filename,
                        mime="application/zip"
                    )
            else:
                st.warning("⚠️ 压缩包生成失败，请重试")

# 清理临时文件（适配Cloud）
st.sidebar.subheader("🗑 清理临时文件")
if st.sidebar.button("清空所有临时文件"):
    try:
        shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
        st.session_state.temp_dir = "/tmp" if "STREAMLIT_SERVER_BASE_URL_PATH" in os.environ else tempfile.mkdtemp()
        st.session_state.original_files = []
        st.session_state.new_names = []
        st.session_state.renamed_folder = ""
        st.session_state.zip_path = ""
        st.sidebar.success("✅ 已清空临时文件")
    except Exception as e:
        st.sidebar.error(f"❌ 清理失败：{str(e)}")

# 使用说明
st.sidebar.subheader("💡 使用说明")
st.sidebar.markdown("""
1. 上传需要重命名的文件（可多选）；
2. 点击「复制文件到临时目录」生成副本；
3. 编辑「新文件名」列（无需输入后缀）；
4. 执行重命名后下载压缩包；
5. 完成后清空临时文件。
""")
st.sidebar.warning("⚠️ 注：Cloud环境临时文件会在应用休眠后自动清理")
