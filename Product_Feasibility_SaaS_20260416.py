import streamlit as st
import jwt
import time

# ========== 语言配置（与门户保持一致） ==========
if "language" not in st.session_state:
    # 优先从 URL 参数获取语言，否则默认中文
    lang_param = st.query_params.get("lang", "zh")
    st.session_state.language = lang_param if lang_param in ["zh", "en"] else "zh"

TEXTS = {
    "zh": {
        "no_token": "❌ 未检测到登录信息，请返回门户重新登录",
        "token_expired": "⏰ 登录已过期，请返回门户重新登录",
        "token_invalid": "🔐 无效的登录凭证，请返回门户重新登录",
        "welcome": "✅ 欢迎 {}，您已成功登录",
    },
    "en": {
        "no_token": "❌ No login information found. Please return to the portal and log in again.",
        "token_expired": "⏰ Login expired. Please return to the portal and log in again.",
        "token_invalid": "🔐 Invalid credentials. Please return to the portal and log in again.",
        "welcome": "✅ Welcome {}, you are now logged in.",
    }
}

def t(key):
    return TEXTS[st.session_state.language].get(key, key)

# ========== JWT 验证配置 ==========
JWT_SECRET = st.secrets.get("JWT_SECRET_KEY", "fallback-secret-key-change-me")

def verify_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload["exp"] > time.time():
            return payload["email"]
        else:
            st.error(f"Token expired at {payload['exp']}, now {time.time()}")
            return None
    except jwt.InvalidSignatureError:
        st.error("JWT signature invalid: JWT_SECRET_KEY mismatch")
        return None
    except jwt.ExpiredSignatureError:
        st.error("Token expired")
        return None
    except Exception as e:
        st.error(f"Other JWT error: {type(e).__name__} - {e}")
        return None
# ========== 执行验证 ==========
query_params = st.query_params
token = query_params.get("token", None)

if token is None:
    st.error(t("no_token"))
    st.stop()

email = verify_token(token)
if email is None:
    st.error(t("token_expired") if token else t("token_invalid"))
    st.stop()

# 验证通过，存储用户信息
st.session_state.user_email = email
st.success(t("welcome").format(email))

# ========== 然后继续你原有的工具代码 ==========
# ... 原有逻辑

import streamlit as st
import openai
import json
import os
import re
import pandas as pd
from io import BytesIO
from docx import Document
from docx.shared import Inches, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime
from openai import OpenAI

# ================== 页面配置 ==================
st.set_page_config(
    page_title="Product Feasibility Analysis System",
    page_icon="📊",
    layout="wide"
)

# ================== 管理员凭证 ==================
ADMIN_USERNAME = "Laurence_ku"
ADMIN_PASSWORD = "Ku_product$2026"

# ================== 从 secrets 读取永久 API 配置 ==================
try:
    PERSISTENT_API_KEY = st.secrets["AI_API_KEY"]
except:
    PERSISTENT_API_KEY = ""
try:
    PERSISTENT_BASE_URL = st.secrets["AI_BASE_URL"]
except:
    PERSISTENT_BASE_URL = "https://api.deepseek.com"
try:
    PERSISTENT_MODEL_NAME = st.secrets["AI_MODEL_NAME"]
except:
    PERSISTENT_MODEL_NAME = "deepseek-coder"

# ================== 初始化 session state ==================
if "lang" not in st.session_state:
    st.session_state.lang = "zh"
if "report_content_zh" not in st.session_state:
    st.session_state.report_content_zh = None
if "report_content_en" not in st.session_state:
    st.session_state.report_content_en = None
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "ai_api_key" not in st.session_state:
    st.session_state.ai_api_key = PERSISTENT_API_KEY
if "ai_base_url" not in st.session_state:
    st.session_state.ai_base_url = PERSISTENT_BASE_URL
if "ai_model_name" not in st.session_state:
    st.session_state.ai_model_name = PERSISTENT_MODEL_NAME

# ================== Word 表格生成（浅灰边框） ==================
def set_cell_border(cell, border_color=RGBColor(0xCC, 0xCC, 0xCC)):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for edge in ['top', 'left', 'bottom', 'right']:
        tag = f'w:{edge}'
        border = OxmlElement(tag)
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), f'{border_color}')
        tcPr.append(border)

