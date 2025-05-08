import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from opendartreader import OpenDartReader  # 수정된 import 문

# ✅ DART API 키를 Streamlit Secrets에서 가져오기
api_key = st.secrets["DART_API_KEY"]
dart = OpenDartReader(api_key)

# ✅ Streamlit 기본 설정
st.set_page_config(page_title="재무제표 조회 앱", layout="centered")
st.title("📊 재무제표 조회 및 다운로드 앱")

st.markdown("회사명을 입력하면 최근 연도의 재무제표를 불러와 보여드릴게요.")

# ✅ 사용자 입력
company_name = st.text_input("회사명을 입력하세요 (예: 삼성전자)", "삼성전자")

# ✅ 조회 버튼
if st.button("📥 재무제표 조회 및 다운로드"):
    corp_code = dart.find_corp_code(company_name)

    if corp_code is None:
        st.error(f"❌ '{company_name}'의 고유번호를 찾을 수 없습니다.")
    else:
        year = datetime.today().year - 1
        try:
            fs = dart.finstate(corp_code, year)

            if fs is None or fs.empty:
                st.warning(f"'{company_name}'의 {year}년도 재무제표를 찾을 수 없습니다.")
            else:
                output_df = fs[['sj_nm', 'account_nm', 'thstrm_amount', 'frmtrm_amount']]
                st.success(f"✅ '{company_name}'의 {year}년 재무제표를 불러왔습니다.")
                st.dataframe(output_df)

                # ✅ 엑셀 파일 버퍼로 저장
                def to_excel(df):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='재무제표')
                    output.seek(0)  # 버퍼의 포인터를 처음으로 되돌림
                    return output.getvalue()

                excel_data = to_excel(output_df)

                st.download_button(
                    label="📂 엑셀로 다운로드",
                    data=excel_data,
                    file_name=f"{company_name}_{year}_재무제표.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")
