import datetime
import calendar
import re
import pandas as pd
import streamlit as st
import requests
from dateutil.relativedelta import relativedelta

# --- CONFIG หน้าเว็บ ---
st.set_page_config(
    page_title="Fitness Admin System Ultra Pro", page_icon="🏋️‍♂️", layout="wide"
)

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyaDa_dEm11JTJQubu39MbV_Ix-ha1eNeyBA9vK9zjCn7OF3Nv3OSZLHyrpoNHWoe1J/exec"

def clean_date_string(raw_val):
    if pd.isna(raw_val) or not raw_val:
        return ""
    val_str = str(raw_val).strip()
    match = re.match(r'^(\d{4}-\d{2}-\d{2})', val_str)
    if match:
        return match.group(1)
    return val_str

@st.cache_data(ttl=10)
def load_data_from_sheet(sheet_name):
    try:
        response = requests.get(WEB_APP_URL, params={"sheet_name": sheet_name})
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 1:
                return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลชีต {sheet_name}: {e}")
        return pd.DataFrame()

def send_action_to_script(payload):
    try:
        response = requests.post(WEB_APP_URL, json=payload)
        if response.status_code == 200 and response.json().get("status") == "success":
            return True
        return False
    except Exception as e:
        st.error(f"การเชื่อมต่อ Cloud ขัดข้อง: {e}")
        return False

# ตรรกะระบบแจ้งเตือนผลรวมและเวลาหมดอายุ (ปรับให้คำนวณจากทุกสิทธิ์รวมกัน)
def get_advanced_alert_list(df_m, df_c, today):
    if not isinstance(df_m, pd.DataFrame) or df_m.empty: return []
    if not isinstance(df_c, pd.DataFrame) or df_c.empty: return []
        
    alert_data = []
    if "is_deleted" not in df_m.columns: return []
        
    active_m = df_m[df_m["is_deleted"].astype(str).str.strip() == "0"]
    
    for _, m_row in active_m.iterrows():
        try:
            m_id = int(float(str(m_row["member_id"]).strip()))
        except: continue
        
        if "member_id" not in df_c.columns or "is_deleted" not in df_c.columns: continue
            
        m_courses = df_c[(df_c["member_id"].astype(str).str.strip() == str(m_id)) & (df_c["is_deleted"].astype(str).str.strip() == "0")]
        
        total_remaining = 0
        has_expired_but_has_slots = False
        expired_reasons = []
        
        for _, c_row in m_courses.iterrows():
            c_status = str(c_row.get("status", "Inactive")).strip()
            
            try: rem_p = int(float(str(c_row.get("rem_private", 0)).strip()))
            except: rem_p = 0
            try: rem_d = int(float(str(c_row.get("rem_duo", 0)).strip()))
            except: rem_d = 0
            try: rem_g = int(float(str(c_row.get("rem_group", 0)).strip()))
            except: rem_g = 0
            
            slots = rem_p + rem_d + rem_g
            total_remaining += slots
            
            exp_str = clean_date_string(c_row.get("expiry_date", ""))
            if exp_str:
                try:
                    exp_date = datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
                    if today > exp_date and slots > 0:
                        has_expired_but_has_slots = True
                        if c_status == "Inactive":
                            expired_reasons.append(f"คอร์ส {c_row.get('course_name','')} หมดเวลาดองสิทธิ์ แต่เหลือรวม {slots} ครั้ง")
                        else:
                            expired_reasons.append(f"คอร์ส {c_row.get('course_name','')} หมดอายุใช้งาน แต่เหลือรวม {slots} ครั้ง")
                except ValueError: continue

        reason = []
        status = "ปกติ"
        
        if total_remaining < 2 and len(m_courses) > 0:
            status = "🚨 สิทธิ์หมด/วิกฤต"
            reason.append(f"🎟️ ยอดรวมทุกสิทธิ์ในทุกคอร์สเหลือ {total_remaining} ครั้ง")
            
        if has_expired_but_has_slots:
            status = "⚠️ คอร์สหมดอายุแต่สิทธิ์เหลือ"
            reason.extend(expired_reasons)

        if status != "ปกติ":
            try: is_f = int(float(str(m_row.get("is_followed", 0)).strip()))
            except: is_f = 0
            alert_data.append({
                "id": m_id, "name": m_row["name"], "phone": m_row["phone"],
                "total_slots": f"{total_remaining} ครั้ง", "status": status,
                "reason": " | ".join(reason), "is_followed": is_f
            })
    return alert_data


# --- เริ่มต้นหน้าหลักแอดมิน ---
st.title("🛡️ Fitness Admin System Pro (Hybrid Support)")
st.markdown("---")

menu = [
    "👥 สมัครสมาชิก & เพิ่มคอร์สใหม่",
    "🛠️ การจัดการคลาส",
    "🏫 จัดการตารางคลาสเรียน",  
    "🎟️ เช็กอินเข้าเรียน (Auto FIFO)",
    "📅 ปฏิทินและประวัติการเข้าคลาส",
    "⚠️ ระบบแจ้งเตือนเงื่อนไขพิเศษ",
    "🧹 ล้างคอร์สที่ไม่ได้ใช้งานเกิน 4 เดือน"
]
choice = st.sidebar.selectbox("เมนูจัดการสตูดิโอ", menu)
today_date = datetime.date.today()

