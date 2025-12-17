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
import pandas as pd  # 新增：补全缺失的pandas导入（原代码用了但没导入）
# 新增：导入上下文相关模块
from streamlit.runtime.scriptrunner import get_script_run_ctx, add_script_run_ctx

# 页面配置
st.set_page_config(
    page_title="网页版批量改名工具（复制重命名）",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)


# 新增：强制自动打开浏览器（核心修复）
def auto_open_browser(port=8501):
    """启动后自动打开浏览器"""

    def open_browser():
        time.sleep(2)  # 等待Streamlit服务启动
        url = f"http://localhost:{port}"
        webbrowser.open_new(url)

    # 启动子线程执行（避免阻塞Streamlit）
    thread = threading.Thread(target=open_browser, daemon=True)
    thread.start()


# 新增：补全Streamlit上下文（消除警告核心）
ctx = get_script_run_ctx()
if ctx:
    add_script_run_ctx(ctx)

# 自定义样式美化
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
    .stTextInput>div>div>input {
        border-radius: 6px;
    }
    .stAlert {
        border-radius: 8px;
    }
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
        margin: 10px 0;
    }
    .uploadedFile {
        border-radius: 6px;
    }
    </style>
""", unsafe_allow_html=True)


# 初始化会话状态（优化赋值逻辑，避免空值）
def init_session_state():
    default_state = {
        "temp_dir": tempfile.mkdtemp(),
        "original_files": [],
        "new_names": [],
        "renamed_folder": "",
        "zip_path": ""
    }
    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value


# 执行初始化
init_session_state()


# ---------------- 核心工具函数 ----------------
def copy_folder_to_temp(uploaded_files, temp_base_dir):
    """将上传的文件夹（通过多文件上传模拟）复制到临时目录"""
    # 创建原文件夹副本目录
    copy_dir = os.path.join(temp_base_dir, f"原文件副本_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(copy_dir, exist_ok=True)

    file_list = []
    for file in uploaded_files:
        # 保存上传的文件到副本目录
        file_path = os.path.join(copy_dir, file.name)
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        file_list.append({
            "original_name": file.name,
            "original_path": file_path,
            "new_name": file.name  # 默认新名称=原名称
        })

    return copy_dir, file_list


def batch_rename_files(file_list, copy_dir):
    """批量重命名临时目录中的文件"""
    renamed_files = []
    fail_list = []
    # 确保new_names长度匹配
    new_names = st.session_state.new_names + [f["original_name"] for f in file_list[len(st.session_state.new_names):]]

    for idx, file_info in enumerate(file_list):
        old_name = file_info["original_name"]
        old_path = file_info["original_path"]
        new_name = new_names[idx].strip()

        # 校验新名称
        if not new_name:
            fail_list.append(f"{old_name}：新名称不能为空")
            continue

        # 分离后缀（自动保留）
        old_ext = Path(old_name).suffix
        new_name_full = new_name + old_ext if not new_name.endswith(old_ext) else new_name

        # 避免重复文件名
        new_path = os.path.join(copy_dir, new_name_full)
        suffix = 1
        while os.path.exists(new_path) and new_path != old_path:
            new_path = os.path.join(copy_dir, f"{Path(new_name).stem}_{suffix}{old_ext}")
            suffix += 1

        # 执行重命名
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
    """将文件夹打包为ZIP压缩包"""
    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                # 保留文件夹结构
                arcname = os.path.relpath(file_path, os.path.dirname(folder_path))
                zipf.write(file_path, arcname)


# ---------------- 网页界面 ----------------
# 启动时自动打开浏览器
auto_open_browser(port=8501)

st.title("🔄 网页版批量文件重命名工具")
st.caption("✅ 无需本地运行程序 | ✅ 复制原文件后重命名 | ✅ 下载重命名后的压缩包")
st.divider()

# 第一步：上传文件夹（通过多文件上传模拟，支持选择多个文件）
st.subheader("📤 第一步：上传需要重命名的文件（可多选）")
uploaded_files = st.file_uploader(
    "选择需要改名的文件（支持多选，会自动复制为新文件夹）",
    accept_multiple_files=True,
    help="注：网页无法直接访问本地文件夹，可多选文件上传（模拟文件夹）"
)

if uploaded_files and st.button("📁 复制文件到临时目录并加载"):
    with st.spinner("正在复制文件..."):
        copy_dir, file_list = copy_folder_to_temp(uploaded_files, st.session_state.temp_dir)
        st.session_state.original_files = file_list
        st.session_state.new_names = [f["new_name"] for f in file_list]  # 确保长度匹配
        st.session_state.renamed_folder = copy_dir
        st.success(f"✅ 成功复制 {len(file_list)} 个文件到临时目录：\n{copy_dir}")
        st.session_state.zip_path = ""  # 清空旧压缩包

# 第二步：编辑新文件名（表格形式）
if st.session_state.original_files:
    st.subheader("✏️ 第二步：编辑新文件名")
    # 生成编辑表格的数据源
    table_data = {
        "序号": list(range(1, len(st.session_state.original_files) + 1)),
        "原文件名": [f["original_name"] for f in st.session_state.original_files],
        "新文件名": st.session_state.new_names
    }

    # 展示可编辑的表格
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

    # 同步编辑后的新名称到会话状态（优化：仅当表格有数据时更新）
    if not edited_df.empty and len(edited_df["新文件名"]) == len(st.session_state.new_names):
        st.session_state.new_names = edited_df["新文件名"].tolist()

    # 第三步：批量重命名
    st.subheader("🚀 第三步：批量重命名并下载")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 执行批量重命名"):
            with st.spinner("正在重命名文件..."):
                renamed_files, fail_list = batch_rename_files(
                    st.session_state.original_files,
                    st.session_state.renamed_folder
                )
                # 展示结果
                if fail_list:
                    st.warning(f"⚠️ 重命名完成：成功 {len(renamed_files)} 个，失败 {len(fail_list)} 个")
                    st.text("失败详情：")
                    st.text("\n".join(fail_list))
                else:
                    st.success(f"🎉 全部重命名成功！共修改 {len(renamed_files)} 个文件")

                # 展示重命名对照表
                if renamed_files:
                    st.subheader("📋 重命名结果对照表")
                    result_df = pd.DataFrame(renamed_files)
                    st.dataframe(result_df, hide_index=True)

    # 第四步：打包并下载
    with col2:
        if st.session_state.renamed_folder and os.path.exists(st.session_state.renamed_folder):
            # 生成压缩包
            if not st.session_state.zip_path or not os.path.exists(st.session_state.zip_path):
                zip_filename = f"重命名后的文件_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                st.session_state.zip_path = os.path.join(st.session_state.temp_dir, zip_filename)
                zip_folder(st.session_state.renamed_folder, st.session_state.zip_path)

            # 提供下载按钮
            if os.path.exists(st.session_state.zip_path):
                with open(st.session_state.zip_path, "rb") as f:
                    st.download_button(
                        label="📥 下载重命名后的文件（ZIP压缩包）",
                        data=f,
                        file_name=os.path.basename(st.session_state.zip_path),
                        mime="application/zip"
                    )
            else:
                st.warning("⚠️ 压缩包生成失败，请重新执行重命名")

# 清理临时文件（可选：页面刷新时清理）
st.sidebar.subheader("🗑 清理临时文件")
if st.sidebar.button("清空所有临时文件"):
    try:
        # 递归删除临时目录
        shutil.rmtree(st.session_state.temp_dir)
        # 重建临时目录
        st.session_state.temp_dir = tempfile.mkdtemp()
        st.session_state.original_files = []
        st.session_state.new_names = []
        st.session_state.renamed_folder = ""
        st.session_state.zip_path = ""
        st.sidebar.success("✅ 已清空所有临时文件")
    except Exception as e:
        st.sidebar.error(f"❌ 清理失败：{str(e)}")

# 操作提示
st.sidebar.subheader("💡 使用说明")
st.sidebar.markdown("""
1. 点击「上传文件」选择需要重命名的文件（可多选）；
2. 点击「复制文件到临时目录」，生成原文件的副本；
3. 在表格中编辑「新文件名」列（无需输入后缀，自动保留）；
4. 点击「执行批量重命名」，修改临时目录中的文件名称；
5. 点击「下载压缩包」，获取重命名后的所有文件；
6. 下载完成后可清空临时文件释放空间。
""")

# 安全提示
st.sidebar.warning(
    "⚠️ 注意：\n1. 所有操作仅针对上传的文件副本，不会修改本地原文件；\n2. 临时文件会保存在服务器（本地），建议及时清理；\n3. 请勿上传敏感/加密文件。")

# 新增：主函数（兼容命令行启动）
if __name__ == "__main__":
    # 强制以Streamlit方式启动（关键！）
    import subprocess
    import sys

    # 检查是否已通过streamlit run启动
    if "streamlit" not in sys.argv[0]:
        script_path = os.path.abspath(__file__)
        # 执行streamlit run命令，并强制关闭无头模式
        subprocess.call([
            sys.executable, "-m", "streamlit", "run",
            script_path, "--server.headless=false",
            "--server.port=8501"
        ])