def markdown_to_docx(md_text, doc, lang):
    lines = md_text.split('\n')
    i = 0
    font_name = 'Arial' if lang == 'en' else '宋体'
    while i < len(lines):
        line = lines[i]
        if line.startswith('# '):
            doc.add_heading(line[2:], level=1)
            i += 1
            continue
        if line.startswith('## '):
            doc.add_heading(line[3:], level=2)
            i += 1
            continue
        if line.startswith('### '):
            doc.add_heading(line[4:], level=3)
            i += 1
            continue
        if line.startswith('|') and i+1 < len(lines):
            table_lines = []
            while i < len(lines) and lines[i].startswith('|'):
                table_lines.append(lines[i].strip())
                i += 1
            if len(table_lines) >= 2:
                def parse_row(row):
                    cells = [cell.strip() for cell in row.split('|')]
                    if cells and cells[0] == '':
                        cells = cells[1:]
                    if cells and cells[-1] == '':
                        cells = cells[:-1]
                    return cells
                headers = parse_row(table_lines[0])
                if len(table_lines) > 1 and '---' in table_lines[1]:
                    data_lines = table_lines[2:] if len(table_lines) > 2 else []
                else:
                    data_lines = table_lines[1:]
                num_cols = len(headers)
                if num_cols > 0:
                    table = doc.add_table(rows=1+len(data_lines), cols=num_cols)
                    table.style = 'Table Grid'
                    table.autofit = True
                    table.width = Inches(6.5)
                    for row in table.rows:
                        for cell in row.cells:
                            set_cell_border(cell, RGBColor(0xCC, 0xCC, 0xCC))
                    for col_idx, cell_text in enumerate(headers):
                        cell = table.cell(0, col_idx)
                        cell.text = cell_text
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.font.bold = True
                                run.font.name = font_name
                    for row_idx, data_line in enumerate(data_lines):
                        cells = parse_row(data_line)
                        for col_idx, cell_text in enumerate(cells):
                            if col_idx < num_cols:
                                cell = table.cell(row_idx+1, col_idx)
                                cell.text = cell_text
                                for paragraph in cell.paragraphs:
                                    for run in paragraph.runs:
                                        run.font.name = font_name
                    doc.add_paragraph()
            continue
        if line.strip():
            p = doc.add_paragraph(line)
            for run in p.runs:
                run.font.name = font_name
        else:
            doc.add_paragraph()
        i += 1

# ================== 管理员对话框 ==================
@st.dialog("管理员登录")
def admin_login_dialog():
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    if st.button("登录"):
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state.admin_logged_in = True
            st.success("登录成功！")
            st.rerun()
        else:
            st.error("用户名或密码错误")

@st.dialog("管理员设置")
def admin_settings_dialog():
    st.subheader("AI API 配置（临时覆盖）")
    new_key = st.text_input("API Key", value=st.session_state.ai_api_key, type="password")
    new_url = st.text_input("Base URL", value=st.session_state.ai_base_url)
    new_model = st.text_input("模型名称", value=st.session_state.ai_model_name)
    if st.button("应用临时配置"):
        st.session_state.ai_api_key = new_key
        st.session_state.ai_base_url = new_url
        st.session_state.ai_model_name = new_model
        st.success("当前会话已使用新配置（刷新页面后恢复为永久配置）")
        st.rerun()
    st.markdown("---")
    st.subheader("永久修改 API Key")
    st.markdown("请前往 [Streamlit Cloud Secrets](https://share.streamlit.io/) 修改 `AI_API_KEY`、`AI_BASE_URL` 和 `AI_MODEL_NAME`，然后重启应用。")

# ================== 右上角按钮 ==================
col1, col2, col3, col4 = st.columns([6, 1, 2, 1])
with col2:
    if st.button("中文", key="zh_btn", type="primary"):
        st.session_state.lang = "zh"
        st.rerun()
with col3:
    if st.button("English", key="en_btn", type="primary"):
        st.session_state.lang = "en"
        st.rerun()
with col4:
    if st.button("⚙️", key="settings_btn"):
        if st.session_state.admin_logged_in:
            admin_settings_dialog()
        else:
            admin_login_dialog()

