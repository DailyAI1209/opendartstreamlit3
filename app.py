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

# 자주 검색되는 기업 리스트 (참고용)
major_companies = {
    "삼성전자": "00126380",
    "현대자동차": "00164742",
    "SK하이닉스": "00164779",
    "LG전자": "00356361",
    "NAVER": "00311863",
    "카카오": "00341682"
}

# 회사 검색 함수
def search_companies(company_name):
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    params = {'crtfc_key': api_key}
    
    try:
        import tempfile
        import zipfile
        import xml.etree.ElementTree as ET
        
        with tempfile.NamedTemporaryFile(suffix='.zip') as temp_file:
            # API로 ZIP 파일 다운로드
            response = requests.get(url, params=params)
            if response.status_code != 200:
                st.error(f"회사 목록 다운로드 오류: {response.status_code}")
                return []
                
            temp_file.write(response.content)
            temp_file.flush()
            
            # ZIP 파일 압축 해제
            try:
                with zipfile.ZipFile(temp_file.name) as zip_ref:
                    xml_data = zip_ref.read('CORPCODE.xml')
            except Exception as e:
                st.error(f"ZIP 파일 압축 해제 오류: {e}")
                return []
            
            # XML 파싱
            try:
                root = ET.fromstring(xml_data)
                results = []
                
                # 검색어와 일치하는 회사 찾기
                for corp in root.findall('.//corp'):
                    corp_name = corp.findtext('corp_name', '')
                    corp_code = corp.findtext('corp_code', '')
                    stock_code = corp.findtext('stock_code', '')
                    
                    # 검색 조건: 회사명에 검색어가 포함되어 있고, 상장회사인 경우 우선
                    if company_name.lower() in corp_name.lower():
                        is_listed = stock_code and stock_code.strip() != ''
                        results.append({
                            'corp_name': corp_name,
                            'corp_code': corp_code,
                            'stock_code': stock_code,
                            'is_listed': is_listed
                        })
                
                # 상장회사 우선, 그 다음 이름 유사도 순으로 정렬
                results.sort(key=lambda x: (not x['is_listed'], abs(len(x['corp_name']) - len(company_name))))
                
                return results[:10]  # 최대 10개 결과 반환
            except Exception as e:
                st.error(f"XML 파싱 오류: {e}")
                return []
                
    except Exception as e:
        st.error(f"회사 검색 중 오류 발생: {e}")
        return []

# 회사 코드 조회 함수
def get_company_code(company_name):
    # 1. 주요 기업 리스트에서 먼저 확인 (빠른 검색)
    if company_name in major_companies:
        return major_companies[company_name]
    
    # 2. 부분 일치하는 회사명 확인 (빠른 검색)
    for name, code in major_companies.items():
        if company_name in name or name in company_name:
            return code
    
    # 3. API를 통해 회사 검색 (정확한 검색)
    st.info("회사를 API를 통해 검색 중입니다. 잠시만 기다려주세요...")
    
    # 3-1. 먼저 corporation.json API로 시도 (빠르지만 정확도 낮음)
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
    except Exception:
        pass  # 실패해도 다음 방법 시도
    
    # 3-2. 전체 회사 목록에서 검색 (느리지만 정확도 높음)
    search_results = search_companies(company_name)
    
    if search_results:
        if len(search_results) == 1:
            # 결과가 하나면 바로 반환
            return search_results[0]['corp_code']
        else:
            # 여러 결과가 있으면 사용자에게 선택하게 함
            st.warning(f"'{company_name}'와(과) 유사한 회사가 여러 개 있습니다. 선택해주세요:")
            
            # 라디오 버튼으로 회사 선택 UI 생성
            company_options = [f"{r['corp_name']} ({'상장' if r['is_listed'] else '비상장'})" for r in search_results]
            selected_index = st.radio("회사 선택:", company_options)
            
            # 선택한 회사의 코드 반환
            selected_index = company_options.index(selected_index)
            return search_results[selected_index]['corp_code']
    
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
    if not company_name.strip():
        st.error("회사명을 입력해주세요.")
    else:
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