if "cal_shift_manage" not in st.session_state:
    st.session_state["cal_shift_manage"] = 0  
if "cal_shift_checkin" not in st.session_state:
    st.session_state["cal_shift_checkin"] = 0

df_members = load_data_from_sheet("members")
df_courses = load_data_from_sheet("courses")

# POP-UP ตรวจจับสิทธิ์รวมวิกฤต
if "popup_shown" not in st.session_state:
    st.session_state["popup_shown"] = False

if isinstance(df_members, pd.DataFrame) and not df_members.empty and not st.session_state["popup_shown"]:
    all_alerts = get_advanced_alert_list(df_members, df_courses, today_date)
    unfollowed_alerts = [a for a in all_alerts if a["is_followed"] == 0]
    if unfollowed_alerts:
        @st.dialog("🚨 แจ้งเตือนยอดสิทธิ์วิกฤต (< 2 ครั้ง)")
        def show_alert_popup(alerts):
            st.write("พบรายชื่อสมาชิกตรงเงื่อนไขสิทธิ์หมด/วิกฤต:")
            for item in alerts:
                st.markdown(f"- **คุณ {item['name']}** ({item['phone']}) ⮞ `{item['status']}` : {item['reason']}")
            if st.button("รับทราบและปิดหน้าต่าง", type="primary", use_container_width=True):
                st.session_state["popup_shown"] = True ; st.rerun()
        show_alert_popup(unfollowed_alerts)

