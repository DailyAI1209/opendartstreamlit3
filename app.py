import streamlit as st
import pandas as pd
import requests
import json
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

# ✅ Streamlit 기본 설정
st.set_page_config(page_title="재무제표 조회 앱", layout="centered")
st.title("📊 재무제표 조회 및 다운로드 앱")

st.markdown("회사명을 입력하면 최근 연도의 재무제표를 불러와 보여드릴게요.")

# ✅ DART API 키를 Streamlit Secrets에서 가져오기
try:
    api_key = st.secrets["DART_API_KEY"]
except Exception:
    st.error("DART_API_KEY를 찾을 수 없습니다. Secrets 설정을 확인하세요.")
    st.stop()

# 회사 고유번호 가져오기 (corpCode.xml 파일 다운로드 및 처리)
@st.cache_data(ttl=86400)  # 24시간 캐싱
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
                stock_code = corp.findtext('stock_code')
                if corp_name and corp_code:
                    corp_dict[corp_name] = {
                        'corp_code': corp_code,
                        'stock_code': stock_code
                    }
            
            return corp_dict
    except Exception as e:
        st.error(f"회사 코드 목록 가져오기 오류: {e}")
        return {}

# 회사명으로 고유번호 찾기
def find_corp_by_name(company_name, corp_dict):
    # 정확히 일치하는 회사 먼저 찾기
    if company_name in corp_dict:
        return corp_dict[company_name]['corp_code']
    
    # 부분 일치하는 회사명 찾기
    matches = []
    for name, info in corp_dict.items():
        if company_name in name:
            matches.append((name, info['corp_code']))
    
    if matches:
        if len(matches) == 1:
            return matches[0][1]
        else:
            # 여러 결과가 있으면 사용자에게 선택하게 함
            st.warning(f"'{company_name}'와(과) 유사한 회사가 여러 개 있습니다. 선택해주세요:")
            options = [name for name, _ in matches]
            selected = st.selectbox("회사 선택:", options)
            for name, code in matches:
                if name == selected:
                    return code
    
    return None

# 재무제표 조회 함수
def get_financial_statement(corp_code, year, reprt_code="11011"):
    # 연결재무제표 요청
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        'crtfc_key': api_key,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': reprt_code,  # 사업보고서
        'fs_div': 'CFS'  # 연결재무제표 (필수값)
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        # 연결재무제표 실패시 개별재무제표 시도
        if response.status_code != 200 or 'status' in data and data['status'] != '000':
            st.info("연결재무제표를 찾을 수 없어 개별재무제표를 조회합니다...")
            params['fs_div'] = 'OFS'  # 개별재무제표
            response = requests.get(url, params=params)
            data = response.json()
        
        # 사업보고서 실패시 분기보고서 시도
        if response.status_code != 200 or 'status' in data and data['status'] != '000':
            st.info("사업보고서를 찾을 수 없어 분기보고서를 조회합니다...")
            params['reprt_code'] = '11014'  # 4분기보고서
            response = requests.get(url, params=params)
            data = response.json()
            
            # 4분기보고서도 실패시 3분기보고서 시도
            if response.status_code != 200 or 'status' in data and data['status'] != '000':
                params['reprt_code'] = '11013'  # 3분기보고서
                response = requests.get(url, params=params)
                data = response.json()
        
        # 올해 데이터가 없으면 작년 데이터 시도
        if (response.status_code != 200 or 'status' in data and data['status'] != '000') and int(year) == datetime.today().year:
            st.info(f"{year}년 재무제표가 없어 {year-1}년 재무제표를 조회합니다...")
            params['bsns_year'] = str(year-1)
            params['reprt_code'] = '11011'  # 다시 사업보고서로 시도
            params['fs_div'] = 'CFS'  # 연결재무제표 다시 시도
            response = requests.get(url, params=params)
            data = response.json()
            
            # 연결재무제표 실패시 개별재무제표 시도
            if response.status_code != 200 or 'status' in data and data['status'] != '000':
                params['fs_div'] = 'OFS'  # 개별재무제표
                response = requests.get(url, params=params)
                data = response.json()
        
        if response.status_code != 200 or 'status' in data and data['status'] != '000':
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

# 실행 캐시 초기화 버튼
if st.sidebar.button("캐시 초기화"):
    st.cache_data.clear()
    st.success("캐시가 초기화되었습니다.")

# 연도 선택 옵션
current_year = datetime.today().year
year_options = list(range(current_year, current_year-5, -1))
selected_year = st.selectbox("조회할 연도를 선택하세요", year_options)

# 보고서 종류 선택
report_options = {
    "11011": "사업보고서",
    "11012": "반기보고서",
    "11013": "1분기보고서",
    "11014": "3분기보고서"
}
selected_report = st.selectbox(
    "보고서 종류를 선택하세요",
    list(report_options.keys()),
    format_func=lambda x: report_options[x]
)

# ✅ 사용자 입력
company_name = st.text_input("회사명을 입력하세요 (예: 삼성전자)", "삼성전자")

# ✅ 조회 버튼
if st.button("📥 재무제표 조회 및 다운로드"):
    with st.spinner("회사 정보를 검색 중입니다..."):
        corp_dict = get_corp_codes()
        
        if not corp_dict:
            st.error("회사 코드 목록을 가져오지 못했습니다.")
        else:
            corp_code = find_corp_by_name(company_name, corp_dict)

            if corp_code is None:
                st.error(f"❌ '{company_name}'의 고유번호를 찾을 수 없습니다.")
            else:
                with st.spinner(f"{selected_year}년 {report_options[selected_report]}를 불러오는 중..."):
                    fs = get_financial_statement(corp_code, selected_year, selected_report)

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
                                file_name=f"{company_name}_{selected_year}_{report_options[selected_report]}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        except Exception as e:
                            st.error(f"데이터 처리 중 오류 발생: {e}")
                            st.error(f"오류 세부정보: {str(e)}")
