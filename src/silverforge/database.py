"""Supabase Database Integration

Supabase를 통한 데이터 저장 및 인증
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_PATH)


def _get_env(key: str) -> Optional[str]:
    """환경변수 또는 Streamlit secrets에서 값 가져오기"""
    # 1. 환경변수 확인
    value = os.getenv(key)
    if value:
        return value

    # 2. Streamlit secrets 확인 (Streamlit Cloud 배포 시)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    return None


SUPABASE_URL = _get_env("SUPABASE_URL")
SUPABASE_KEY = _get_env("SUPABASE_KEY")

# Supabase 클라이언트 (lazy init)
_supabase_client = None


def get_supabase():
    """Supabase 클라이언트 반환"""
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return None

        from supabase import create_client

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    return _supabase_client


def is_configured() -> bool:
    """Supabase 설정 여부 확인"""
    return bool(SUPABASE_URL and SUPABASE_KEY)


# ============ Auth Functions ============

def sign_up(email: str, password: str) -> dict:
    """회원가입"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        return {"user": response.user, "session": response.session}
    except Exception as e:
        return {"error": str(e)}


def sign_in(email: str, password: str) -> dict:
    """로그인"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        return {"user": response.user, "session": response.session}
    except Exception as e:
        return {"error": str(e)}


def sign_in_with_google(redirect_url: str) -> dict:
    """Google OAuth 로그인 URL 생성"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_url,
            }
        })
        return {"url": response.url}
    except Exception as e:
        return {"error": str(e)}


def exchange_code_for_session(code: str) -> dict:
    """OAuth 콜백 코드로 세션 교환"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = supabase.auth.exchange_code_for_session({"auth_code": code})
        return {"user": response.user, "session": response.session}
    except Exception as e:
        return {"error": str(e)}


def sign_out() -> dict:
    """로그아웃"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        supabase.auth.sign_out()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def get_user(access_token: str) -> Optional[dict]:
    """현재 사용자 정보"""
    supabase = get_supabase()
    if not supabase:
        return None

    try:
        response = supabase.auth.get_user(access_token)
        return response.user
    except Exception:
        return None


# ============ Database Functions ============

def save_document(
    user_id: str,
    filename: str,
    markdown: str,
    quality_score: int,
    quality_details: dict,
) -> dict:
    """변환 문서 저장"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        data = {
            "user_id": user_id,
            "filename": filename,
            "markdown": markdown,
            "quality_score": quality_score,
            "quality_details": quality_details,
            "created_at": datetime.utcnow().isoformat(),
        }

        response = supabase.table("documents").insert(data).execute()
        return {"data": response.data}
    except Exception as e:
        return {"error": str(e)}


def get_documents(user_id: str, limit: int = 50) -> dict:
    """사용자 문서 목록 조회"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = (
            supabase.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"data": response.data}
    except Exception as e:
        return {"error": str(e)}


def get_document(doc_id: str, user_id: str) -> dict:
    """특정 문서 조회"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = (
            supabase.table("documents")
            .select("*")
            .eq("id", doc_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return {"data": response.data}
    except Exception as e:
        return {"error": str(e)}


def delete_document(doc_id: str, user_id: str) -> dict:
    """문서 삭제"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = (
            supabase.table("documents")
            .delete()
            .eq("id", doc_id)
            .eq("user_id", user_id)
            .execute()
        )
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}
