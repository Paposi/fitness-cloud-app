import datetime
import calendar
import pandas as pd
import streamlit as st
import requests

# --- CONFIG หน้าเว็บ ---
st.set_page_config(
    page_title="Fitness Admin System Pro", page_icon="🏋️‍♂️", layout="wide"
)

# 🌐 Web App URL ของคุณ
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyaDa_dEm11JTJQubu39MbV_Ix-ha1eNeyBA9vK9zjCn7OF3Nv3OSZLHyrpoNHWoe1J/exec"

# ==========================================
# ฟังก์ชันเชื่อมต่อ Google Sheet ผ่าน Web App URL
# ==========================================

# 1. ฟังก์ชันดึงข้อมูลจาก Google Sheet มาเป็น Pandas DataFrame (เปิดใช้ Cache 60 วินาที)
@st.cache_data(ttl=60)
def load_data_from_sheet(sheet_name):
    try:
        response = requests.get(WEB_APP_URL, params={"sheet_name": sheet_name})
        if response.status_code == 200:
            data = response.json()
            if len(data) > 1:
                df = pd.DataFrame(data[1:], columns=data[0])
                if "member_id" in df.columns:
                    df["member_id"] = df["member_id"].astype(int)
                if "class_id" in df.columns:
                    df["class_id"] = df["class_id"].astype(int)
                if "remaining_private" in df.columns:
                    df["remaining_private"] = df["remaining_private"].astype(int)
                if "remaining_group" in df.columns:
                    df["remaining_group"] = df["remaining_group"].astype(int)
                if "remaining_duo" in df.columns:
                    df["remaining_duo"] = df["remaining_duo"].astype(int)
                else:
                    df["remaining_duo"] = 10
                
                if "is_followed" in df.columns:
                    df["is_followed"] = df["is_followed"].astype(int)
                if "is_deleted" in df.columns:
                    df["is_deleted"] = df["is_deleted"].astype(int)
                
                if "status" not in df.columns:
                    df["status"] = "Active"
                    
                return df
            else:
                return pd.DataFrame()
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลจาก Sheet {sheet_name}: {e}")
        return pd.DataFrame()

# 2. ฟังก์ชันส่งข้อมูลการบันทึก/แก้ไข ไปที่ Apps Script หลังบ้าน
def send_action_to_script(payload):
    try:
        response = requests.post(WEB_APP_URL, json=payload)
        if response.status_code == 200 and response.json().get("status") == "success":
            return True
        return False
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Cloud: {e}")
        return False

# --- ฟังก์ชันคำนวณและดึงรายชื่อกลุ่มแจ้งเตือน ---
def get_alert_members_list(today_date):
    df_all = load_data_from_sheet("members")
    alert_data = []
    
    if not df_all.empty:
        df_active = df_all[(df_all["is_deleted"] == 0) & (df_all["status"] == "Active")]
        for _, row in df_active.iterrows():
            raw_date = str(row["expiry_date"])[:10] 
            try:
                exp_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                continue

            days_left = (exp_date - today_date).days
            p_left = int(row["remaining_private"])
            g_left = int(row["remaining_group"])
            d_left = int(row["remaining_duo"]) if "remaining_duo" in row else 0

            reason = []
            status = "ปกติ"

            if 0 <= days_left <= 7:
                reason.append(f"⏰ เวลาจะหมดในอีก {days_left} วัน")
                status = "⚠️ ควรแจ้งเตือน"
            elif days_left < 0:
                reason.append(f"🔴 หมดอายุแล้ว ({abs(days_left)} วัน)")
                status = "🚨 ขาดต่ออายุ"

            if row["package_type"] == "รายครั้ง":
                if p_left == 0 and g_left == 0 and d_left == 0:
                    reason.append("🔴 โควตาทุกคลาสหมดเกลี้ยง (0 ครั้ง)")
                    status = "🚨 ขาดต่ออายุ"
                elif (1 <= p_left <= 2) or (1 <= g_left <= 2) or (1 <= d_left <= 2):
                    reason.append(f"🎟️ สิทธิ์ใกล้หมด (เดี่ยว {p_left}, คู่ {d_left}, กลุ่ม {g_left})")
                    status = "⚠️ ควรแจ้งเตือน"

            if status != "ปกติ":
                alert_data.append({
                    "id": int(row["member_id"]),
                    "name": row["name"],
                    "phone": row["phone"],
                    "package_type": row["package_type"],
                    "p_left": f"{p_left} ครั้ง" if p_left != 99999 else "ไม่จำกัด",
                    "g_left": f"{g_left} ครั้ง" if g_left != 99999 else "ไม่จำกัด",
                    "d_left": f"{d_left} ครั้ง" if d_left != 99999 else "ไม่จำกัด",
                    "expiry_date": raw_date,
                    "status": status,
                    "reason": " และ ".join(reason),
                    "is_followed": int(row["is_followed"])
                })
    return alert_data


# --- หน้าตาโปรแกรม (UI) ---
st.title("🛡️ ระบบบริหารจัดการสตูดิโอ (Cloud Version via Google Sheet)")
st.markdown("---")

menu = [
    "👥 จัดการสมาชิก & สมัครแพ็กเกจ",
    "🏫 จัดการเพิ่มคลาสเรียน",  
    "🎟️ เช็กอินตัดสิทธิ์เข้าคลาส",
    "📅 ปฏิทินการเข้าใช้บริการ",
    "⚠️ ระบบแจ้งเตือนสมาชิกใกล้หมดอายุ",
]
choice = st.sidebar.selectbox("เมนูสำหรับ Admin", menu)
today_date = datetime.date.today()

