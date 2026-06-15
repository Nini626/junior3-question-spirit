import streamlit as st
import base64
from zhipuai import ZhipuAI
import pandas as pd
from datetime import datetime, date
import requests
import json

# ---------- 页面设置 ----------
st.set_page_config(page_title="错题订正·初三数理化", page_icon="📐")
st.title("📐 九年级数理化错题精灵")

# ---------- GitHub 配置（从 secrets 读取） ----------
GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", "Nini626")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "junior3-question-spirit")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
CSV_PATH = "user_codes.csv"

# ---------- 回写 GitHub 的核心函数 ----------
def update_csv_on_github(df):
    """将绑定信息推回 GitHub，防止 Streamlit 重启后丢失数据"""
    if not GITHUB_TOKEN:
        st.warning("⚠️ 未配置 GitHub Token，绑定数据可能在应用重启后丢失，请联系管理员。")
        df[["用户名", "使用码", "有效期", "绑定手机号"]].to_csv("user_codes.csv", index=False, encoding="utf-8")
        return False

    try:
        csv_content = df[["用户名", "使用码", "有效期", "绑定手机号"]].to_csv(index=False, encoding="utf-8")
        csv_b64 = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")

        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}

        # 获取当前文件 SHA
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            st.error(f"获取 GitHub 文件失败：{r.json().get('message', '未知错误')}")
            return False
        sha = r.json()["sha"]

        # 推送更新
        payload = {
            "message": f"更新用户绑定信息 - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": csv_b64,
            "sha": sha,
        }
        r = requests.put(url, headers=headers, data=json.dumps(payload), timeout=10)
        if r.status_code in [200, 201]:
            return True
        else:
            st.error(f"GitHub 写入失败：{r.json().get('message', '未知错误')}")
            return False
    except Exception as e:
        st.error(f"GitHub 回写异常：{e}")
        return False

# ---------- 读取用户码表 ----------
@st.cache_data(show_spinner=False)
def load_user_codes():
    try:
        df = pd.read_csv("user_codes.csv", dtype=str)
        df["绑定手机号"] = df["绑定手机号"].fillna("")
        df["有效期_dt"] = pd.to_datetime(df["有效期"]).dt.date
        return df
    except Exception as e:
        st.error(f"用户码表加载失败：{e}")
        return pd.DataFrame(columns=["用户名", "使用码", "有效期", "绑定手机号", "有效期_dt"])

# 加载数据
df_codes = load_user_codes()

# 初始化会话状态
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "current_username" not in st.session_state:
    st.session_state["current_username"] = ""
if "daily_usage" not in st.session_state:
    st.session_state["daily_usage"] = 0
if "usage_date" not in st.session_state:
    st.session_state["usage_date"] = date.today()

# 每日使用次数上限
DAILY_LIMIT = 10

# 重置每日计数（跨日自动清零）
if st.session_state["usage_date"] != date.today():
    st.session_state["daily_usage"] = 0
    st.session_state["usage_date"] = date.today()

# ---------- 登录验证界面 ----------
if not st.session_state["authenticated"]:
    st.subheader("🔐 身份验证（一码一机，禁止共享）")
    user_code = st.text_input("请输入你的专属使用码", type="password")
    user_phone = st.text_input("请输入本人手机号（用于绑定激活）")
    btn_verify = st.button("提交验证并激活")

    if btn_verify:
        # 手机号格式校验
        if len(user_phone.strip()) != 11 or not user_phone.isdigit():
            st.error("请输入正确的11位手机号！")
            st.stop()

        # 查找使用码
        match_row = df_codes[df_codes["使用码"] == user_code.strip()]
        if len(match_row) == 0:
            st.error("使用码无效，请联系管理员获取～")
            st.stop()

        idx = match_row.index[0]
        bind_phone = df_codes.loc[idx, "绑定手机号"]
        expire_date = match_row.iloc[0]["有效期_dt"]
        today = datetime.today().date()

        # 1. 判断是否已被绑定
        if bind_phone != "":
            # 已绑定 → 校验手机号是否一致（允许同一用户换设备重新登录）
            if bind_phone != user_phone.strip():
                st.error("❌ 该使用码已被他人激活绑定，无法重复使用！")
                st.stop()
            # 手机号一致 → 允许登录（同一用户换设备场景）
        else:
            # 未绑定 → 判断是否过期
            if today > expire_date:
                st.error(f"使用码已过期（有效期至{expire_date}），请联系管理员续期～")
                st.stop()

            # 执行绑定，回写 GitHub
            df_codes.loc[idx, "绑定手机号"] = user_phone.strip()
            success = update_csv_on_github(df_codes)

            if success:
                # 清除缓存，确保下次加载最新数据
                st.cache_data.clear()
                st.success("✅ 绑定成功！手机号已安全保存。")
            else:
                st.warning("⚠️ 绑定已记录，但云端同步可能延迟。如遇问题请联系管理员。")

        # 登录成功
        st.session_state["authenticated"] = True
        st.session_state["current_username"] = match_row.iloc[0]["用户名"]
        st.rerun()

    st.stop()

# ---------- 验证通过后主页 ----------
st.success(f"✅ 验证通过！欢迎你，{st.session_state['current_username']}")

# 显示今日剩余次数
remaining = DAILY_LIMIT - st.session_state["daily_usage"]
if remaining <= 2:
    st.warning(f"💡 今日剩余使用次数：{remaining} 次")
else:
    st.info(f"💡 上传整面试卷或作业图片，AI老师会逐题批改订正（今日剩余 {remaining} 次）")

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

# ---------- 提示词 ----------
prompt_dict = {
    "数学": (
        "你是一位采用苏格拉底式教学法的九年级数学老师。用户会上传一整面作业或试卷的图片，里面可能包含多道题目。"
        "请按以下规则逐题处理："
        "1. 识别图片中所有题目，并用编号标记（如第1题、第2题……）。"
        "2. 对每一道题，先判断学生答案是否正确。"
        "3. 如果答案错误，请采用苏格拉底式提问法进行订正：不要直接给出正确解法，而是通过一连串引导性问题，启发学生自己发现错误所在，并一步步走向正确答案。每个问题后留出停顿，等待学生思考。讲解中必须关联课本知识点（如九年级数学的二次函数、圆、相似三角形等）。"
        "4. 最后，针对这道错题，出一道同类型、同难度的类似题供学生练习，并给出参考答案。"
        "5. 如果某道题不是数学内容（如英语），请标注"此题非数学题，跳过"。"
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

    # 检查每日使用次数
    if st.session_state["daily_usage"] >= DAILY_LIMIT:
        st.error(f"⚠️ 今日使用次数已达上限（{DAILY_LIMIT}次），请明天再来～")
        st.stop()

    # 读取并编码图片
    image_bytes = image_to_process.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    # 构建用户消息
    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
        }
    ]

    with st.spinner(f"AI {subject}老师正在逐题分析……"):
        try:
            response = client.chat.completions.create(
                model="glm-4.6v",
                messages=[
                    {"role": "system", "content": prompt_dict[subject]},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.7,
            )
            answer = response.choices[0].message.content

            # 记录使用次数
            st.session_state["daily_usage"] += 1

            st.subheader(f"📖 {subject}老师批改")
            st.write(answer)

        except Exception as e:
            st.error(f"AI 分析出错：{e}")
            st.info("请稍后重试，或联系管理员～")