# ================== 语言文本 ==================
TEXTS = {
    "zh": {
        "title": "📊 产品可行性 - AI分析系统",
        "sidebar_title": "关于分析系统",
        "sidebar_basis": "本系统基于：",
        "basis_items": ["25+年研发管理经验", "AI大模型数据分析", "行业数据库与竞品追踪", "DFSS/六西格玛方法论"],
        "analyst_name_label": "分析人姓名",
        "analyst_name_ph": "请输入您的姓名或分析师姓名",
        "analyst_title_label": "分析人头衔（可选）",
        "analyst_title_ph": "例如：研发总监、技术顾问",
        "api_status": "AI API 状态",
        "api_configured": "✅ 已配置",
        "api_not_configured": "❌ 未配置，请联系管理员",
        "contact_info": "📞 **联系：**  \n✉️ 电邮: Techlife2027@gmail.com",
        "input_title": "📝 产品信息输入",
        "basic_info": "基本信息",
        "product_name": "产品名称",
        "product_name_ph": "例如：宠物智能饮水机",
        "product_desc": "产品简要描述",
        "product_desc_ph": "例如：一款支持APP控制、可记录饮水量的智能宠物饮水机",
        "target_markets": "目标市场",
        "market_options": ["中国大陆", "美国", "欧洲", "东南亚", "日本", "其他"],
        "target_users": "目标用户群体",
        "target_users_ph": "例如：25-40岁城市中产、养猫人群",
        "market_channel": "市场与渠道",
        "channel_status": "现有渠道情况",
        "channel_options": ["有成熟渠道", "有部分渠道", "渠道较弱", "无渠道/从零开始"],
        "channel_detail": "渠道详情",
        "channel_detail_ph": "例如：天猫旗舰店、京东自营、部分线下宠物店",
        "brand_status": "品牌认知度",
        "brand_options": ["高（知名品牌）", "中（行业内有认知）", "低（需要建立品牌）"],
        "tech_capability": "技术能力",
        "tech_experience_label": "相关技术经验（可手动输入）",
        "tech_experience_ph": "例如：智能硬件/物联网、APP开发、机械结构设计、光学设计、电子电路、供应链管理等",
        "dev_stage": "产品开发阶段",
        "stage_options": ["概念/想法", "调研中", "已立项", "开发中", "已有样机"],
        "business_goals": "商业目标",
        "estimated_budget_label": "预估研发预算（可手动输入）",
        "estimated_budget_ph": "例如：50万以下、50-100万、100-200万、200-500万、500万以上，或直接输入具体金额",
        "sales_target": "首年销售目标",
        "sales_target_ph": "例如：1000万人民币 / 200万美元",
        "other_info": "其他信息",
        "other_ph": "任何你认为重要的信息，如：已有技术储备、合作伙伴、特殊要求等",
        "submit_btn": "🚀 开始分析",
        "product_name_missing": "请填写产品名称",
        "api_key_missing": "AI API Key 未配置，请联系管理员",
        "generating": "报告生成中，大概需要3~5分钟，请稍候...",
        "error_prefix": "报告生成失败：",
        "report_title": "📄 生成的可行性分析报告",
        "download_section": "📥 下载报告",
        "download_btn": "下载 Word 文档",
        "back_btn": "← 返回重新填写",
        "footer": "© 2026 Laurence Ku | AI产品可行性分析系统 | 基于25年研发管理经验",
        "report_prompt": """
你是一位资深产品分析师和研发顾问，拥有25年消费电子及智能硬件行业经验。请根据以下产品信息，生成一份专业的《产品可行性分析报告》。

**重要要求：**
1. 报告必须严格按照以下Markdown结构输出，并且必须包含第六部分的所有三个小节：6.1、6.2、6.3。
2. 对于用户选择的每一个目标市场（例如中国大陆、美国等），都需要分别进行市场规模与趋势、用户画像、竞品分析、渠道结构的分析。**不能只笼统地写一个综合表格，而是按市场分别列出**。
3. 用户痛点分析必须基于真实场景，并**从痛点中提炼出具体的技术参数要求**（例如：从“清洗困难”提炼出“易拆洗、无死角、可洗碗机清洗”等具体设计指标）。
4. 竞品分析要针对每个目标市场列出该市场的主要竞品（至少3个），并对比功能、定价、优势劣势。
5. 技术可行性评估中的“关键技术要求”必须与前面提炼的用户痛点直接关联，明确写出对应的技术指标（如噪音≤30dB、出粮精度误差<5%、材质为食品级不锈钢等），**并且要充分利用用户提供的“相关技术经验”和“预估研发预算”来评估客户现有能力和资源匹配度**。
6. 所有表格必须包含具体数据（金额、百分比、评分等），不得留空或仅写“待补充”。

# 《产品可行性分析报告》
## {product_name}

**报告在线访问地址：https://appuct-feasibility-ktqejrpgsdbxwfjbcsorqq.streamlit.app/**

## 报告基本信息

| 项目 | 内容 |
|------|------|
| 产品名称 | {product_name} |
| 产品描述 | {product_description} |
| 目标市场 | {target_markets} |
| 目标用户 | {target_users} |
| 相关技术经验 | {tech_experience} |
| 预估研发预算 | {estimated_budget} |
| 报告日期 | {{CURRENT_DATE}} |
| 分析人 | {{ANALYST_INFO}} |

---

## 第一部分：市场需求分析

### 1.1 市场规模与趋势

**请按每个目标市场分别列出**，每个市场单独一个表格或一个子章节。表格需包含：市场规模（具体年份和金额）、年增长率、主要驱动因素、主要瓶颈。

### 1.2 用户画像

**请按每个目标市场分别描述**核心用户特征：年龄、性别、收入、宠物类型、购买动机、价格敏感度、信息获取渠道等。可用表格或分点列出。

### 1.3 用户痛点分析

**请按每个目标市场分别列出3-5个核心痛点**，用表格说明：痛点、提及频率（高/中/低）、具体描述。**并且在每个痛点后，直接提炼出对应的技术参数要求**（例如：痛点“饮水机清洗困难”→ 技术参数要求：“结构可完全拆卸、无清洁死角、支持洗碗机清洗”）。

### 1.4 关键功能需求排序

基于上述痛点，列出跨市场通用的关键功能需求，用表格给出功能、重要性评分（1-10分）、说明。

---

## 第二部分：竞品分析

### 2.1 主要竞争对手

**请按每个目标市场分别列出至少3个主要竞品**，用表格说明：品牌、产品型号/系列、优势、劣势、定价区间。

### 2.2 竞品功能对比

**请按每个目标市场分别选择5-6个关键功能进行对比**，用表格展示：功能、竞品A表现、竞品B表现、竞品C表现、市场空白机会。

### 2.3 市场空白点分析

综合所有市场，列出至少3个跨市场的空白机会，每个机会给出简要说明。

---

## 第三部分：渠道适配性分析

### 3.1 目标市场渠道结构

**请按每个目标市场分别描述**主要渠道类型、占比、特点、适合度，用表格形式。

### 3.2 客户现有渠道现状

（基于用户输入：渠道情况={channel_status}，渠道详情={channel_detail}，品牌认知度={brand_status}，进行分析，说明优势和不足）

### 3.3 渠道策略建议

按年份给出渠道拓展建议，用表格：阶段、市场、渠道策略、具体行动。

---

## 第四部分：技术可行性评估

### 4.1 关键技术要求

**必须与第一部分提炼的用户痛点直接挂钩，并充分利用用户提供的“相关技术经验”和“预估研发预算”**。用表格列出：关键技术项、对应的痛点、具体技术要求（含量化指标）、客户现有能力（基于用户输入的{tech_experience}）、风险评估（高/中/低）。同时，评估用户预算{estimated_budget}是否能支持所需研发投入，给出建议。

### 4.2 开发周期估算

用表格列出：阶段、时间、关键任务。

### 4.3 关键风险点

用表格列出：风险、可能性（高/中/低）、影响（高/中/低）、应对措施。

---

## 第五部分：销售预测

### 5.1 预测模型假设

列出定价、目标市场、市场份额等假设，用要点形式。

### 5.2 销售额预测

3年预测，用表格：年份、美国市场、中国市场、总营收、关键假设。

### 5.3 投资回报估算

用表格列出：研发投入、市场推广、首批生产成本、总启动资金、毛利率、盈亏平衡点。

---

## 第六部分：结论与建议

### 6.1 综合评估

用表格打分：市场吸引力、技术可行性、渠道匹配度、竞争格局、投资回报，各1-10分，并说明理由。

### 6.2 差异化定位建议

给出2-3个定位选项，用表格分析：定位、优势、风险。

### 6.3 最终建议

给出综合评分（例如X/10分）和“建议/不建议/积极进入”的结论，以及5点具体的下一步行动。

---

请直接输出报告内容，不要添加额外解释。对于用户未提供的信息，基于行业标准进行合理推断，并给出具体的数字。务必确保第六部分的 6.2 和 6.3 完整输出。
"""
    },
    "en": {
        "title": "📊 Product Feasibility - AI Analysis System",
        "sidebar_title": "About the System",
        "sidebar_basis": "This system is based on:",
        "basis_items": ["25+ years R&D management", "AI big data analysis", "Industry database & competitor tracking", "DFSS/Six Sigma methodology"],
        "analyst_name_label": "Analyst Name",
        "analyst_name_ph": "Enter your name or analyst name",
        "analyst_title_label": "Analyst Title (Optional)",
        "analyst_title_ph": "e.g., R&D Director, Technical Consultant",
        "api_status": "AI API Status",
        "api_configured": "✅ Configured",
        "api_not_configured": "❌ Not configured, contact admin",
        "contact_info": "📞 **Contact: Laurence**  \n✉️ Email: Techlife2027@gmail.com",
        "input_title": "📝 Product Information Input",
        "basic_info": "Basic Information",
        "product_name": "Product Name",
        "product_name_ph": "e.g., Smart Pet Water Fountain",
        "product_desc": "Brief Description",
        "product_desc_ph": "e.g., A smart pet fountain with APP control and water intake logging",
        "target_markets": "Target Markets",
        "market_options": ["Mainland China", "United States", "Europe", "Southeast Asia", "Japan", "Others"],
        "target_users": "Target User Group",
        "target_users_ph": "e.g., Urban middle-class cat owners aged 25-40",
        "market_channel": "Market & Channel",
        "channel_status": "Current Channel Status",
        "channel_options": ["Mature channels", "Partial channels", "Weak channels", "No channels / start from scratch"],
        "channel_detail": "Channel Details",
        "channel_detail_ph": "e.g., Tmall flagship store, JD self-operated, some offline pet stores",
        "brand_status": "Brand Awareness",
        "brand_options": ["High (well-known)", "Medium (recognized in industry)", "Low (need to build brand)"],
        "tech_capability": "Technical Capability",
        "tech_experience_label": "Relevant Tech Experience (free text)",
        "tech_experience_ph": "e.g., Smart Hardware/IoT, App Development, Mechanical Design, Optical Design, Electronic Circuits, Supply Chain Management",
        "dev_stage": "Development Stage",
        "stage_options": ["Idea/Concept", "Researching", "Project approved", "Developing", "Prototype ready"],
        "business_goals": "Business Goals",
        "estimated_budget_label": "Estimated R&D Budget (free text)",
        "estimated_budget_ph": "e.g., Under 500k, 500k-1M, 1M-2M, 2M-5M, Above 5M, or specific amount",
        "sales_target": "First Year Sales Target",
        "sales_target_ph": "e.g., 10M RMB / 2M USD",
        "other_info": "Other Information",
        "other_ph": "Any important info, e.g., existing tech stack, partners, special requirements",
        "submit_btn": "🚀 Start Analysis",
        "product_name_missing": "Please enter the product name",
        "api_key_missing": "AI API Key not configured, contact admin",
        "generating": "Generating report in 3~5 minutes, please wait...",
        "error_prefix": "Report generation failed: ",
        "report_title": "📄 Generated Feasibility Analysis Report",
        "download_section": "📥 Download Report",
        "download_btn": "Download Word Document",
        "back_btn": "← Back to re-enter",
        "footer": "© 2026 Laurence Ku | AI Product Feasibility System | Based on 25+ years R&D experience",
        "report_prompt": """
You are a senior product analyst and R&D consultant with 25 years of experience in consumer electronics and smart hardware. Based on the following product information, generate a professional "Product Feasibility Analysis Report".

**Important Requirements:**
1. The report must strictly follow the Markdown structure below and MUST include all three subsections of Part 6: 6.1, 6.2, and 6.3.
2. For each target market selected by the user (e.g., Mainland China, USA), you must provide separate analysis for market size & trends, user persona, competitor analysis, and channel structure. **Do not write a single combined table; break down by market**.
3. User pain points must be based on real scenarios, and **from each pain point, derive specific technical parameter requirements** (e.g., pain point "difficult to clean" → technical requirement "fully detachable structure, no dead corners, dishwasher-safe").
4. Competitor analysis must list at least 3 main competitors per target market, comparing features, pricing, strengths, and weaknesses.
5. The "Key Technical Requirements" in Part 4 must be directly linked to the pain points identified earlier, specifying quantitative metrics (e.g., noise ≤30dB, feeding accuracy error <5%, food-grade stainless steel), **and must fully utilize the user's provided "Relevant Tech Experience" and "Estimated R&D Budget" to assess the client's capability and resource fit**.
6. All tables must contain concrete data (amounts, percentages, scores, etc.) – never leave cells empty or write "to be added".

# Product Feasibility Analysis Report
## {product_name}

**Online report access: https://appuct-feasibility-ktqejrpgsdbxwfjbcsorqq.streamlit.app/**

## Report Basic Information

| Item | Content |
|------|---------|
| Product Name | {product_name} |
| Product Description | {product_description} |
| Target Markets | {target_markets} |
| Target Users | {target_users} |
| Relevant Tech Experience | {tech_experience} |
| Estimated R&D Budget | {estimated_budget} |
| Report Date | {{CURRENT_DATE}} |
| Analyst | {{ANALYST_INFO}} |

---

## Part 1: Market Demand Analysis

### 1.1 Market Size & Trends

**Provide separate analysis for each target market.** Each market should have its own table or subsection including: market size (year and amount), growth rate, key drivers, key barriers.

### 1.2 User Persona

**Describe user persona separately for each target market** – age, gender, income, pet type, purchase motivation, price sensitivity, info channels. Use tables or bullet points.

### 1.3 User Pain Points

**List 3-5 core pain points per target market** in a table: pain point, frequency (High/Medium/Low), description. **After each pain point, derive corresponding technical parameter requirements** (e.g., pain point "hard to clean" → technical requirement "fully removable parts, dishwasher-safe, no dead corners").

### 1.4 Key Feature Priority

Based on the pain points above, list cross-market key features with importance score (1-10) and explanation in a table.

---

## Part 2: Competitive Analysis

### 2.1 Main Competitors

**List at least 3 main competitors per target market** in a table: brand, product/model, strengths, weaknesses, price range.

### 2.2 Feature Comparison

**For each target market, compare 5-6 key features** in a table: feature, competitor A, competitor B, competitor C, gap opportunity.

### 2.3 Market Gap Summary

List at least 3 cross-market gap opportunities with brief explanation.

---

## Part 3: Channel Suitability Analysis

### 3.1 Target Market Channel Structure

**Describe channel types, share, characteristics, suitability separately for each target market** in a table.

### 3.2 Client's Current Channel Status

(Analyze based on user input: channel status={channel_status}, channel details={channel_detail}, brand awareness={brand_status})

### 3.3 Channel Strategy Recommendations

Provide channel expansion recommendations by year in a table: phase, market, channel strategy, specific actions.

---

## Part 4: Technical Feasibility Assessment

### 4.1 Key Technical Requirements

**Must directly map to pain points from Part 1, and fully utilize the user's "Relevant Tech Experience" and "Estimated R&D Budget".** Use a table with: technology item, corresponding pain point, specific technical requirement (quantified), client capability (based on user's {tech_experience}), risk level (High/Medium/Low). Also assess whether the {estimated_budget} is sufficient for required R&D, and provide recommendations.

### 4.2 Development Timeline Estimate

List phase, duration, key tasks in a table.

### 4.3 Key Risk Points

List risk, probability (High/Medium/Low), impact (High/Medium/Low), mitigation in a table.

---

## Part 5: Sales Forecast

### 5.1 Forecast Assumptions

List pricing, target market, share assumptions in bullet points.

### 5.2 Sales Forecast

3-year forecast in a table: year, US market, China market, total revenue, key assumptions.

### 5.3 ROI Estimate

List R&D investment, marketing, first production cost, total capital, gross margin, breakeven point in a table.

---

## Part 6: Conclusion & Recommendations

### 6.1 Comprehensive Evaluation

Score each dimension: Market Attractiveness, Technical Feasibility, Channel Fit, Competitive Landscape, ROI Potential out of 10, with explanation in a table.

### 6.2 Differentiation Positioning Recommendations

Provide 2-3 positioning options in a table: positioning, advantages, risks.

### 6.3 Final Recommendation

Provide overall score (e.g., X/10) and a conclusion like "Recommended / Highly Recommended / Not Recommended", plus 5 specific next steps.

---

Output the report directly without additional explanation. For information not provided by the user, make reasonable inferences based on industry standards and provide specific numbers. Ensure that Part 6 includes all three subsections 6.1, 6.2, and 6.3.
"""
    }
}