# ==========================================
# ระบบหน้าต่างแจ้งเตือนด่วน (Pop-up Alert Dialog) เด้งเมื่อเข้าโปรแกรม
# ==========================================
@st.dialog("🚨 หน้าต่างแจ้งเตือนสมาชิกวิกฤต (เปิดแอปอัตโนมัติ)")
def show_startup_popup(alerts):
    st.write("สวัสดีครับแอดมิน! นี่คือรายชื่อสมาชิกที่ **หมดอายุ/สิทธิ์เกลี้ยง** หรือ **ใกล้หมดอายุใน 7 วัน**:")
    st.markdown("---")
    
    danger_list = [a for a in alerts if a["status"] == "🚨 ขาดต่ออายุ" and a["is_followed"] == 0]
    warning_list = [a for a in alerts if a["status"] == "⚠️ ควรแจ้งเตือน" and a["is_followed"] == 0]
    
    if danger_list:
        st.subheader("🔴 กลุ่มหมดอายุ/หมดครั้ง (ยังไม่ได้ตาม)")
        for item in danger_list:
            st.markdown(f"- **คุณ {item['name']}** ({item['phone']}) -> `{item['reason']}`")
            
    if warning_list:
        st.subheader("⚠️ กลุ่มใกล้หมดอายุภายใน 7 วัน (ยังไม่ได้ตาม)")
        for item in warning_list:
            st.markdown(f"- **คุณ {item['name']}** ({item['phone']}) -> `{item['reason']}`")
            
    if not danger_list and not warning_list:
        st.success("🟢 ยอดเยี่ยมมาก! รายชื่อที่ต้องตามของวันนี้ถูกโทรเช็กหมดเรียบร้อยแล้วครับ")
        
    st.markdown("---")
    if st.button("รับทราบและปิดหน้าต่าง", type="primary", use_container_width=True):
        st.rerun()

if "popup_shown" not in st.session_state:
    st.session_state["popup_shown"] = False

if not st.session_state["popup_shown"]:
    all_alerts = get_alert_members_list(today_date)
    active_alerts = [a for a in all_alerts if a["is_followed"] == 0]
    if active_alerts:
        st.session_state["popup_shown"] = True
        show_startup_popup(all_alerts)


