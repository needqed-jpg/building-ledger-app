import streamlit as st
import requests
import pandas as pd

# 페이지 기본 설정 (모바일 대응 반응형)
st.set_page_config(page_title="건축물대장 간편 조회", page_icon="🏢", layout="wide")

# API 키 설정 (Streamlit Secrets에서 불러오거나 직접 입력)
DATA_GO_KR_KEY = st.secrets.get("DATA_GO_KR_KEY", "0988d8e915f78b6a7fab52b3e27113fb3575e71995de9db53cb21e1d009af3ae")
JUSO_API_KEY = st.secrets.get("JUSO_API_KEY", "devU01TX0FVVEgyMDI2MDkxODE1MDYzNTEyMDQyNzI=")

# 1. 주소 변환 함수
def parse_address_to_codes(api_key: str, address: str):
    url = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
    params = {
        "confmKey": api_key,
        "currentPage": "1",
        "countPerPage": "1",
        "keyword": address,
        "resultType": "json"
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        juso_list = data.get("results", {}).get("juso", [])
        if not juso_list:
            return None, "주소를 찾을 수 없습니다."
        
        juso = juso_list[0]
        adm_cd = juso.get("admCd", "")
        lnbr_mnnm = juso.get("lnbrMnnm", "")
        lnbr_slno = juso.get("lnbrSlno", "")
        
        addr_summary = {
            "roadAddr": f"{juso.get('rnMgtSn')} {juso.get('roadAddr')}",
            "jibunAddr": juso.get('jibunAddr')
        }
        codes = {
            "sigungu_cd": adm_cd[:5],
            "bjdong_cd": adm_cd[5:],
            "bun": str(lnbr_mnnm).zfill(4),
            "ji": str(lnbr_slno).zfill(4),
            "plat_gb_cd": "0"
        }
        return codes, addr_summary
    except Exception as e:
        return None, str(e)

# 2. 표제부 API 호출
def get_building_tot_area(service_key: str, sigungu_cd: str, bjdong_cd: str, bun: str, ji: str, plat_gb_cd: str = "0"):
    url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
    params = {
        "serviceKey": service_key,
        "sigunguCd": sigungu_cd,
        "bjdongCd": bjdong_cd,
        "platGbCd": plat_gb_cd,
        "bun": bun,
        "ji": ji,
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        body = response.json().get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if not items:
            return []
        if isinstance(items, dict):
            items = [items]
            
        results = []
        for item in items:
            raw_use = str(item.get("useAprDay") or "").strip()
            use_day = f"{raw_use[:4]}-{raw_use[4:6]}-{raw_use[6:]}" if len(raw_use) == 8 else (raw_use or "-")
            results.append({
                "건물명": item.get("bldNm") or "(명칭 없음)",
                "동명칭": item.get("dongNm") or "-",
                "주용도": item.get("mainPurpsCdNm") or "-",
                "대지위치": item.get("platPlc") or "-",
                "건축면적": f"{item.get('archArea', 0)} ㎡",
                "연면적": f"{item.get('totArea', 0)} ㎡",
                "세대수": f"{item.get('hhldCnt', 0)}세대",
                "사용승인일": use_day,
                "층수": f"지상 {item.get('grndFlrCnt', 0)}층 / 지하 {item.get('ugrndFlrCnt', 0)}층"
            })
        return results
    except Exception:
        return []

# 3. 전유부 API 호출
def get_building_expos_pubuse(service_key: str, sigungu_cd: str, bjdong_cd: str, bun: str, ji: str, plat_gb_cd: str = "0"):
    url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"
    params = {
        "serviceKey": service_key,
        "sigunguCd": sigungu_cd,
        "bjdongCd": bjdong_cd,
        "platGbCd": plat_gb_cd,
        "bun": bun,
        "ji": ji,
        "numOfRows": "300",
        "pageNo": "1",
        "_type": "json"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        body = response.json().get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if not items:
            return []
        if isinstance(items, dict):
            items = [items]
            
        results = []
        for item in items:
            if str(item.get("exposPubuseGbCd") or "").strip() in ["1", "전유"]:
                results.append({
                    "동명칭": (item.get("dongNm") or "-").strip(),
                    "층수": f"{item.get('flrNo', '-')}층",
                    "호명칭": (item.get("hoNm") or "-").strip(),
                    "전유면적(㎡)": float(item.get("area") or 0),
                    "주용도": item.get("mainPurpsCdNm") or "-"
                })
        results.sort(key=lambda x: (x["동명칭"], x["층수"], x["호명칭"]))
        return results
    except Exception:
        return []

# --- UI 화면 구성 ---
st.title("🏢 건축물대장 & 전유부 간편 조회")

col1, col2 = st.columns([3, 1])
with col1:
    user_address = st.text_input("주소 입력", value="새말길 243-9", placeholder="예: 새말길 243-9 또는 신현동 523-20")
with col2:
    target_ho = st.text_input("호수 (선택)", placeholder="예: 201")

if st.button("조회하기", type="primary", use_container_width=True):
    if not user_address:
        st.warning("주소를 입력해 주세요.")
    else:
        with st.spinner("건축물대장 데이터를 불러오는 중..."):
            codes, addr_info = parse_address_to_codes(JUSO_API_KEY, user_address)
            
            if not codes:
                st.error("주소 검색 결과가 없습니다.")
            else:
                st.success(f"📍 {addr_info['roadAddr']}")
                
                # 1. 표제부
                bld_list = get_building_tot_area(DATA_GO_KR_KEY, codes["sigungu_cd"], codes["bjdong_cd"], codes["bun"], codes["ji"])
                if bld_list:
                    st.subheader("📋 건축물대장 표제부")
                    for bld in bld_list:
                        with st.expander(f"📌 {bld['건물명']} ({bld['동명칭']})", expanded=True):
                            c1, c2, c3 = st.columns(3)
                            c1.metric("연면적", bld["연면적"])
                            c2.metric("건축면적", bld["건축면적"])
                            c3.metric("세대수", bld["세대수"])
                            st.write(f"- **주용도**: {bld['주용도']} | **층수**: {bld['층수']} | **사용승인일**: {bld['사용승인일']}")
                
                # 2. 전유부
                expos_list = get_building_expos_pubuse(DATA_GO_KR_KEY, codes["sigungu_cd"], codes["bjdong_cd"], codes["bun"], codes["ji"])
                if expos_list:
                    st.subheader("🚪 전유부(호별) 현황")
                    df = pd.DataFrame(expos_list)
                    
                    if target_ho:
                        clean_ho = target_ho.replace("호", "").strip()
                        df = df[df["호명칭"].str.replace("호", "").str.contains(clean_ho)]
                        if df.empty:
                            st.info(f"'{target_ho}'호에 대한 정보가 없습니다.")
                        else:
                            st.dataframe(df, use_container_width=True)
                    else:
                        st.dataframe(df, use_container_width=True)
                else:
                    st.info("전유부 내역이 없는 일반건축물(단독주택 등)이거나 데이터가 없습니다.")