# ==========================================
# 1. หน้าจัดการและเปิดคอร์สใหม่
# ==========================================
if choice == "👥 สมัครสมาชิก & เพิ่มคอร์สใหม่":
    st.header("👤 ระบบการจัดการ MemberID และ เปิดคอร์สเรียนผสม")
    tab1, tab2 = st.tabs(["➕ สมัคร Member ID ใหม่", "🎟️ ซื้อคอร์สผสม Hybrid ใหม่ให้ ID เดิม"])
    
    with tab1:
        st.subheader("สร้างประวัติสมาชิกใหม่")
        with st.form(key="new_member_form", clear_on_submit=True):
            m_name = st.text_input("ชื่อ-นามสกุลลูกค้า *")
            m_phone = st.text_input("เบอร์โทรศัพท์ *")
            submit_m = st.form_submit_button("บันทึกข้อมูลสมาชิก")
        if submit_m:
            if not m_name.strip() or not m_phone.strip():
                st.error("❌ กรุณากรอกชื่อและเบอร์โทรศัพท์ให้ครบถ้วน")
            else:
                next_m_id = 1 if df_members.empty else int(float(str(df_members["member_id"].max()))) + 1
                payload = {
                    "action": "insert_member", "sheet_name": "members",
                    "row_data": [next_m_id, m_name.strip(), m_phone.strip(), f"'{today_date.strftime('%Y-%m-%d')}'", 0, 0]
                }
                if send_action_to_script(payload):
                    st.cache_data.clear(); st.success(f"🎉 ออกรหัสสำเร็จ! Member ID: {next_m_id}"); st.rerun()

    with tab2:
        st.subheader("เปิดคอร์สผสม (กำหนดจำนวนครั้งแยกประเภทคลาสได้ในคอร์สเดียว)")
        if df_members.empty:
            st.info("ยังไม่มีข้อมูลสมาชิกในระบบ")
        else:
            active_m = df_members[df_members["is_deleted"].astype(str).str.strip() == "0"]
            m_options = {f"ID {r['member_id']}: คุณ {r['name']}": r for _, r in active_m.iterrows()}
            selected_m_label = st.selectbox("เลือกสมาชิกที่ต้องการเพิ่มคอร์ส", list(m_options.keys()))
            m_selected = m_options[selected_m_label]
            
            with st.form(key="new_course_form", clear_on_submit=True):
                c_name = st.text_input("ชื่อคอร์สผสม *", placeholder="เช่น คอร์สเหมาใจสปอร์ต มกราคม")
                
                st.markdown("🎯 **ระบุจำนวนครั้งแยกตามรูปแบบคลาส (หากไม่มีให้กรอก 0)**")
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    slots_private = st.number_input("จำนวนครั้งคลาสเดี่ยว (Private)", min_value=0, value=0)
                with col_s2:
                    slots_duo = st.number_input("จำนวนครั้งคลาสคู่ (Duo)", min_value=0, value=0)
                with col_s3:
                    slots_group = st.number_input("จำนวนครั้งคลาสกลุ่ม (Group)", min_value=0, value=0)
                
                col_dur1, col_dur2 = st.columns(2)
                with col_dur1:
                    inactive_days = st.number_input("⏳ ระยะเวลาดองคอร์ส Inactive Duration (วัน) *", min_value=1, value=90)
                with col_dur2:
                    active_days = st.number_input("🔥 ระยะเวลาใช้งานหลังเปิดคอร์ส Active Duration (วัน) *", min_value=1, value=30)
                
                submit_c = st.form_submit_button("💳 ยืนยันการออกคอร์สผสม")
                
            if submit_c:
                if not c_name.strip():
                    st.error("❌ กรุณาระบุชื่อคอร์ส")
                elif slots_private + slots_duo + slots_group <= 0:
                    st.error("❌ คอร์สต้องมีจำนวนสิทธิ์เรียนอย่างน้อยหนึ่งประเภทคลาส (มากกว่า 0 ครั้ง)")
                else:
                    if df_courses.empty:
                        next_c_id = 1
                    else:
                        valid_ids = pd.to_numeric(df_courses["course_id"], errors='coerce').fillna(0)
                        next_c_id = int(valid_ids.max()) + 1
                    
                    inactive_expiry = today_date + datetime.timedelta(days=int(inactive_days))
                    
                    course_payload = {
                        "action": "insert_course", 
                        "sheet_name": "courses",
                        "row_data": [
                            next_c_id, int(m_selected["member_id"]), c_name.strip(), 
                            slots_private, slots_private,  
                            slots_duo, slots_duo,          
                            slots_group, slots_group,      
                            f"'{today_date.strftime('%Y-%m-%d')}'", 
                            int(inactive_days), int(active_days), f"'{inactive_expiry.strftime('%Y-%m-%d')}'", 
                            "Inactive", 0
                        ]
                    }
                    if send_action_to_script(course_payload):
                        st.cache_data.clear(); st.success(f"🎉 บันทึกคอร์สผสมสำเร็จ! สถานะ: Inactive (หมดระยะดอง: {inactive_expiry.strftime('%Y-%m-%d')})"); st.rerun()

    st.markdown("---")
    st.subheader("📋 รายการคอร์สทั้งหมดในระบบ (สิทธิ์คงเหลือแยกประเภทคลาส)")
    
    if isinstance(df_courses, pd.DataFrame) and not df_courses.empty:
        df_courses.columns = [c.strip() for c in df_courses.columns]
        
        if "is_deleted" in df_courses.columns:
            df_disp_courses = df_courses[df_courses["is_deleted"].astype(str).str.strip() == "0"].copy()
            
            if not df_disp_courses.empty and not df_members.empty:
                df_members_clean = df_members[["member_id", "name", "phone"]].copy()
                df_members_clean["member_id"] = df_members_clean["member_id"].astype(str).str.strip()
                df_disp_courses["member_id"] = df_disp_courses["member_id"].astype(str).str.strip()
                
                df_merged = df_disp_courses.merge(df_members_clean, on="member_id", how="left")
                df_merged["member_id_int"] = df_merged["member_id"].astype(int)
                df_merged = df_merged.sort_values(by="member_id_int")

                table_data = []
                for _, r in df_merged.iterrows():
                    c_status = str(r.get("status", "Inactive")).strip()
                    c_id = int(float(str(r["course_id"])))
                    
                    exp_str = clean_date_string(r.get("expiry_date", ""))
                    is_expired = False
                    if exp_str:
                        try: is_expired = today_date > datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
                        except: pass
                    
                    if c_status == "Inactive":
                        status_label = "🟡 Inactive" if not is_expired else "❌ หมดเวลาดอง"
                    else:
                        status_label = "🟢 Active" if not is_expired else "❌ หมดอายุใช้งาน"

                    p_txt = f"P: {r.get('rem_private','0')}/{r.get('total_private','0')}"
                    d_txt = f"D: {r.get('rem_duo','0')}/{r.get('total_duo','0')}"
                    g_txt = f"G: {r.get('rem_group','0')}/{r.get('total_group','0')}"

                    table_data.append({
                        "Member": f"คุณ {r.get('name', '')} (ID: {r.get('member_id', '')})",
                        "Course Info": f"รหัส: {c_id} | {r.get('course_name', '')}",
                        "สิทธิ์คงเหลือ Private": p_txt,
                        "สิทธิ์คงเหลือ Duo": d_txt,
                        "สิทธิ์คงเหลือ Group": g_txt,
                        "วันหมดอายุ": clean_date_string(r.get('expiry_date', '')),
                        "สถานะ": status_label
                    })

                st.table(pd.DataFrame(table_data))