# ==========================================
# 1. จัดการสมาชิก & สมัครแพ็กเกจ
# ==========================================
if choice == "👥 จัดการสมาชิก & สมัครแพ็กเกจ":
    st.header("👤 บริหารจัดการข้อมูลสมาชิกและสิทธิ์การเข้าใช้งาน")
    col1, col2 = st.columns([1, 1.8])

    with col1:
        st.subheader("➕ เพิ่มสมาชิกใหม่")
        with st.form(key="member_form", clear_on_submit=True):
            name = st.text_input("ชื่อ-นามสกุลสมาชิก *")
            phone = st.text_input("เบอร์โทรศัพท์ *")
            package_type = st.radio("ประเภทแพ็กเกจ", ["รายครั้ง", "รายปี"])

            st.markdown("**ระบุสิทธิ์คงเหลือ (หากเลือกรายครั้ง):**")
            slots_private = st.number_input("จำนวนคลาสเดี่ยว (Private)", min_value=0, max_value=100, value=10)
            slots_duo = st.number_input("จำนวนคลาสคู่ (Duo)", min_value=0, max_value=100, value=10)
            slots_group = st.number_input("จำนวนคลาสกลุ่ม (Group)", min_value=0, max_value=100, value=10)
            
            duration_days = st.number_input("อายุแพ็กเกจ (จำนวนวัน)", min_value=1, max_value=365, value=30)
            submit_member = st.form_submit_button(label="บันทึกข้อมูลสมาชิก")

        if submit_member:
            if not name.strip() or not phone.strip():
                st.error("❌ กรุณากรอกชื่อและเบอร์โทรศัพท์")
            else:
                calculated_expiry = today_date + datetime.timedelta(days=duration_days)
                actual_private = slots_private if package_type == "รายครั้ง" else 99999
                actual_duo = slots_duo if package_type == "รายครั้ง" else 99999
                actual_group = slots_group if package_type == "รายครั้ง" else 99999
                
                df_members_check = load_data_from_sheet("members")
                next_id = 1 if df_members_check.empty else int(df_members_check["member_id"].astype(int).max()) + 1

                payload = {
                    "action": "insert_member",
                    "sheet_name": "members",
                    "row_data": [next_id, name.strip(), phone.strip(), package_type, actual_private, actual_group, calculated_expiry.strftime("%Y-%m-%d"), 0, 0, today_date.strftime("%Y-%m-%d"), actual_duo, "Active"]
                }
                
                if send_action_to_script(payload):
                    st.cache_data.clear()
                    st.success(f"🎉 เพิ่มคุณ {name} สำเร็จ! หมดอายุวันที่ {calculated_expiry}")
                    st.rerun()
                else:
                    st.error("❌ ไม่สามารถเชื่อมต่อเพื่อบันทึกข้อมูลลง Google Sheet ได้")

    with col2:
        st.subheader("📋 รายชื่อสมาชิกปัจจุบัน")
        df_members = load_data_from_sheet("members")
        
        if not df_members.empty:
            df_active = df_members[df_members["is_deleted"] == 0].copy()
            if not df_active.empty:
                df_disp = df_active.rename(columns={
                    "member_id": "รหัส", "name": "ชื่อ", "phone": "เบอร์โทร", "package_type": "ประเภทแพ็กเกจ", "expiry_date": "วันหมดอายุ", "status": "สถานะ"
                })
                df_disp["วันหมดอายุ"] = df_disp["วันหมดอายุ"].apply(lambda x: str(x)[:10])
                df_disp["คลาสเดี่ยวเหลือ"] = df_disp["remaining_private"].apply(lambda x: "ไม่จำกัด" if int(x) == 99999 else f"{x} ครั้ง")
                df_disp["คลาสคู่เหลือ"] = df_disp["remaining_duo"].apply(lambda x: "ไม่จำกัด" if int(x) == 99999 else f"{x} ครั้ง")
                df_disp["คลาสกลุ่มเหลือ"] = df_disp["remaining_group"].apply(lambda x: "ไม่จำกัด" if int(x) == 99999 else f"{x} ครั้ง")
                
                def highlight_inactive(row):
                    if row["สถานะ"] == "Inactive":
                        return ["background-color: #FFFDE7"] * len(row)
                    return [""] * len(row)
                
                st.dataframe(
                    df_disp[["รหัส", "ชื่อ", "เบอร์โทร", "ประเภทแพ็กเกจ", "คลาสเดี่ยวเหลือ", "คลาสคู่เหลือ", "คลาสกลุ่มเหลือ", "วันหมดอายุ", "สถานะ"]].style.apply(highlight_inactive, axis=1), 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("ยังไม่มีข้อมูลสมาชิกในระบบ")
        else:
            st.info("ยังไม่มีข้อมูลสมาชิกในระบบ")

        st.markdown("---")
        st.subheader("⚙️ เครื่องมือปรับเปลี่ยนสิทธิ์ / สลับสถานะ Active / ต่ออายุด่วน")
        
        if not df_members.empty:
            df_active = df_members[df_members["is_deleted"] == 0]
            m_select_options = {
                f"ID {r['member_id']}: คุณ {r['name']} ({r['package_type']} | สถานะ: {r['status']})": r 
                for _, r in df_active.iterrows()
            }
            if m_select_options:
                selected_m_label = st.selectbox("เลือกสมาชิกที่ต้องการปรับปรุงสิทธิ์", list(m_select_options.keys()))
                m_data = m_select_options[selected_m_label]
                
                clean_exp_str = str(m_data["expiry_date"])[:10]
                current_exp = datetime.datetime.strptime(clean_exp_str, "%Y-%m-%d").date()
                st.markdown(f"**กำลังจัดการสิทธิ์ของ:** `คุณ {m_data['name']}` | สถานะปัจจุบัน: `{m_data['status']}`")
                
                next_status = "Inactive" if m_data["status"] == "Active" else "Active"
                btn_color = "secondary" if m_data["status"] == "Active" else "primary"
                if st.button(f"🔄 คลิกเพื่อเปลี่ยนสถานะเป็น {next_status}", type=btn_color):
                    payload = {
                        "action": "update_member_status",
                        "member_id": int(m_data["member_id"]),
                        "remaining_private": int(m_data["remaining_private"]),
                        "remaining_group": int(m_data["remaining_group"]),
                        "remaining_duo": int(m_data.get("remaining_duo", 10)),
                        "expiry_date": clean_exp_str,
                        "status": next_status,
                        "is_followed": 0
                    }
                    if send_action_to_script(payload):
                        st.cache_data.clear()
                        st.success(f"เปลี่ยนสถานะ คุณ {m_data['name']} เป็น {next_status} เรียบร้อยแล้ว!")
                        st.rerun()

                st.markdown("<br>", unsafe_allow_html=True)
                adj_col1, adj_col2, adj_col3, adj_col4 = st.columns(4)
                
                with adj_col1:
                    st.markdown("🥊 **คลาสเดี่ยว (Private)**")
                    if m_data["package_type"] == "รายปี":
                        st.caption("สิทธิ์ไม่จำกัด")
                        p_action, p_amt = "ไม่มีผล", 0
                    else:
                        st.write(f"ปัจจุบัน: `{m_data['remaining_private']} ครั้ง`")
                        p_action = st.radio("จัดการคลาสเดี่ยว", ["คงเดิม", "➕ เพิ่มสิทธิ์", "➖ ลดสิทธิ์"], key=f"p_action_{m_data['member_id']}")
                        p_amt = st.number_input("จำนวนครั้ง (เดี่ยว)", min_value=0, max_value=100, value=0, key=f"p_amt_{m_data['member_id']}")

                with adj_col2:
                    st.markdown("👥 **คลาสคู่ (Duo)**")
                    if m_data["package_type"] == "รายปี":
                        st.caption("สิทธิ์ไม่จำกัด")
                        d_action, d_amt = "ไม่มีผล", 0
                    else:
                        current_d_amt = int(m_data.get("remaining_duo", 10))
                        st.write(f"ปัจจุบัน: `{current_d_amt} ครั้ง`")
                        d_action = st.radio("จัดการคลาสคู่", ["คงเดิม", "➕ เพิ่มสิทธิ์", "➖ ลดสิทธิ์"], key=f"d_action_{m_data['member_id']}")
                        d_amt = st.number_input("จำนวนครั้ง (คู่)", min_value=0, max_value=100, value=0, key=f"d_amt_{m_data['member_id']}")

                with adj_col3:
                    st.markdown("👥 **คลาสกลุ่ม (Group)**")
                    if m_data["package_type"] == "รายปี":
                        st.caption("สิทธิ์ไม่จำกัด")
                        g_action, g_amt = "ไม่มีผล", 0
                    else:
                        st.write(f"ปัจจุบัน: `{m_data['remaining_group']} ครั้ง`")
                        g_action = st.radio("จัดการคลาสกลุ่ม", ["คงเดิม", "➕ เพิ่มสิทธิ์", "➖ ลดสิทธิ์"], key=f"g_action_{m_data['member_id']}")
                        g_amt = st.number_input("จำนวนครั้ง (กลุ่ม)", min_value=0, max_value=100, value=0, key=f"g_amt_{m_data['member_id']}")

                with adj_col4:
                    st.markdown("📅 **แก้ไขวันหมดอายุ**")
                    st.write(f"ปัจจุบัน: `{clean_exp_str}`")
                    new_expiry_date = st.date_input("เลือกวันหมดอายุใหม่", value=current_exp, key=f"exp_{m_data['member_id']}")

                if st.button("💾 บันทึกการเปลี่ยนสิทธิ์และเวลา", type="primary", use_container_width=True):
                    new_p = int(m_data["remaining_private"])
                    new_g = int(m_data["remaining_group"])
                    new_d = int(m_data.get("remaining_duo", 10))
                    
                    if p_action == "➕ เพิ่มสิทธิ์": new_p += p_amt
                    elif p_action == "➖ ลดสิทธิ์": new_p = max(0, new_p - p_amt)
                        
                    if g_action == "➕ เพิ่มสิทธิ์": new_g += g_amt
                    elif g_action == "➖ ลดสิทธิ์": new_g = max(0, new_g - g_amt)
                    
                    if d_action == "➕ เพิ่มสิทธิ์": new_d += d_amt
                    elif d_action == "➖ ลดสิทธิ์": new_d = max(0, new_d - d_amt)

                    payload = {
                        "action": "update_member_status",
                        "member_id": int(m_data["member_id"]),
                        "remaining_private": new_p,
                        "remaining_group": new_g,
                        "remaining_duo": new_d,
                        "expiry_date": new_expiry_date.strftime("%Y-%m-%d"),
                        "status": m_data["status"],
                        "is_followed": 0
                    }
                    if send_action_to_script(payload):
                        st.cache_data.clear()
                        st.success(f"🎉 อัปเดตสิทธิ์ของ คุณ {m_data['name']} เรียบร้อยแล้ว!")
                        st.rerun()
            else:
                st.info("ไม่มีรายชื่อสมาชิกให้ปรับเปลี่ยนสิทธิ์")


# ==========================================
# 2. จัดการเพิ่มคลาสเรียน
# ==========================================
elif choice == "🏫 จัดการเพิ่มคลาสเรียน":
    st.header("🏫 ระบบจัดการตารางและควบคุมคลาสเรียน")

    with st.expander("➕ คลิกเพื่อเปิดฟอร์ม เพิ่มคลาสเรียนใหม่ / ระบบ Routine", expanded=False):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            insert_mode = st.radio("รูปแบบการลงตาราง", ["เพิ่มวันเดียวแบบปกติ", "ตั้งตารางประจำ (Routine)"])
            class_name = st.text_input("ชื่อคลาสเรียน *", placeholder="เช่น Yoga Flow, Zumba, Pilates")
            instructor = st.text_input("ชื่อครูผู้สอน *", placeholder="เช่น ครูบี, ครูแอน, โค้ชเจ็ค")
            class_type = st.selectbox("ประเภทคลาส *", ["คลาสเดี่ยว (Private)", "คลาสคู่ (Duo)", "คลาสกลุ่ม (Group)"])
            chosen_color = st.color_picker("🎨 เลือกสีกล่องปฏิทินสำหรับคลาสนี้", "#E3F2FD")
        
        with col_f2:
            if insert_mode == "เพิ่มวันเดียวแบบปกติ":
                single_date = st.date_input("วันที่เปิดสอน", value=today_date)
                days_of_week = []
                routine_range = None
            else:
                days_of_week = st.multiselect(
                    "เลือกวันในสัปดาห์ที่เปิดสอน",
                    ["Monday (จันทร์)", "Tuesday (อังคาร)", "Wednesday (พุธ)", "Thursday (พฤหัส)", "Friday (ศุกร์)", "Saturday (เสาร์)", "Sunday (อาทิตย์)"]
                )
                routine_range = st.radio("ระยะเวลาในการสร้างคลาสวนลูป", ["ต่อเนื่อง 1 เดือน", "ต่อเนื่อง 3 เดือน", "ต่อเนื่อง 1 ปี"])

            if st.button("🚀 บันทึกตารางคลาสเรียน", type="primary"):
                if not class_name.strip() or not instructor.strip():
                    st.error("❌ กรุณากรอกชื่อคลาสเรียนและชื่อครูผู้สอนให้ครบถ้วน")
                elif insert_mode == "ตั้งตารางประจำ (Routine)" and not days_of_week:
                    st.error("❌ กรุณาเลือกวันในสัปดาห์อย่างน้อย 1 วัน")
                else:
                    df_classes_check = load_data_from_sheet("classes")
                    start_id = 1 if df_classes_check.empty else int(df_classes_check["class_id"].astype(int).max()) + 1
                    
                    day_mapping = {
                        "Monday (จันทร์)": 0, "Tuesday (อังคาร)": 1, "Wednesday (พุธ)": 2,
                        "Thursday (พฤหัส)": 3, "Friday (ศุกร์)": 4, "Saturday (เสาร์)": 5, "Sunday (อาทิตย์)": 6
                    }
                    
                    rows_to_send = []
                    if insert_mode == "เพิ่มวันเดียวแบบปกติ":
                        rows_to_send.append([start_id, class_name.strip(), instructor.strip(), single_date.strftime("%Y-%m-%d"), class_type, chosen_color])
                    else:
                        if routine_range == "ต่อเนื่อง 1 เดือน": end_date = today_date + datetime.timedelta(days=30)
                        elif routine_range == "ต่อเนื่อง 3 เดือน": end_date = today_date + datetime.timedelta(days=90)
                        else: end_date = today_date + datetime.timedelta(days=365)
                            
                        target_days = [day_mapping[d] for d in days_of_week]
                        current = today_date
                        c_id = start_id
                        while current <= end_date:
                            if current.weekday() in target_days:
                                rows_to_send.append([c_id, class_name.strip(), instructor.strip(), current.strftime("%Y-%m-%d"), class_type, chosen_color])
                                c_id += 1
                            current += datetime.timedelta(days=1)
                    
                    payload = {
                        "action": "insert_classes_bulk",
                        "sheet_name": "classes",
                        "rows_data": rows_to_send
                    }
                    if send_action_to_script(payload):
                        st.cache_data.clear()
                        st.success("✨ บันทึกตารางเรียนเข้าสู่ระบบ Cloud สำเร็จ!")
                        st.rerun()

    st.markdown("---")
    st.subheader("📅 หน้าจอปฏิทินภาพรวมคลาสเรียนประจำเดือน (Monthly Calendar View)")
    col_m1, col_m2 = st.columns(2)
    with col_m1: current_month = st.selectbox("เลือกเดือนที่ต้องการดูตาราง", list(calendar.month_name)[1:], index=today_date.month - 1)
    with col_m2: current_year = st.selectbox("เลือกปี (ค.ศ.)", [2026, 2027], index=0)
        
    df_classes = load_data_from_sheet("classes")
    df_attendance = load_data_from_sheet("attendance")
    
    month_num = list(calendar.month_name).index(current_month)
    start_date = datetime.date(current_year, month_num, 1)
    end_date = datetime.date(current_year, month_num, calendar.monthrange(current_year, month_num)[1])
    
    class_dict = {}
    if not df_classes.empty:
        df_classes["class_date_dt"] = pd.to_datetime(df_classes["class_date"].str[:10]).dt.date
        df_month = df_classes[(df_classes["class_date_dt"] >= start_date) & (df_classes["class_date_dt"] <= end_date)]
        
        for _, row in df_month.iterrows():
            day_int = row["class_date_dt"].day
            if day_int not in class_dict: class_dict[day_int] = []
            class_dict[day_int].append((int(row["class_id"]), row["class_name"], row["instructor"], row["class_type"], row["class_color"]))
        
    month_cal = calendar.monthcalendar(current_year, month_num)
    cols_header = st.columns(7)
    for idx, day_h in enumerate(["อาทิตย์ (Su)", "จันทร์ (Mo)", "อังคาร (Tu)", "พุธ (We)", "พฤหัส (Th)", "ศุกร์ (Fr)", "เสาร์ (Sa)"]):
        cols_header[idx].markdown(f"<div style='text-align:center; font-weight:bold; background-color:#262730; color:white; padding:5px;'>{day_h}</div>", unsafe_allow_html=True)
        
    for week in month_cal:
        cols_week = st.columns(7)
        for d_idx, day in enumerate(week):
            if day != 0:
                cols_week[d_idx].markdown(f"<div style='font-weight:bold; color:#ff4b4b;'>{day}</div>", unsafe_allow_html=True)
                if day in class_dict:
                    for c_id, c_name, inst, c_type, c_color in class_dict[day]:
                        b_count = 0 if df_attendance.empty or "class_id" not in df_attendance.columns else len(df_attendance[df_attendance["class_id"].astype(int) == c_id])
                        
                        cols_week[d_idx].markdown(
                            f"""<div style='background-color:{c_color}; border-left:4px solid #222; padding:4px; font-size:0.8rem; border-radius:4px; margin-bottom:5px;'>
                                <b style='color:#000000;'>{c_name}</b><br>
                                <span style='color:#000000; font-size:0.75rem;'>🏷️ {c_type}</span><br>
                                <span style='color:#000000;'>👤 {inst} ({b_count}คน)</span>
                            </div>""", unsafe_allow_html=True
                        )
                        if b_count == 0:
                            if cols_week[d_idx].button("🗑️ ลบ", key=f"del_m_{c_id}"):
                                payload = {"action": "delete_row_by_id", "sheet_name": "classes", "key_column": "class_id", "target_id": c_id}
                                if send_action_to_script(payload): 
                                    st.cache_data.clear()
                                    st.rerun()
                cols_week[d_idx].markdown("<div style='min-height:20px;'></div><hr style='margin:5px 0;'>", unsafe_allow_html=True)


# ==========================================
# 3. เช็กอินตัดสิทธิ์เข้าคลาส
# ==========================================
elif choice == "🎟️ เช็กอินตัดสิทธิ์เข้าคลาส":
    st.header("🎯 ระบบตัดสิทธิ์สมาชิกเข้าคลาส (Check-in)")

    df_members = load_data_from_sheet("members")
    if df_members.empty or len(df_members[(df_members["is_deleted"] == 0) & (df_members["status"] == "Active")]) == 0:
        st.warning("⚠️ จำเป็นต้องมีข้อมูลสมาชิกที่เปิดใช้งาน (Active) ในระบบก่อน")
    else:
        col1, col2 = st.columns(2)
        df_active_members = df_members[(df_members["is_deleted"] == 0) & (df_members["status"] == "Active")]

        with col1:
            st.subheader("1. เลือกสมาชิกที่จะเข้าเรียน")
            m_options = {
                f"{r['name']} (เดี่ยวคงเหลือ: {r['remaining_private'] if int(r['remaining_private']) != 99999 else 'ไม่จำกัด'}, คู่คงเหลือ: {r.get('remaining_duo', 10) if int(r.get('remaining_duo', 10)) != 99999 else 'ไม่จำกัด'}, กลุ่มคงเหลือ: {r['remaining_group'] if int(r['remaining_group']) != 99999 else 'ไม่จำกัด'} | หมดอายุ {str(r['expiry_date'])[:10]})": r
                for _, r in df_active_members.iterrows()
            }
            selected_m_label = st.selectbox("ค้นหาชื่อสมาชิก", list(m_options.keys()))
            member_data = m_options[selected_m_label]

        with col2:
            st.subheader("2. เลือกวันเรียนจากปฏิทิน 📅")
            selected_date = st.date_input("เลือกวันที่เพื่อบันทึกการเช็กอินเข้าเรียน", today_date)

            df_classes = load_data_from_sheet("classes")
            df_day_classes = pd.DataFrame()
            if not df_classes.empty:
                df_day_classes = df_classes[df_classes["class_date"].str[:10] == selected_date.strftime("%Y-%m-%d")]

            if df_day_classes.empty:
                st.error(f"❌ ไม่มีคลาสเรียนเปิดสอนในวันที่ {selected_date}")
                class_data = None
            else:
                c_options = {f"⏰ {r['class_name']} ({r['class_type']} | ผู้สอน: {r['instructor']})": r for _, r in df_day_classes.iterrows()}
                selected_c_label = st.selectbox("เลือกคลาสเรียนของวันนี้", list(c_options.keys()))
                class_data = c_options[selected_c_label]

        st.markdown("### 🔍 ผลการตรวจสอบสิทธิ์")

        if class_data is not None:
            df_attendance = load_data_from_sheet("attendance")
            
            already_checked_in = False
            if not df_attendance.empty and "member_id" in df_attendance.columns and "class_id" in df_attendance.columns:
                # 🛠️ แก็ไขบั๊กจุดนี้เรียบร้อย (ลบเครื่องหมาย = ที่เกินมาออก)
                match = df_attendance[
                    (df_attendance["member_id"].astype(int) == int(member_data["member_id"])) & 
                    (df_attendance["class_id"].astype(int) == int(class_data["class_id"])) &
                    (df_attendance["checkin_date"].str[:10] == selected_date.strftime("%Y-%m-%d"))
                ]
                if not match.empty: already_checked_in = True

            clean_exp_str = str(member_data["expiry_date"])[:10]
            exp_date = datetime.datetime.strptime(clean_exp_str, "%Y-%m-%d").date()
            is_expired = today_date > exp_date
            
            if class_data["class_type"] == "คลาสเดี่ยว (Private)":
                slots_left = int(member_data["remaining_private"])
            elif class_data["class_type"] == "คลาสคู่ (Duo)":
                slots_left = int(member_data.get("remaining_duo", 10))
            else:
                slots_left = int(member_data["remaining_group"])
                
            is_no_slots = (member_data["package_type"] == "รายครั้ง" and slots_left <= 0)

            if already_checked_in:
                st.warning(f"⚠️ สมาชิกคนนี้เคยเช็กอินเข้าคลาส '{class_data['class_name']}' ในวันนี้ไปแล้วครับ")
            elif is_expired:
                st.error(f"❌ ไม่สามารถเข้าเรียนได้: แพ็กเกจหมดอายุแล้วเมื่อ {clean_exp_str}")
            elif is_no_slots:
                st.error(f"❌ ไม่สามารถเข้าเรียนได้: โควตาของ {class_data['class_type']} หมดแล้ว (0 ครั้ง)")
            else:
                st.success(f"🟢 สมาชิกมีสิทธิ์เข้าเรียน | กำลังจะตัดโควตา: {class_data['class_type']} คลาส {class_data['class_name']}")

                if st.button("🚀 ยืนยันการเข้าคลาสและตัดสิทธิ์", type="primary"):
                    next_att_id = 1 if df_attendance.empty else int(df_attendance["attendance_id"].astype(int).max()) + 1
                    
                    new_p = int(member_data["remaining_private"])
                    new_g = int(member_data["remaining_group"])
                    new_d = int(member_data.get("remaining_duo", 10))
                    
                    if member_data["package_type"] == "รายครั้ง":
                        if class_data["class_type"] == "คลาสเดี่ยว (Private)": 
                            new_p = max(0, new_p - 1)
                        elif class_data["class_type"] == "คลาสคู่ (Duo)":
                            new_d = max(0, new_d - 1)
                        else: 
                            new_g = max(0, new_g - 1)

                    payload = {
                        "action": "checkin_member",
                        "attendance_row": [next_att_id, int(member_data["member_id"]), int(class_data["class_id"]), selected_date.strftime("%Y-%m-%d")],
                        "member_id": int(member_data["member_id"]),
                        "remaining_private": new_p,
                        "remaining_group": new_g,
                        "remaining_duo": new_d
                    }
                    if send_action_to_script(payload):
                        st.cache_data.clear()
                        st.balloons()
                        st.success(f"🎬 เช็กอินคลาสของคุณ {member_data['name']} เรียบร้อย!")
                        st.rerun()

        # ตารางปฏิทินย่อยรายบุคคล
        st.markdown("---")
        st.subheader(f"🗓️ ตารางปฏิทินการเช็กอินเข้าคลาสของ: คุณ {member_data['name']} 👤")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1: checkin_month = st.selectbox("เลือกเดือนที่ต้องการเช็กประวัติการจอง", list(calendar.month_name)[1:], index=today_date.month - 1, key="personal_cal_m")
        with col_c2: checkin_year = st.selectbox("เลือกปี (ค.ศ.)", [2026, 2027], index=0, key="personal_cal_y")
            
        month_num = list(calendar.month_name).index(checkin_month)
        start_p_date = datetime.date(checkin_year, month_num, 1)
        end_p_date = datetime.date(checkin_year, month_num, calendar.monthrange(checkin_year, month_num)[1])
        
        df_attendance = load_data_from_sheet("attendance")
        df_classes = load_data_from_sheet("classes")
        
        personal_dict = {}
        if not df_attendance.empty and not df_classes.empty:
            df_p_att = df_attendance[df_attendance["member_id"].astype(int) == int(member_data["member_id"])]
            if not df_p_att.empty:
                df_merged = df_p_att.merge(df_classes, on="class_id")
                df_merged["class_date_dt"] = pd.to_datetime(df_merged["class_date"].str[:10]).dt.date
                df_p_month = df_merged[(df_merged["class_date_dt"] >= start_p_date) & (df_merged["class_date_dt"] <= end_p_date)]
                
                for _, row in df_p_month.iterrows():
                    day_int = row["class_date_dt"].day
                    if day_int not in personal_dict: personal_dict[day_int] = []
                    personal_dict[day_int].append((int(row["attendance_id"]), row["class_name"], row["instructor"], row["class_type"], row["class_color"]))
            
        month_cal = calendar.monthcalendar(checkin_year, month_num)
        cols_header = st.columns(7)
        for idx, day_h in enumerate(["อาทิตย์ (Su)", "จันทร์ (Mo)", "อังคาร (Tu)", "พุธ (We)", "พฤหัส (Th)", "ศุกร์ (Fr)", "เสาร์ (Sa)"]):
            cols_header[idx].markdown(f"<div style='text-align:center; font-weight:bold; background-color:#ff4b4b; color:white; padding:5px;'>{day_h}</div>", unsafe_allow_html=True)
       
        for week in month_cal:
            cols_week = st.columns(7)
            for day_idx, day in enumerate(week):
                if day != 0:
                    cols_week[day_idx].markdown(f"<div style='font-weight:bold; color:#fff;'>{day}</div>", unsafe_allow_html=True)
                    if day in personal_dict:
                        for att_id, c_name, inst, c_type, c_color in personal_dict[day]:
                            cols_week[day_idx].markdown(
                                f"""<div style="background-color: {c_color}; border-left: 4px solid #111; padding: 4px 6px; border-radius: 4px; margin-bottom: 4px; font-size: 0.8rem; line-height: 1.1;">
                                    <b style="color: #000000;">📌 {c_name}</b><br>
                                    <span style="color:#000000; font-size:0.75rem;">({c_type})</span><br>
                                    <span style="color:#000000;">👤 ผู้สอน: {inst}</span>
                                </div>""", unsafe_allow_html=True
                            )
                            if cols_week[day_idx].button("🗑️ ยกเลิก", key=f"p_del_{att_id}", type="secondary"):
                                new_p = int(member_data["remaining_private"])
                                new_g = int(member_data["remaining_group"])
                                new_d = int(member_data.get("remaining_duo", 10))
                                
                                if member_data["package_type"] == "รายครั้ง":
                                    if c_type == "คลาสเดี่ยว (Private)": new_p += 1
                                    elif c_type == "คลาสคู่ (Duo)": new_d += 1
                                    else: new_g += 1
                                        
                                payload = {
                                    "action": "cancel_checkin",
                                    "attendance_id": att_id,
                                    "member_id": int(member_data["member_id"]),
                                    "remaining_private": new_p,
                                    "remaining_group": new_g,
                                    "remaining_duo": new_d
                                }
                                if send_action_to_script(payload): 
                                    st.cache_data.clear()
                                    st.rerun()
                    cols_week[day_idx].markdown("<div style='min-height:20px;'></div><hr style='margin:10px 0; border-color:#333;'>", unsafe_allow_html=True)


# ==========================================
# 4. ปฏิทินการเข้าใช้บริการ
# ==========================================
elif choice == "📅 ปฏิทินการเข้าใช้บริการ":
    st.header("📅 ตารางบันทึกการเข้าคลาสของสมาชิก")

    df_attendance = load_data_from_sheet("attendance")
    df_members = load_data_from_sheet("members")
    df_classes = load_data_from_sheet("classes")

    if df_attendance.empty or df_members.empty or df_classes.empty:
        st.info("ยังไม่มีประวัติการเช็กอินเข้าใช้บริการในระบบ")
    else:
        df_m = df_members[df_members["is_deleted"] == 0]
        df_merged = df_attendance.merge(df_m, on="member_id").merge(df_classes, on="class_id")
        df_merged = df_merged.sort_values(by="checkin_date", ascending=False)

        for _, row in df_merged.iterrows():
            att_id = int(row["attendance_id"])
            m_id = int(row["member_id"])
            p_type = row["package_type"]
            c_type = row["class_type"]
            
            clean_checkin_date = str(row['checkin_date'])[:10]
            
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.markdown(f"🔹 **วันที่:** `{clean_checkin_date}` | **คลาส:** `{row['class_name']}` (`{c_type}`) | **ชื่อสมาชิก:** `{row['name']}` ({p_type})")
            with col_btn:
                if st.button("❌ ยกเลิกและคืนสิทธิ์", key=f"cancel_{att_id}", type="secondary"):
                    new_p = int(row["remaining_private"])
                    new_g = int(row["remaining_group"])
                    new_d = int(row.get("remaining_duo", 10))
                    
                    if p_type == "รายครั้ง":
                        if c_type == "คลาสเดี่ยว (Private)": new_p += 1
                        elif c_type == "คลาสคู่ (Duo)": new_d += 1
                        else: new_g += 1

                    payload = {
                        "action": "cancel_checkin",
                        "attendance_id": att_id,
                        "member_id": m_id,
                        "remaining_private": new_p,
                        "remaining_group": new_g,
                        "remaining_duo": new_d
                    }
                    if send_action_to_script(payload):
                        st.cache_data.clear()
                        st.success(f"🔄 คืนสิทธิ์ สำเร็จ!")
                        st.rerun()
            st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)