# ================== 获取当前语言 ==================
lang = st.session_state.lang
t = TEXTS[lang]

st.title(t["title"])

# ================== 侧边栏 ==================
with st.sidebar:
    # 关于分析系统
    st.markdown(f"## {t['sidebar_title']}")
    st.markdown(t["sidebar_basis"])
    for item in t["basis_items"]:
        st.markdown(f"- {item}")
    st.markdown("---")
    
    # 分析人姓名和头衔
    analyst_name = st.text_input(t["analyst_name_label"], placeholder=t["analyst_name_ph"])
    analyst_title = st.text_input(t["analyst_title_label"], placeholder=t["analyst_title_ph"])
    if analyst_name:
        st.markdown(f"**{t['analyst_name_label']}: {analyst_name}**")
        if analyst_title:
            st.markdown(f"_{analyst_title}_")
    else:
        st.caption(t["analyst_name_ph"])
    st.markdown("---")
    
    # API状态
    st.markdown(f"**{t['api_status']}**")
    if st.session_state.ai_api_key:
        st.success(t["api_configured"])
    else:
        st.error(t["api_not_configured"])
    st.markdown("---")
    
    # 联系信息
    st.markdown(t["contact_info"])

# ================== 主表单 ==================
st.markdown(f"### {t['input_title']}")
col1, col2 = st.columns(2)

