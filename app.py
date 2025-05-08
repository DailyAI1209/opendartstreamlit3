import streamlit as st
import pandas as pd
import requests
import json
import os
import time
from datetime import datetime
from io import BytesIO

# ✅ DART API 키를 Streamlit Secrets에서 가져오기
try:
    api_key = st.secrets["DART_API_KEY"]
except Exception:
    st.error("DART_API_KEY를 찾을 수 없습니다. Secrets 설정을 확인하세요.")
    api_key = "ead29c380197353c60f0963443c43523e8f5daed"  # 코드에 직접 추가 (테스트용)

# ✅ Streamlit 기본 설정
st.set_page_config(page_title="재무제표 조회 앱", layout="centered")
st.title("📊 재무제표 조회 및 다운로드 앱")

st.markdown("회사명을 입력하면 재무제표를 불러와 보여드릴게요.")

# 주요 상장기업 딕셔너리 (미리 정의)
LISTED_COMPANIES = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "NAVER": "035420",
    "카카오": "035720",
    "현대차": "005380",
    "기아": "000270",
    "LG화학": "051910",
    "삼성바이오로직스": "207940",
    "셀트리온": "068270",
    "한국전력": "015760",
    "포스코": "005490",
    "신한지주": "055550",
    "KB금융": "105560",
    "현대모비스": "012330",
    "LG생활건강": "051900",
    "SK이노베이션": "096770",
    "LG전자": "066570",
    "SK텔레콤": "017670",
    "삼성SDI": "006400",
    "하나금융지주": "086790"
}