# ==========================================
# 5. ระบบแจ้งเตือนสมาชิกใกล้หมดอายุ
# ==========================================
elif choice == "⚠️ ระบบแจ้งเตือนสมาชิกใกล้หมดอายุ":
    st.header("🚨 รายชื่อสมาชิกที่ต้องติดต่อ (ใกล้หมดอายุ/หมดครั้ง)")
    st.info("💡 คุณสามารถกดปุ่ม ✔️ เพื่อบันทึกว่า 'โทรติดตามแล้ว' หรือกด 🗑️ ลบ เพื่อซ่อนรายชื่อได้")

    alert_list = get_alert_members_list(today_date)

    if not alert_list:
        st.success("🟢 สมาชิกทุกคนในสตูดิโอมีสถานะแพ็กเกจปกติ ไม่มีรายชื่อค้างแจ้งเตือนครับ")
    else:
        st.subheader("🔴 กลุ่มที่หมดอายุ/หมดครั้งแล้ว (ต้องต่อด่วน)")
        danger_items = [x for x in alert_list if x["status"] == "🚨 ขาดต่ออายุ"]
        
        if not danger_items:
            st.success("ไม่มีสมาชิกที่ขาดต่ออายุค้างในระบบ")
        else:
            for item in danger_items:
                c_col1, c_col2, c_col3, c_col4 = st.columns([2.5, 1.5, 1, 1])
                label_prefix = "✅ *(ติดตามแล้ว)* ~" if item["is_followed"] == 1 else "📌 "
                label_suffix = "~" if item["is_followed"] == 1 else ""
                
                with c_col1:
                    st.markdown(f"{label_prefix}**คุณ {item['name']}** (📞 โทร: {item['phone']}){label_suffix}")
                    st.caption(f"เหตุผล: {item['reason']}")
                with c_col2:
                    st.markdown(f"เดี่ยวเหลือ: `{item['p_left']}` | คู่เหลือ: `{item['d_left']}` | กลุ่มเหลือ: `{item['g_left']}`")
                    st.caption(f"วันหมดอายุเดิม: {item['expiry_date']}")
                with c_col3:
                    if item["is_followed"] == 0:
                        if st.button("✔️ ตามแล้ว", key=f"follow_d_{item['id']}", use_container_width=True):
                            payload = {"action": "update_follow_status", "member_id": item['id'], "is_followed": 1}
                            if send_action_to_script(payload): 
                                st.cache_data.clear()
                                st.rerun()
                    else:
                        if st.button("🔄 รีเซ็ต", key=f"unfollow_d_{item['id']}", use_container_width=True):
                            payload = {"action": "update_follow_status", "member_id": item['id'], "is_followed": 0}
                            if send_action_to_script(payload): 
                                st.cache_data.clear()
                                st.rerun()
                with c_col4:
                    if st.button("🗑️ ลบ", key=f"hide_d_{item['id']}", type="secondary", use_container_width=True):
                        payload = {"action": "update_delete_status", "member_id": item['id'], "is_deleted": 1}
                        if send_action_to_script(payload): 
                            st.cache_data.clear()
                            st.rerun()
                st.markdown("<hr style='margin: 5px 0; opacity: 0.3;'>", unsafe_allow_html=True)

        st.write("") 
        st.subheader("⚠️ กลุ่มที่ใกล้หมด (แนะนำให้ทักท้วงชวนซื้อแพ็กเกจเพิ่ม)")
        warning_items = [x for x in alert_list if x["status"] == "⚠️ ควรแจ้งเตือน"]
        
        if not warning_items:
            st.success("สมาชิกทุกคนยังมีวันและจำนวนครั้งเหลือเฟือครับ!")
        else:
            for item in warning_items:
                w_col1, w_col2, w_col3, w_col4 = st.columns([2.5, 1.5, 1, 1])
                label_prefix = "✅ *(ติดตามแล้ว)* ~" if item["is_followed"] == 1 else "📌 "
                label_suffix = "~" if item["is_followed"] == 1 else ""
                
                with w_col1:
                    st.markdown(f"{label_prefix}**คุณ {item['name']}** (📞 โทร: {item['phone']}){label_suffix}")
                    st.caption(f"เหตุผล: {item['reason']}")
                with w_col2:
                    st.markdown(f"เดี่ยวเหลือ: `{item['p_left']}` | คู่เหลือ: `{item['d_left']}` | กลุ่มเหลือ: `{item['g_left']}`")
                    st.caption(f"จะหมดอายุ: {item['expiry_date']}")
                with w_col3:
                    if item["is_followed"] == 0:
                        if st.button("✔️ ตามแล้ว", key=f"follow_w_{item['id']}", use_container_width=True):
                            payload = {"action": "update_follow_status", "member_id": item['id'], "is_followed": 1}
                            if send_action_to_script(payload): 
                                st.cache_data.clear()
                                st.rerun()
                    else:
                        if st.button("🔄 รีเซ็ต", key=f"unfollow_w_{item['id']}", use_container_width=True):
                            payload = {"action": "update_follow_status", "member_id": item['id'], "is_followed": 0}
                            if send_action_to_script(payload): 
                                st.cache_data.clear()
                                st.rerun()
                with w_col4:
                    if st.button("🗑️ ลบ", key=f"hide_w_{item['id']}", type="secondary", use_container_width=True):
                        payload = {"action": "update_delete_status", "member_id": item['id'], "is_deleted": 1}
                        if send_action_to_script(payload): 
                            st.cache_data.clear()
                            st.rerun()
                st.markdown("<hr style='margin: 5px 0; opacity: 0.3;'>", unsafe_allow_html=True)