# ==========================================
# 2. หน้าจัดการคลาสและแก้ไขข้อมูลคอร์ส
# ==========================================
elif choice == "🛠️ การจัดการคลาส":
    st.header("🛠️ การจัดการคลาสและแก้ไขข้อมูลคอร์สผสม")
    df_courses = load_data_from_sheet("courses")
    
    if not df_courses.empty:
        df_courses.columns = [c.strip() for c in df_courses.columns]
        df_members_clean = df_members[["member_id", "name", "phone"]].copy()
        df_members_clean["member_id"] = df_members_clean["member_id"].astype(str).str.strip()
        df_courses["member_id"] = df_courses["member_id"].astype(str).str.strip()
        
        df_merged = df_courses.merge(df_members_clean, on="member_id", how="left")
        df_merged["member_id_int"] = df_merged["member_id"].astype(int)
        df_merged = df_merged.sort_values(by="member_id_int")
        
        table_data = []
        for _, r in df_merged.iterrows():
            table_data.append({
                "Member": f"คุณ {r.get('name', '')} (ID: {r.get('member_id', '')})",
                "Course Info": f"รหัส: {int(float(r['course_id']))} | {r.get('course_name', '')}",
                "Private": f"{r.get('rem_private','0')} / {r.get('total_private','0')}",
                "Duo": f"{r.get('rem_duo','0')} / {r.get('total_duo','0')}",
                "Group": f"{r.get('rem_group','0')} / {r.get('total_group','0')}",
                "หมดอายุ": clean_date_string(r.get('expiry_date', '')),
                "สถานะ": r.get('status', 'Inactive')
            })
        st.table(pd.DataFrame(table_data))
        
        st.markdown("---")
        st.subheader("📝 แก้ไขสิทธิ์และวันหมดอายุรายคอร์ส")
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            edit_id = st.number_input("ระบุ Course ID ที่ต้องการแก้ไข", min_value=1, step=1)
        
        target = df_courses[df_courses['course_id'].astype(int) == int(edit_id)]
        if not target.empty:
            with col_e2:
                new_p = st.number_input("แก้สิทธิ์คงเหลือ Private", value=int(float(target['rem_private'].iloc[0])))
                new_d = st.number_input("แก้สิทธิ์คงเหลือ Duo", value=int(float(target['rem_duo'].iloc[0])))
                new_g = st.number_input("แก้สิทธิ์คงเหลือ Group", value=int(float(target['rem_group'].iloc[0])))
                new_expiry = st.date_input("วันหมดอายุใหม่", value=pd.to_datetime(target['expiry_date'].iloc[0]))
            
            if st.button("✅ ยืนยันการแก้ไขข้อมูลคอร์ส"):
                clean_date = f"'{new_expiry.strftime('%Y-%m-%d')}"
                payload = {
                    "action": "update_course_details_hybrid",
                    "course_id": int(edit_id),
                    "new_private": new_p,
                    "new_duo": new_d,
                    "new_group": new_g,
                    "new_expiry": clean_date
                }
                if send_action_to_script(payload):
                    st.success("อัปเดตสิทธิ์ผสมของคอร์สเรียบร้อยแล้ว!")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("ระบุ Course ID ด้านบนเพื่อเริ่มการแก้ไข")