# 종목코드로 회사 고유번호 조회 함수
def get_corp_code_by_stock_code(stock_code):
    url = "https://opendart.fss.or.kr/api/company.json"
    params = {
        'crtfc_key': api_key,
        'stock_code': stock_code
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'status' in data and data['status'] == '000':
            return data.get('corp_code')
        else:
            st.warning(f"회사 코드 조회 실패: {data.get('message', '알 수 없는 오류')}")
            return None
    except Exception as e:
        st.error(f"회사 코드 조회 중 오류 발생: {e}")
        return None

# 회사명으로 종목코드 찾기
def find_stock_code(company_name):
    # 1. 정확한 회사명 매칭
    if company_name in LISTED_COMPANIES:
        return LISTED_COMPANIES[company_name]
    
    # 2. 부분 매칭 시도
    for name, code in LISTED_COMPANIES.items():
        if company_name in name or name in company_name:
            return code
    
    # 3. 직접 입력된 종목코드인지 확인
    if company_name.isdigit() and len(company_name) == 6:
        return company_name
    
    return None

# 회사명으로 고유번호 검색 (대체 API 사용)
def search_corp_code_by_name(company_name):
    url = "https://opendart.fss.or.kr/api/company.json"
    
    # 종목코드가 있는지 먼저 확인
    stock_code = find_stock_code(company_name)
    if stock_code:
        params = {
            'crtfc_key': api_key,
            'stock_code': stock_code
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'status' in data and data['status'] == '000':
                st.success(f"'{company_name}' 기업 정보를 찾았습니다.")
                return data.get('corp_code')
        except:
            pass  # 실패 시 다음 방법 시도

    # 이름으로 검색 - 기업개황 API
    url = "https://opendart.fss.or.kr/api/company.json"
    params = {
        'crtfc_key': api_key,
        'corp_name': company_name
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'status' in data and data['status'] == '000':
            return data.get('corp_code')
    except:
        pass  # 실패 시 다음 방법 시도
    
    # 삼성전자 고유번호 하드코딩 (마지막 수단)
    if "삼성" in company_name and "전자" in company_name:
        return "00126380"
    
    return None

# 재무제표 조회 함수
def get_financial_statement(corp_code, year):
    # 연결재무제표 요청
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        'crtfc_key': api_key,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': '11011',  # 사업보고서
        'fs_div': 'CFS'  # 연결재무제표
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        # 연결재무제표 실패시 개별재무제표 시도
        if 'status' in data and data['status'] != '000':
            st.info("연결재무제표를 찾을 수 없어 개별재무제표를 조회합니다...")
            params['fs_div'] = 'OFS'  # 개별재무제표
            response = requests.get(url, params=params)
            data = response.json()
        
        # 사업보고서 실패시 분기보고서 시도
        if 'status' in data and data['status'] != '000':
            st.info("사업보고서를 찾을 수 없어 분기보고서를 조회합니다...")
            params['reprt_code'] = '11014'  # 4분기보고서
            response = requests.get(url, params=params)
            data = response.json()
            
            # 4분기보고서도 실패시 3분기보고서 시도
            if 'status' in data and data['status'] != '000':
                params['reprt_code'] = '11013'  # 3분기보고서
                response = requests.get(url, params=params)
                data = response.json()
        
        # 올해 데이터가 없으면 작년 데이터 시도
        if 'status' in data and data['status'] != '000':
            if int(year) >= datetime.today().year - 1:
                st.info(f"{year}년 재무제표가 없어 {year-1}년 재무제표를 조회합니다...")
                params['bsns_year'] = str(year-1)
                params['reprt_code'] = '11011'  # 다시 사업보고서로 시도
                response = requests.get(url, params=params)
                data = response.json()
        
        if 'status' in data and data['status'] != '000':
            st.warning(f"API 오류: {data.get('message', '알 수 없는 오류')}")
            return None
            
        if 'list' not in data or not data['list']:
            return None
        
        # 데이터프레임으로 변환
        df = pd.DataFrame(data['list'])
        return df
    except Exception as e:
        st.error(f"재무제표 조회 중 오류 발생: {e}")
        return None

# 직접 종목코드 입력 방식 추가
method = st.radio(
    "회사 검색 방법을 선택하세요",
    ["회사명으로 검색", "종목코드로 검색"]
)

# 연도 선택 옵션
current_year = datetime.today().year
year_options = list(range(current_year-1, current_year-6, -1))
selected_year = st.selectbox("조회할 연도를 선택하세요", year_options)

# ✅ 사용자 입력
if method == "회사명으로 검색":
    input_text = st.text_input("회사명을 입력하세요 (예: 삼성전자)", "삼성전자")
    placeholder_text = "회사명"
else:
    input_text = st.text_input("종목코드를 입력하세요 (예: 005930)", "005930")
    placeholder_text = "종목코드"

# 상장회사 선택 옵션 추가
if method == "회사명으로 검색":
    st.markdown("### 주요 상장회사 바로 선택")
    cols = st.columns(4)
    company_buttons = {}
    
    for i, (company, code) in enumerate(list(LISTED_COMPANIES.items())[:20]):
        col_idx = i % 4
        with cols[col_idx]:
            company_buttons[company] = st.button(company)
    
    # 버튼 클릭 처리
    for company, clicked in company_buttons.items():
        if clicked:
            input_text = company
            st.experimental_rerun()

# ✅ 조회 버튼
if st.button(f"📥 재무제표 조회 및 다운로드"):
    if not input_text.strip():
        st.error(f"{placeholder_text}을(를) 입력해주세요.")
    else:
        with st.spinner("회사 정보를 검색 중입니다..."):
            if method == "종목코드로 검색":
                corp_code = get_corp_code_by_stock_code(input_text)
                company_name = input_text  # 종목코드를 회사명 대신 사용
            else:
                corp_code = search_corp_code_by_name(input_text)
                company_name = input_text

        if corp_code is None:
            st.error(f"❌ '{input_text}'의 고유번호를 찾을 수 없습니다.")
            
            if method == "회사명으로 검색":
                st.info("💡 팁: 정확한 회사명을 입력하거나, 종목코드로 검색해보세요. 위의 주요 상장회사 버튼을 클릭할 수도 있습니다.")
            else:
                st.info("💡 팁: 정확한 6자리 종목코드를 입력하세요. 예: 삼성전자는 '005930'입니다.")
        else:
            with st.spinner(f"{selected_year}년 재무제표를 불러오는 중..."):
                fs = get_financial_statement(corp_code, selected_year)

                if fs is None or fs.empty:
                    st.warning(f"'{input_text}'의 {selected_year}년도 재무제표를 찾을 수 없습니다.")
                    st.info("💡 팁: 다른 연도를 선택하거나, 다른 회사를 검색해보세요.")
                else:
                    try:
                        # 필요한 열 선택
                        desired_columns = ['sj_nm', 'account_nm', 'thstrm_amount', 'frmtrm_amount']
                        available_columns = [col for col in desired_columns if col in fs.columns]
                        
                        if not available_columns:
                            st.warning("원하는 열이 데이터에 없습니다.")
                            st.write("사용 가능한 열:", fs.columns.tolist())
                            output_df = fs
                        else:
                            output_df = fs[available_columns]
                        
                        st.success(f"✅ '{input_text}'의 {selected_year}년 재무제표를 불러왔습니다.")
                        st.dataframe(output_df)

                        # ✅ 엑셀 파일 버퍼로 저장
                        def to_excel(df):
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                df.to_excel(writer, index=False, sheet_name='재무제표')
                            output.seek(0)
                            return output.getvalue()

                        excel_data = to_excel(output_df)

                        st.download_button(
                            label="📂 엑셀로 다운로드",
                            data=excel_data,
                            file_name=f"{input_text}_{selected_year}_재무제표.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"데이터 처리 중 오류 발생: {e}")
                        st.error(f"오류 세부정보: {str(e)}")
