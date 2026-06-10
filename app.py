import streamlit as st
import base64
from zhipuai import ZhipuAI

# ---------- 页面设置 ----------
st.set_page_config(page_title="错题订正·初三数理化", page_icon="📐")
st.title("📐 九年级数理化错题精灵")

# ---------- 密码验证 ----------
VIP_PASSWORD = "ctjl2026"

if "ok" not in st.session_state:
    st.session_state.ok = False

if not st.session_state.ok:
    pwd = st.text_input("🔐 请输入使用密码", type="password")
    if st.button("验证"):
        if pwd == VIP_PASSWORD:
            st.session_state.ok = True
            st.rerun()
        else:
            st.error("密码错误，请付费获取～")
    st.stop()

# ---------- 连接智谱AI ----------
client = ZhipuAI(api_key=st.secrets["ZHIPUAI_API_KEY"])

# ---------- 学科选择 ----------
subject = st.selectbox("📚 请选择学科：", ["数学", "物理", "化学"])

st.success("✅ 验证通过！")
st.info("💡 上传整面试卷或作业图片，AI老师会逐题批改订正")

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