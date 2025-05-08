import streamlit as st
import pandas as pd
import requests
import tempfile
import zipfile
import xml.etree.ElementTree as ET
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

# 회사 고유번호 조회 함수
@st.cache_data(ttl=3600)  # 1시간 캐싱
def get_corp_codes():
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    params = {'crtfc_key': api_key}
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.zip') as temp_file:
            # API로 ZIP 파일 다운로드
            response = requests.get(url, params=params)
            if response.status_code != 200:
                st.error(f"API 오류: {response.status_code}")
                return {}
                
            temp_file.write(response.content)
            temp_file.flush()
            
            # ZIP 파일 압축 해제
            with zipfile.ZipFile(temp_file.name) as zip_ref:
                xml_data = zip_ref.read('CORPCODE.xml')
            
            # XML 파싱
            root = ET.fromstring(xml_data)
            corp_dict = {}
            for corp in root.findall('.//corp'):
                corp_name = corp.findtext('corp_name')
                corp_code = corp.findtext('corp_code')
                if corp_name and corp_code:
                    corp_dict[corp_name] = corp_code
            
            return corp_dict
    except Exception as e:
        st.error(f"회사 코드 목록 가져오기 오류: {e}")
        return {}

def find_corp_code(company_name, corp_dict):
    # 정확히 일치하는 회사 먼저 찾기
    if company_name in corp_dict:
        return corp_dict[company_name]
    
    # 유사한 회사명 찾기
    for name, code in corp_dict.items():
        if company_name in name:
            return code
    
    return None

# 재무제표 조회 함수
def get_financial_statement(corp_code, year):
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        'crtfc_key': api_key,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': '11011'  # 사업보고서
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if response.status_code != 200:
            st.error(f"재무제표 API 오류: {data.get('message')}")
            return None
        
        if 'list' not in data or not data['list']:
            return None
        
        # 데이터프레임으로 변환
        df = pd.DataFrame(data['list'])
        return df
    except Exception as e:
        st.error(f"재무제표 조회 중 오류 발생: {e}")
        return None

# ✅ 사용자 입력
company_name = st.text_input("회사명을 입력하세요 (예: 삼성전자)", "삼성전자")

# ✅ 조회 버튼
if st.button("📥 재무제표 조회 및 다운로드"):
    with st.spinner("회사 코드 목록을 가져오는 중..."):
        corp_dict = get_corp_codes()
        
    if not corp_dict:
        st.error("회사 코드 목록을 가져오지 못했습니다.")
    else:
        with st.spinner("회사 정보를 검색 중입니다..."):
            corp_code = find_corp_code(company_name, corp_dict)

        if corp_code is None:
            st.error(f"❌ '{company_name}'의 고유번호를 찾을 수 없습니다.")
        else:
            year = datetime.today().year - 1
            with st.spinner(f"{year}년 재무제표를 불러오는 중..."):
                fs = get_financial_statement(corp_code, year)

                if fs is None or fs.empty:
                    st.warning(f"'{company_name}'의 {year}년도 재무제표를 찾을 수 없습니다.")
                else:
                    try:
                        # 필요한 열 선택
                        cols_to_select = []
                        if 'sj_nm' in fs.columns:
                            cols_to_select.append('sj_nm')
                        if 'account_nm' in fs.columns:
                            cols_to_select.append('account_nm')
                        if 'thstrm_amount' in fs.columns:
                            cols_to_select.append('thstrm_amount')
                        if 'frmtrm_amount' in fs.columns:
                            cols_to_select.append('frmtrm_amount')
                        
                        if not cols_to_select:
                            st.warning("원하는 열이 데이터에 없습니다.")
                            st.write("사용 가능한 열:", fs.columns.tolist())
                            output_df = fs
                        else:
                            output_df = fs[cols_to_select]
                        
                        st.success(f"✅ '{company_name}'의 {year}년 재무제표를 불러왔습니다.")
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
                            file_name=f"{company_name}_{year}_재무제표.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"데이터 처리 중 오류 발생: {e}")
                        st.error(f"오류 세부정보: {str(e)}")