# ==========================================
# 3. หน้าจัดการตารางคลาสเรียน
# ==========================================
elif choice == "🏫 จัดการตารางคลาสเรียน":
    st.header("🏫 ระบบบริหารจัดการและวางตารางคลาสเรียน")
    df_classes_check = load_data_from_sheet("classes")
    if not df_classes_check.empty:
        df_classes_check.columns = [c.strip() for c in df_classes_check.columns]
    
    with st.expander("➕ เพิ่มตารางคลาสใหม่", expanded=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            insert_mode = st.radio("รูปแบบการลงตาราง", ["เพิ่มวันเดียวแบบปกติ", "ตั้งตารางประจำ (Routine)"])
            raw_class_name = st.text_input("ชื่อคลาสเรียน *")
            instructor = st.text_input("ชื่อครูผู้สอน *")
            class_type = st.selectbox("ประเภทคลาส *", ["คลาสเดี่ยว (Private)", "คลาสคู่ (Duo)", "คลาสกลุ่ม (Group)"])
            
            time_slots = [f"{h:02d}:00 - {h+1:02d}:00" for h in range(8, 21)]
            selected_time = st.selectbox("⏱️ ระบุเวลาเข้าเรียน *", time_slots, index=11)
            chosen_color = st.color_picker("🎨 เลือกสีกล่องปฏิทิน", "#E3F2FD")
            
        with col_f2:
            if insert_mode == "เพิ่มวันเดียวแบบปกติ":
                single_date = st.date_input("วันที่เปิดสอน", value=today_date)
            else:
                days_of_week = st.multiselect("เลือกวันในสัปดาห์", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                routine_range = st.selectbox("ระยะเวลาวนลูป", ["1 เดือน", "3 เดือน"])

            if st.button("🚀 บันทึกตารางคลาสเรียน", type="primary"):
                if not raw_class_name.strip():
                    st.error("❌ กรุณากรอกชื่อคลาสเรียน")
                else:
                    class_name_with_time = f"{raw_class_name.strip()} ({selected_time})"
                    start_id = 1 if df_classes_check.empty else int(df_classes_check["class_id"].max()) + 1
                    rows_to_send = []
                    
                    if insert_mode == "เพิ่มวันเดียวแบบปกติ":
                        rows_to_send = [[start_id, class_name_with_time, instructor.strip(), f"'{single_date.strftime('%Y-%m-%d')}'", class_type, chosen_color]]
                    else:
                        months = 1 if routine_range == "1 เดือน" else 3
                        end_date = today_date + relativedelta(months=months)
                        curr = today_date
                        day_map = {"Monday":0, "Tuesday":1, "Wednesday":2, "Thursday":3, "Friday":4, "Saturday":5, "Sunday":6}
                        target_days = [day_map[d] for d in days_of_week]
                        
                        while curr <= end_date:
                            if curr.weekday() in target_days:
                                rows_to_send.append([start_id, class_name_with_time, instructor.strip(), f"'{curr.strftime('%Y-%m-%d')}'", class_type, chosen_color])
                                start_id += 1
                            curr += datetime.timedelta(days=1)
                    
                    if rows_to_send:
                        if send_action_to_script({"action": "insert_classes_bulk", "sheet_name": "classes", "rows_data": rows_to_send}):
                            st.cache_data.clear(); st.success("✨ บันทึกตารางคลาสเรียนสำเร็จ!"); st.rerun()

    st.markdown("---")
    
    view_date_manage = today_date + relativedelta(months=st.session_state["cal_shift_manage"])
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 3, 2])
    with col_btn1:
        if st.session_state["cal_shift_manage"] > -1:
            if st.button("◀️ เดือนก่อนหน้า", use_container_width=True):
                st.session_state["cal_shift_manage"] -= 1
                st.rerun()
        else:
            st.button("◀️ เดือนก่อนหน้า", disabled=True, use_container_width=True)
            
    with col_btn2:
        st.subheader(f"📅 ตารางภาพรวมคลาสเรียนประจำเดือน ({view_date_manage.strftime('%B %Y')})")
        
    with col_btn3:
        if st.session_state["cal_shift_manage"] < 1:
            if st.button("เดือนถัดไป ▶️", use_container_width=True):
                st.session_state["cal_shift_manage"] += 1
                st.rerun()
        else:
            st.button("เดือนถัดไป ▶️", disabled=True, use_container_width=True)

    df_classes_all = load_data_from_sheet("classes")
    if isinstance(df_classes_all, pd.DataFrame) and df_classes_all.empty:
        st.info("ยังไม่มีข้อมูลคลาสเรียนในระบบ")
    else:
        df_classes_all.columns = [c.strip() for c in df_classes_all.columns]
        df_classes_all["clean_date"] = df_classes_all["class_date"].apply(clean_date_string)
        
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdatescalendar(view_date_manage.year, view_date_manage.month)
        days_header = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสฯ", "ศุกร์", "เสาร์"]
        
        hc = st.columns(7)
        for idx, d_name in enumerate(days_header):
            hc[idx].markdown(f"<div style='text-align:center; font-weight:bold; background-color:#333333; color:#ffffff; padding:8px; border-radius:4px; border: 1px solid #444444;'>{d_name}</div>", unsafe_allow_html=True)
            
        for week in month_days:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day.month != view_date_manage.month:
                        st.markdown(f"<p style='color:#555555; text-align:center;'>{day.day}</p>", unsafe_allow_html=True)
                    else:
                        if day == today_date:
                            is_today_style = "border: 2px solid #FF5722; background-color:#3a2214; color:#ffffff;"
                        else:
                            is_today_style = "background-color:#262626; border: 1px solid #444444; color:#ffffff;"
                            
                        st.markdown(f"<div style='{is_today_style} padding:6px; border-radius:4px; font-weight:bold; text-align:center;'>{day.day}</div>", unsafe_allow_html=True)
                        
                        day_str = day.strftime("%Y-%m-%d")
                        match_cls = df_classes_all[df_classes_all["clean_date"] == day_str]
                        for _, c_row in match_cls.iterrows():
                            c_bg = c_row.get("class_color", "#E3F2FD")
                            if pd.isna(c_bg) or str(c_bg).strip() == "":
                                c_bg = "#E3F2FD"
                                
                            st.markdown(f"""
                            <div style='background-color:{c_bg}; font-size:11px; padding:4px; margin-top:4px; border-radius:4px; border-left:4px solid #1E88E5; color:#000000; font-weight:500; line-height:1.3;'>
                                📌 {c_row.get('class_name','')}<br>👤 {c_row.get('instructor','')}
                            </div>
                            """, unsafe_allow_html=True)

