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
from supabase import create_client  # 新增：导入 supabase

# ================== 页面配置 ==================
st.set_page_config(
    page_title="Product Feasibility Analysis System",
    page_icon="📊",
    layout="wide"
)

# ================== 🆕 新增：接收门户参数和计数功能 ==================
# 获取 URL 参数
query_params = st.query_params

if "user_id" in query_params:
    st.session_state.user_id = query_params["user_id"]
    st.session_state.user_email = query_params.get("email", [""])[0]
    # 设置语言
    if "lang" in query_params:
        st.session_state.lang = query_params["lang"] if query_params["lang"] in ["zh", "en"] else "zh"
    else:
        st.session_state.lang = "zh"
else:
    st.warning("请从 TechLife Suite 门户登录后访问")
    st.stop()

# 🆕 Supabase 初始化（用于计数）
@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception:
        return None

supabase = init_supabase()

# 🆕 消耗免费次数函数
def consume_trial(user_id: str, app_name: str) -> tuple:
    """
    消耗一次免费次数
    返回: (是否成功, 剩余次数, 错误信息)
    """
    if not supabase:
        return True, -1, ""  # Supabase 未配置，允许使用
    
    try:
        response = supabase.table("profiles")\
            .select("free_trials_remaining, subscription_tier")\
            .eq("id", user_id)\
            .execute()
        
        if not response.data:
            return False, 0, "用户不存在"
        
        profile = response.data[0]
        tier = profile.get("subscription_tier", "free")
        remaining = profile.get("free_trials_remaining", 30)
        
        # 专业版无限使用
        if tier == "pro":
            return True, -1, ""
        
        # 免费版检查次数
        if remaining <= 0:
            return False, 0, "免费次数已用完（共30次），请联系管理员升级"
        
        # 消耗一次
        supabase.table("profiles").update({
            "free_trials_remaining": remaining - 1
        }).eq("id", user_id).execute()
        
        # 记录使用日志
        supabase.table("usage_logs").insert({
            "user_id": user_id,
            "app_name": app_name,
            "analysis_count": 1,
            "used_at": datetime.now().isoformat()
        }).execute()
        
        return True, remaining - 1, ""
        
    except Exception as e:
        return False, 0, f"计数失败: {str(e)}"

# ================== 原有代码继续 ==================
# 管理员凭证
ADMIN_USERNAME = "Laurence_ku"
ADMIN_PASSWORD = "Ku_product$2026"

# 从 secrets 读取永久 API 配置
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

# 初始化 session state
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

# 以下原有代码保持不变（Word 表格生成、管理员对话框、语言文本等）
# ...（省略原有代码，保持原样）...

# ================== 提交按钮（🆕 修改：添加计数逻辑）==================
# 找到原代码中的提交按钮部分，添加计数逻辑
# 原代码约在第 300-320 行

if submitted:
    if not product_name:
        st.error(t["product_name_missing"])
    elif not st.session_state.ai_api_key:
        st.error(t["api_key_missing"])
    else:
        # 🆕 新增：消耗免费次数
        allowed, new_remaining, error_msg = consume_trial(st.session_state.user_id, "feasibility")
        if not allowed:
            st.error(error_msg)
        else:
            # 原有报告生成代码
            with spinner_placeholder.container():
                st.markdown(f'<div style="text-align: center; margin-top: 10px;">{t["generating"]}</div>', unsafe_allow_html=True)
                with st.spinner(""):
                    try:
                        # ... 原有的报告生成逻辑 ...
                        # （保持原有代码不变）
                    except Exception as e:
                        st.error(f"{t['error_prefix']}{e}")

# ... 其余原有代码保持不变 ...