with col1:
    st.markdown(f"#### {t['basic_info']}")
    product_name = st.text_input(t["product_name"], placeholder=t["product_name_ph"])
    product_description = st.text_area(t["product_desc"], placeholder=t["product_desc_ph"], height=100)
    
    # 目标市场多选
    st.markdown(f"**{t['target_markets']}**")
    selected_markets = st.multiselect(
        "",
        options=t["market_options"],
        default=[t["market_options"][0]],
        label_visibility="collapsed"
    )
    # 自定义市场输入
    custom_market = st.text_input(
        "其他市场（可手动输入，多个市场请用逗号分隔）" if lang=="zh" else "Other markets (comma separated)",
        placeholder="例如：东南亚, 中东" if lang=="zh" else "e.g., Southeast Asia, Middle East",
        key="custom_market_input"
    )
    
    target_users = st.text_input(t["target_users"], placeholder=t["target_users_ph"])

with col2:
    st.markdown(f"#### {t['market_channel']}")
    channel_status = st.selectbox(t["channel_status"], options=t["channel_options"])
    channel_detail = st.text_area(t["channel_detail"], placeholder=t["channel_detail_ph"], height=80)
    brand_status = st.selectbox(t["brand_status"], options=t["brand_options"])

st.markdown(f"#### {t['tech_capability']}")
col3, col4 = st.columns(2)
with col3:
    tech_experience = st.text_area(
        t["tech_experience_label"],
        placeholder=t["tech_experience_ph"],
        height=80
    )