# ==========================================
# 4. หน้าเช็กอินเข้าเรียน (Auto FIFO แยกตามหมวดหมู่คลาส)
# ==========================================
elif choice == "🎟️ เช็กอินเข้าเรียน (Auto FIFO)":
    st.header("🎟️ ระบบปฏิทินเช็กอินและยกเลิกแยกตามประเภทคลาสของคอร์สผสม")
    if df_members.empty or df_courses.empty:
        st.warning("⚠️ ในระบบต้องมีประวัติสมาชิกและคอร์สเรียนก่อนทำรายการ")
    else:
        st.subheader("👤 1. เลือกรายชื่อสมาชิกที่จะทำรายการ")
        active_m = df_members[df_members["is_deleted"].astype(str).str.strip() == "0"]
        m_options = {f"ID {r['member_id']}: คุณ {r['name']} (📞 {r['phone']})": r for _, r in active_m.iterrows()}
        selected_m_label = st.selectbox("ค้นหาและเลือกรายชื่อลูกค้าเพื่อดูสถานะการเช็กอิน", list(m_options.keys()))
        m_data = m_options[selected_m_label]
        m_id = str(int(float(str(m_data["member_id"]))))
        
        st.markdown("---")
        
        view_date_checkin = today_date + relativedelta(months=st.session_state["cal_shift_checkin"])
        
        col_cbtn1, col_cbtn2, col_cbtn3 = st.columns([2, 3, 2])
        with col_cbtn1:
            if st.session_state["cal_shift_checkin"] > -1:
                if st.button("◀️ เดือนก่อนหน้า ", use_container_width=True):
                    st.session_state["cal_shift_checkin"] -= 1
                    st.rerun()
            else:
                st.button("◀️ เดือนก่อนหน้า ", disabled=True, use_container_width=True)
                
        with col_cbtn2:
            st.subheader(f"📅 2. ตารางปฏิทินระบุสถานะคลาสเรียนของคุณ {m_data['name']} ({view_date_checkin.strftime('%B %Y')})")
            
        with col_cbtn3:
            if st.session_state["cal_shift_checkin"] < 1:
                if st.button("เดือนถัดไป ▶️ ", use_container_width=True):
                    st.session_state["cal_shift_checkin"] += 1
                    st.rerun()
            else:
                st.button("เดือนถัดไป ▶️ ", disabled=True, use_container_width=True)
                
        st.info("💡 ระบบจะสแกนหาคอร์สผสมที่มีสิทธิ์ตรงกับประเภทคลาสของวันนั้นๆ และจะตัดสิทธิ์จากคอร์สเก่าสุดให้ตามหลัก FIFO")

        df_classes_all = load_data_from_sheet("classes")
        df_attendance = load_data_from_sheet("attendance")
        
        if isinstance(df_classes_all, pd.DataFrame) and df_classes_all.empty:
            st.info("ยังไม่มีข้อมูลตารางสอนคลาสเรียนใดๆ ในเดือนนี้")
        else:
            df_classes_all.columns = [c.strip() for c in df_classes_all.columns]
            df_classes_all["clean_date"] = df_classes_all["class_date"].apply(clean_date_string)
            if isinstance(df_attendance, pd.DataFrame) and not df_attendance.empty:
                df_attendance.columns = [c.strip() for c in df_attendance.columns]
                df_attendance["clean_att_date"] = df_attendance["checkin_date"].apply(clean_date_string)
            
            cal = calendar.Calendar(firstweekday=6)
            month_days = cal.monthdatescalendar(view_date_checkin.year, view_date_checkin.month)
            days_header = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสฯ", "ศุกร์", "เสาร์"]
            
            hc = st.columns(7)
            for idx, d_name in enumerate(days_header):
                hc[idx].markdown(f"<div style='text-align:center; font-weight:bold; background-color:#333333; color:#ffffff; padding:8px; border-radius:4px; border: 1px solid #444444;'>{d_name}</div>", unsafe_allow_html=True)
                
            for week_idx, week in enumerate(month_days):
                cols = st.columns(7)
                for i, day in enumerate(week):
                    with cols[i]:
                        if day.month != view_date_checkin.month:
                            st.markdown(f"<p style='color:#555555; text-align:center;'>{day.day}</p>", unsafe_allow_html=True)
                        else:
                            if day == today_date:
                                is_today_style = "border: 2px solid #FF5722; background-color:#3a2214; color:#ffffff;"
                            else:
                                is_today_style = "background-color:#262626; border: 1px solid #444444; color:#ffffff;"
                                
                            st.markdown(f"<div style='{is_today_style} padding:6px; border-radius:4px; font-weight:bold; text-align:center;'>{day.day}</div>", unsafe_allow_html=True)
                            
                            day_str = day.strftime("%Y-%m-%d")
                            match_cls = df_classes_all[df_classes_all["clean_date"] == day_str]
                            
                            for c_idx, c_row in match_cls.iterrows():
                                cls_id = str(int(float(str(c_row["class_id"]))))
                                target_class_type = str(c_row["class_type"]).strip()
                                
                                is_booked = False
                                booked_att_id = None
                                booked_course_id = None
                                
                                if isinstance(df_attendance, pd.DataFrame) and not df_attendance.empty:
                                    match_user_att = df_attendance[
                                        (df_attendance["clean_att_date"] == day_str) &
                                        (df_attendance["member_id"].astype(str).str.strip() == m_id) & 
                                        (df_attendance["class_id"].astype(str).str.strip() == cls_id)
                                    ]
                                    if not match_user_att.empty:
                                        is_booked = True
                                        booked_att_id = int(float(str(match_user_att.iloc[0]["attendance_id"])))
                                        booked_course_id = int(float(str(match_user_att.iloc[0]["course_id"])))

                                box_bg = "#C8E6C9" if is_booked else c_row.get("class_color", "#E3F2FD")
                                if pd.isna(box_bg) or str(box_bg).strip() == "":
                                    box_bg = "#E3F2FD"
                                border_color = "#388E3C" if is_booked else "#1E88E5"
                                
                                st.markdown(f"""
                                <div style='background-color:{box_bg}; font-size:11px; padding:6px; margin-top:5px; border-radius:4px; border-left:4px solid {border_color}; color:#000000; font-weight:500; line-height:1.3;'>
                                    <b>📌 {c_row.get('class_name','')}</b><br>
                                    👤 ครู: {c_row.get('instructor','')}<br>
                                    🎯 หมวด: {target_class_type}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                if is_booked:
                                    if st.button("🗑️ ลบคืนสิทธิ์", key=f"del_{cls_id}_{week_idx}_{i}_{c_idx}", type="secondary"):
                                        cancel_payload = {
                                            "action": "cancel_checkin_hybrid",
                                            "attendance_id": booked_att_id,
                                            "course_id": booked_course_id,
                                            "class_type": target_class_type
                                        }
                                        if send_action_to_script(cancel_payload):
                                            st.cache_data.clear(); st.success("🔄 คืนสิทธิ์เข้าคอร์สผสมสำเร็จ!"); st.rerun()
                                else:
                                    if st.button("🎟️ ตัดสิทธิ์", key=f"cut_{cls_id}_{week_idx}_{i}_{c_idx}", type="primary"):
                                        df_courses.columns = [c.strip() for c in df_courses.columns]
                                        
                                        slot_col = "rem_private"
                                        if "Duo" in target_class_type: slot_col = "rem_duo"
                                        if "Group" in target_class_type: slot_col = "rem_group"
                                        
                                        valid_courses = df_courses[
                                            (df_courses["member_id"].astype(str).str.strip() == m_id) & 
                                            (df_courses[slot_col].astype(float) > 0) & 
                                            (df_courses["status"].astype(str).str.strip().isin(["Active", "Inactive"])) & 
                                            (df_courses["is_deleted"].astype(str).str.strip() == "0")
                                        ].copy()
                                        
                                        if valid_courses.empty:
                                            st.error(f"❌ ไม่มีโควตาสิทธิ์คงเหลือสำหรับ {target_class_type} ในคอร์สใดๆ ของลูกค้ารายนี้")
                                        else:
                                            valid_courses["clean_signup"] = valid_courses["signup_date"].apply(clean_date_string)
                                            valid_courses = valid_courses.sort_values(by="clean_signup", ascending=True)
                                            
                                            target_course_to_cut = valid_courses.iloc[0]
                                            c_id_to_cut = int(float(str(target_course_to_cut["course_id"])))
                                            c_current_status = str(target_course_to_cut.get("status", "Inactive")).strip()
                                            
                                            try: active_duration_days = int(float(str(target_course_to_cut.get("active_duration", 30))))
                                            except: active_duration_days = 30
                                            
                                            next_att_id = 1 if df_attendance.empty else int(float(str(df_attendance["attendance_id"].max()))) + 1
                                            new_slots = max(0, int(float(str(target_course_to_cut[slot_col]))) - 1)
                                            
                                            if c_current_status == "Inactive":
                                                @st.dialog("⚠️ ยืนยันการเปิดใช้งานคอร์สเรียนผสม")
                                                def confirm_and_activate(payload_data, class_dt_str, days_limit):
                                                    st.warning("💡 คอร์สผสมนี้ปัจจุบันมีสถานะเป็น Inactive")
                                                    st.write(f"การเช็กอินเรียนคลาสนี้ในวันที่ **{class_dt_str}** จะเปิดการทำงานคอร์ส (Active) ทันที")
                                                    
                                                    class_date_obj = datetime.datetime.strptime(class_dt_str, "%Y-%m-%d").date()
                                                    calculated_expiry = class_date_obj + datetime.timedelta(days=days_limit)
                                                    
                                                    st.info(f"📅 เริ่มนับเวลา **{days_limit} วัน** วันหมดอายุใหม่คือ: **{calculated_expiry.strftime('%Y-%m-%d')}**")
                                                    
                                                    if st.button("✅ ยืนยันเปิด Active และหักแต้ม", type="primary", use_container_width=True):
                                                        payload_data["update_course_status"] = "Active"
                                                        payload_data["update_expiry_date"] = f"'{calculated_expiry.strftime('%Y-%m-%d')}'"
                                                        
                                                        if send_action_to_script(payload_data):
                                                            st.cache_data.clear(); st.balloons(); st.rerun()
                                                
                                                base_payload = {
                                                    "action": "checkin_hybrid_course",
                                                    "attendance_row": [next_att_id, int(m_id), int(cls_id), f"'{day_str}'", c_id_to_cut],
                                                    "course_id": c_id_to_cut,
                                                    "slot_column": slot_col,
                                                    "new_slots": new_slots
                                                }
                                                confirm_and_activate(base_payload, day_str, active_duration_days)
                                            
                                            else:
                                                payload = {
                                                    "action": "checkin_hybrid_course",
                                                    "attendance_row": [next_att_id, int(m_id), int(cls_id), f"'{day_str}'", c_id_to_cut],
                                                    "course_id": c_id_to_cut,
                                                    "slot_column": slot_col,
                                                    "new_slots": new_slots
                                                }
                                                if send_action_to_script(payload):
                                                    st.cache_data.clear(); st.balloons(); st.rerun()

elif choice == "📅 ปฏิทินและประวัติการเข้าคลาส":
    st.header("📅 บันทึกการเข้าคลาสและประวัติภาพรวมหลังบ้าน")
    
    df_attendance = load_data_from_sheet("attendance")
    df_classes = load_data_from_sheet("classes")
    
    if df_attendance.empty or df_members.empty or df_classes.empty: 
        st.info("ยังไม่มีข้อมูลประวัติการเข้าคลาสเรียน")
    else:
        # ล้างช่องว่างที่หัวคอลัมน์เพื่อป้องกันการแมตช์พลาด
        df_attendance.columns = [c.strip() for c in df_attendance.columns]
        df_classes.columns = [c.strip() for c in df_classes.columns]
        df_members_clean = df_members[["member_id", "name", "phone"]].copy()
        df_members_clean.columns = [c.strip() for c in df_members_clean.columns]
        
        # แปลง Key สำหรับเชื่อมโยงข้อมูลให้เป็น String และตัดช่องว่างออก
        df_attendance["class_id"] = df_attendance["class_id"].astype(str).str.strip()
        df_classes["class_id"] = df_classes["class_id"].astype(str).str.strip()
        
        df_attendance["member_id"] = df_attendance["member_id"].astype(str).str.strip()
        df_members_clean["member_id"] = df_members_clean["member_id"].astype(str).str.strip()
        
        # 1. นำประวัติเช็กอิน (attendance) มารวมกับรายชื่อลูกค้าเพื่อเอา "ชื่อลูกค้า"
        df_merged = df_attendance.merge(df_members_clean, on="member_id", how="left")
        
        # 2. นำไปรวมกับตารางคลาส (classes) เพื่อดึง "ประเภทคลาส" และ "ครูผู้สอน (Instructor)"
        df_final = df_merged.merge(df_classes[["class_id", "class_type", "instructor"]], on="class_id", how="left")
        
        # จัดเรียงลำดับคอลัมน์ให้สวยงามและอ่านง่ายสำหรับแอดมิน
        # ตรวจสอบชื่อคอลัมน์ที่มีอยู่จริงเพื่อป้องกัน KeyError
        display_cols = []
        col_map = {
            "attendance_id": "รหัสเช็กอิน",
            "checkin_date": "วันที่เข้าเรียน",
            "member_id": "Member ID",
            "name": "ชื่อลูกค้า",
            "class_name": "ชื่อคลาสเรียน",
            "class_type": "ประเภทคลาส (Private/Duo/Group)",
            "instructor": "ครูผู้สอน (Instructor)",
            "course_id": "รหัสคอร์สที่ตัดสิทธิ์"
        }
        
        # ล้างคอลัมน์ที่ดึงมาเกินหรือชื่อซ้ำ และเปลี่ยนชื่อหัวตารางเป็นภาษาไทย
        rename_dict = {}
        for eng_col, thai_col in col_map.items():
            if eng_col in df_final.columns:
                display_cols.append(eng_col)
                rename_dict[eng_col] = thai_col
                
        df_display = df_final[display_cols].copy()
        df_display.rename(columns=rename_dict, inplace=True)
        
        # เรียงลำดับตามวันที่เข้าเรียนล่าสุดขึ้นก่อน (ถ้ามีคอลัมน์วันที่)
        if "วันที่เข้าเรียน" in df_display.columns:
            df_display["วันที่เข้าเรียน"] = df_display["วันที่เข้าเรียน"].apply(clean_date_string)
            df_display = df_display.sort_values(by="วันที่เข้าเรียน", ascending=False)
            
        # แสดงตารางแบบเต็มความกว้างหน้าจอ
        st.dataframe(df_display, use_container_width=True, hide_index=True)

elif choice == "⚠️ ระบบแจ้งเตือนเงื่อนไขพิเศษ":
    st.header("🚨 หน้ารวมรายชื่อวิกฤต (สิทธิ์รวม < 2 หรือ เวลาหมดแต่สิทธิ์เหลือ)")
    alert_list = get_advanced_alert_list(df_members, df_courses, today_date)
    if not alert_list: st.success("🟢 ทุกคนปกติสุขดีครับ")
    else:
        for item in alert_list:
            st.write(f"👤 คุณ {item['name']} - {item['status']} : {item['reason']}")

elif choice == "🧹 ล้างคอร์สที่ไม่ได้ใช้งานเกิน 4 เดือน":
    st.header("🧹 ระบบคัดกรองล้างฐานข้อมูลคอร์สที่ไม่มีความเคลื่อนไหวเกิน 4 เดือน")
    st.info("คอร์สย่อยเก่าๆ ที่ไม่มีการมาลงชื่อเรียนเกิน 4 เดือนจะแสดงที่นี่เพื่อให้แอดมินกดลบทำความสะอาด โดยไม่กระทบกับข้อมูล Member ID หลัก")
