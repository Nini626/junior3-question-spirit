import streamlit as st
import base64
from zhipuai import ZhipuAI
import pandas as pd
from datetime import datetime

# ---------- 页面设置（完全保留原代码） ----------
st.set_page_config(page_title="错题订正·初三数理化", page_icon="📐")
st.title("📐 九年级数理化错题精灵")

# ---------- 新增：一人一码专属验证逻辑 ----------
# 读取用户使用码表（和app.py同目录的user_codes.csv）
@st.cache_data
def load_user_codes():
    try:
        df = pd.read_csv("user_codes.csv")
        # 统一格式处理，避免数字/日期格式问题
        df["使用码"] = df["使用码"].astype(str)
        df["有效期"] = pd.to_datetime(df["有效期"]).dt.date
        return df
    except Exception as e:
        st.error(f"用户码表加载失败：{e}")
        return pd.DataFrame(columns=["用户名", "使用码", "有效期"])

# 加载用户码表
df_codes = load_user_codes()

# 初始化登录状态
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "current_username" not in st.session_state:
    st.session_state["current_username"] = ""

# 未登录时仅显示登录界面
if not st.session_state["authenticated"]:
    user_code = st.text_input("🔐 请输入你的专属使用码", type="password")
    if st.button("验证"):
        # 1. 检查使用码是否存在
        match_row = df_codes[df_codes["使用码"] == user_code]
        if len(match_row) == 0:
            st.error("使用码无效，请联系管理员获取～")
        else:
            # 2. 检查使用码是否过期
            expire_date = match_row.iloc[0]["有效期"]
            today = datetime.today().date()
            if today > expire_date:
                st.error(f"使用码已过期（有效期至{expire_date}），请联系管理员续期～")
            else:
                # 3. 验证通过，记录登录状态
                st.session_state["authenticated"] = True
                st.session_state["current_username"] = match_row.iloc[0]["用户名"]
                st.rerun()
    # 未登录时终止后续代码执行
    st.stop()

# 验证通过后显示欢迎信息
st.success(f"✅ 验证通过！欢迎你，{st.session_state['current_username']}")
st.info("💡 上传整面试卷或作业图片，AI老师会逐题批改订正")

# ---------- 以下为你原有的所有业务代码，完全未改动 ----------
# ---------- 连接智谱AI ----------
client = ZhipuAI(api_key=st.secrets["ZHIPUAI_API_KEY"])

# ---------- 学科选择 ----------
subject = st.selectbox("📚 请选择学科：", ["数学", "物理", "化学"])

# ---------- 双输入入口：上传 + 拍照 ----------
uploaded_image = st.file_uploader("📷 上传错题图片（jpg/png）：", type=["jpg", "jpeg", "png"])
captured_image = st.camera_input("📸 直接拍照上传：")

# 优先使用拍照的图片
if captured_image is not None:
    image_to_process = captured_image
elif uploaded_image is not None:
    image_to_process = uploaded_image
else:
    image_to_process = None

# ---------- 新提示词 ----------
prompt_dict = {
    "数学": (
        "你是一位采用苏格拉底式教学法的九年级数学老师。用户会上传一整面作业或试卷的图片，里面可能包含多道题目。"
        "请按以下规则逐题处理："
        "1. 识别图片中所有题目，并用编号标记（如第1题、第2题……）。"
        "2. 对每一道题，先判断学生答案是否正确。"
        "3. 如果答案错误，请采用苏格拉底式提问法进行订正：不要直接给出正确解法，而是通过一连串引导性问题，启发学生自己发现错误所在，并一步步走向正确答案。每个问题后留出停顿，等待学生思考。讲解中必须关联课本知识点（如九年级数学的二次函数、圆、相似三角形等）。"
        "4. 最后，针对这道错题，出一道同类型、同难度的类似题供学生练习，并给出参考答案。"
        "5. 如果某道题不是数学内容（如英语），请标注“此题非数学题，跳过”。"
        "请用清晰的分隔线隔开不同题目，并使用友好鼓励的语气。"
        "现在，立即分析图片内容，不要输出任何开场白或等待指令，直接开始逐题处理。"
    ),
    "物理": (
        "你是一位采用苏格拉底式教学法的九年级物理老师。用户会上传一整面作业或试卷的图片，里面可能包含多道题目。"
        "请按以下规则逐题处理："
        "1. 识别图片中所有题目，并用编号标记。"
        "2. 对每一道题，先判断学生答案是否正确。"
        "3. 如果错误，采用苏格拉底式提问法订正，关联课本概念。"
        "4. 最后，出一道同类题并附参考答案。"
        "5. 非物理题标注跳过。"
        "现在，立即分析图片内容，不要输出任何开场白。"
    ),
    "化学": (
        "你是一位采用苏格拉底式教学法的九年级化学老师。用户会上传一整面作业或试卷的图片，里面可能包含多道题目。"
        "请按以下规则逐题处理："
        "1. 识别图片中所有题目，并用编号标记。"
        "2. 对每一道题，先判断学生答案是否正确。"
        "3. 如果错误，采用苏格拉底式提问法订正，关联课本知识点。"
        "4. 最后，出一道同类题并附参考答案。"
        "5. 非化学题标注跳过。"
        "现在，立即分析图片内容，不要输出任何开场白。"
    ),
}

# ---------- 开始分析 ----------
if st.button("✨ 开始智能订正"):
    if image_to_process is None:
        st.warning("请上传图片或拍照哦～")
        st.stop()

    # 读取并编码图片
    image_bytes = image_to_process.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    # 构建用户消息
    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
        }
    ]

    with st.spinner(f"AI {subject}老师正在逐题分析……"):
        response = client.chat.completions.create(
            model="glm-4.6v",
            messages=[
                {"role": "system", "content": prompt_dict[subject]},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
        )
        answer = response.choices[0].message.content

    st.subheader(f"📖 {subject}老师批改")
    st.write(answer)