with col4:
    dev_stage = st.selectbox(t["dev_stage"], options=t["stage_options"])

st.markdown(f"#### {t['business_goals']}")
col5, col6 = st.columns(2)
with col5:
    estimated_budget = st.text_input(
        t["estimated_budget_label"],
        placeholder=t["estimated_budget_ph"]
    )
with col6:
    sales_target = st.text_input(t["sales_target"], placeholder=t["sales_target_ph"])

st.markdown(f"#### {t['other_info']}")
additional_info = st.text_area("", placeholder=t["other_ph"], height=80)

# ================== 提交按钮 ==================
st.markdown("---")
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    submitted = st.button(t["submit_btn"], type="primary", use_container_width=True)
spinner_placeholder = st.empty()

# ================== 报告生成逻辑 ==================
if submitted:
    if not product_name:
        st.error(t["product_name_missing"])
    elif not st.session_state.ai_api_key:
        st.error(t["api_key_missing"])
    else:
        with spinner_placeholder.container():
            st.markdown(f'<div style="text-align: center; margin-top: 10px;">{t["generating"]}</div>', unsafe_allow_html=True)
            with st.spinner(""):
                try:
                    # 构建分析师信息
                    if analyst_name:
                        if analyst_title:
                            analyst_info = f"{analyst_name} ({analyst_title})"
                        else:
                            analyst_info = analyst_name
                    else:
                        analyst_info = "AI 分析师（基于行业数据库）" if lang == "zh" else "AI Analyst (based on industry database)"
                    
                    client = OpenAI(
                        api_key=st.session_state.ai_api_key,
                        base_url=st.session_state.ai_base_url,
                    )
                    prompt_template = t["report_prompt"]
                    
                    # 合并目标市场（选择 + 自定义）
                    all_markets = selected_markets.copy()
                    custom_market_val = st.session_state.get("custom_market_input", "")
                    if custom_market_val and custom_market_val.strip():
                        custom_list = [m.strip() for m in custom_market_val.split(",") if m.strip()]
                        all_markets.extend(custom_list)
                    target_markets_str = ", ".join(all_markets)
                    
                    prompt = prompt_template.format(
                        product_name=product_name,
                        product_description=product_description or "未提供",
                        target_markets=target_markets_str,
                        target_users=target_users or "未提供",
                        channel_status=channel_status,
                        channel_detail=channel_detail or "未提供",
                        brand_status=brand_status,
                        tech_experience=tech_experience if tech_experience else "未提供",
                        estimated_budget=estimated_budget if estimated_budget else "未提供"
                    )
                    response = client.chat.completions.create(
                        model=st.session_state.ai_model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=8000
                    )
                    report_content = response.choices[0].message.content
                    
                    # 替换日期和分析人信息
                    if lang == "zh":
                        current_date = datetime.now().strftime("%Y年%m月%d日")
                        report_content = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', current_date, report_content)
                        report_content = re.sub(r'\d{4}-\d{2}-\d{2}', current_date, report_content)
                    else:
                        current_date = datetime.now().strftime("%B %d, %Y")
                        report_content = re.sub(r'\d{4}-\d{2}-\d{2}', current_date, report_content)
                        report_content = re.sub(r'[A-Z][a-z]+ \d{1,2}, \d{4}', current_date, report_content)
                    report_content = report_content.replace("{{CURRENT_DATE}}", current_date)
                    report_content = report_content.replace("{{ANALYST_INFO}}", analyst_info)
                    
                    if lang == "zh":
                        report_content = re.sub(r'(\| 分析人 \|).*?(\|)', rf'\1 {analyst_info} \2', report_content, flags=re.DOTALL)
                    else:
                        report_content = re.sub(r'(\| Analyst \|).*?(\|)', rf'\1 {analyst_info} \2', report_content, flags=re.DOTALL)
                    
                    report_content = re.sub(r'\*+', '', report_content)
                    
                    if lang == "zh":
                        st.session_state.report_content_zh = report_content
                    else:
                        st.session_state.report_content_en = report_content
                    st.rerun()
                except Exception as e:
                    st.error(f"{t['error_prefix']}{e}")

# ================== 显示报告 ==================
current_report = None
if lang == "zh":
    current_report = st.session_state.report_content_zh
else:
    current_report = st.session_state.report_content_en

if current_report:
    st.markdown(f"## {t['report_title']}")
    st.markdown(current_report, unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(f"### {t['download_section']}")
    
    # 生成Word文档并下载
    doc = Document()
    markdown_to_docx(current_report, doc, lang)
    doc_bytes = BytesIO()
    doc.save(doc_bytes)
    doc_bytes.seek(0)
    st.download_button(
        label=t["download_btn"],
        data=doc_bytes,
        file_name=f"{product_name}_Feasibility_Report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    
    if st.button(t["back_btn"]):
        if lang == "zh":
            st.session_state.report_content_zh = None
        else:
            st.session_state.report_content_en = None
        st.rerun()
else:
    st.markdown("---")
    st.caption(t["footer"])
