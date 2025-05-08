import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from io import BytesIO

# ✅ DART API 키를 Streamlit Secrets에서 가져오기
try:
    api_key = st.secrets["DART_API_KEY"]
except Exception:
    st.error("DART_API_KEY를 찾을 수 없습니다. Secrets 설정을 확인하세요.")
    st.stop()

# ✅ Streamlit 기본 설정
st.set_page_config(page_title="재무제표 조회 앱", layout="centered")
st.title("📊 재무제표 조회 및 다운로드 앱")

st.markdown("회사명을 입력하면 최근 연도의 재무제표를 불러와 보여드릴게요.")

# 주요 기업 리스트 (미리 코드 정의)
major_companies = {
    "삼성전자": "00126380",
    "현대자동차": "00164742",
    "SK하이닉스": "00164779",
    "LG전자": "00356361",
    "NAVER": "00311863",
    "카카오": "00341682",
    "현대모비스": "00213051",
    "기아": "00165337",
    "포스코": "00154348",
    "삼성바이오로직스": "00347781",
    "KB금융": "00781719",
    "신한지주": "00382199",
    "LG화학": "00356361",
    "삼성SDI": "00126186",
    "한국전력": "00130783",
    "셀트리온": "00237935",
    "SK이노베이션": "00105579",
    "삼성물산": "00126186",
    "하나금융지주": "00547583",
    "SK텔레콤": "00126351"
}

# 회사 코드 조회 함수
def get_company_code(company_name):
    # 1. 주요 기업 리스트에서 먼저 확인
    if company_name in major_companies:
        return major_companies[company_name]
    
    # 2. 부분 일치하는 회사명 확인
    for name, code in major_companies.items():
        if company_name in name or name in company_name:
            return code
    
    # 3. API를 통해 회사 코드 검색
    url = "https://opendart.fss.or.kr/api/corporation.json"
    params = {
        'crtfc_key': api_key,
        'corp_name': company_name
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'status' in data and data['status'] == '000':
            if 'list' in data and len(data['list']) > 0:
                return data['list'][0]['corp_code']
    except Exception as e:
        st.warning(f"회사 코드 검색 중 오류 발생: {e}")
    
    # 4. 실패 시 기본 삼성전자 코드 반환 또는 None
    if company_name == "삼성전자" or not company_name.strip():
        return "00126380"  # 삼성전자 코드
    
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
        if 'status' in data and data['status'] != '000' and int(year) == datetime.today().year:
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

# 연도 선택 옵션
current_year = datetime.today().year
year_options = list(range(current_year, current_year-5, -1))
selected_year = st.selectbox("조회할 연도를 선택하세요", year_options)

# ✅ 사용자 입력
company_name = st.text_input("회사명을 입력하세요 (예: 삼성전자)", "삼성전자")

# ✅ 조회 버튼
if st.button("📥 재무제표 조회 및 다운로드"):
    with st.spinner("회사 정보를 검색 중입니다..."):
        corp_code = get_company_code(company_name)

    if corp_code is None:
        st.error(f"❌ '{company_name}'의 고유번호를 찾을 수 없습니다.")
    else:
        with st.spinner(f"{selected_year}년 재무제표를 불러오는 중..."):
            fs = get_financial_statement(corp_code, selected_year)

            if fs is None or fs.empty:
                st.warning(f"'{company_name}'의 {selected_year}년도 재무제표를 찾을 수 없습니다.")
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
                    
                    st.success(f"✅ '{company_name}'의 {selected_year}년 재무제표를 불러왔습니다.")
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
                        file_name=f"{company_name}_{selected_year}_재무제표.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"데이터 처리 중 오류 발생: {e}")
                    st.error(f"오류 세부정보: {str(e)}")
