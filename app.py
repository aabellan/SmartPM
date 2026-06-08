import streamlit as st
import os
import tempfile
from collections import Counter
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from xerparser.reader import Reader

st.set_page_config(page_title="SmartPM Python", page_icon="📊", layout="wide")

st.title("🚀 CHEC SmartPM A3")
st.markdown("**Primavera P6 .XER Analyzer • Final Stable**")
st.divider()

# ====================== HELPERS ======================
def safe_get(obj, attr, default=None):
    if obj is None:
        return default
    value = getattr(obj, attr, default)
    return value if value is not None else default

def get_activity_date(act, preferred_fields):
    for field in preferred_fields:
        date_val = safe_get(act, field)
        if date_val:
            try:
                return pd.to_datetime(date_val)
            except:
                continue
    return None

@st.cache_data(show_spinner=False)
def parse_xer_file(uploaded_file):
    if uploaded_file is None:
        return None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xer") as tmp:
        tmp.write(uploaded_file.getbuffer())
        temp_path = tmp.name
    try:
        return Reader(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# ====================== SIDEBAR ======================
with st.sidebar:
    # === Company Logo at the top of Sidebar ===
    try:
        st.image("China_Harbour-no bg.png", width=220)  # Adjust width as needed
    except:
        st.markdown("**SmartPM Python**")  # Fallback if logo not found

    st.header("📁 Upload Schedules")
    current_file = st.file_uploader("Current Schedule (.XER)", type=["xer"], key="current")
    baseline_file = st.file_uploader("Baseline Schedule (.XER)", type=["xer"], key="baseline")
    
    if st.button("🔄 Clear All Data"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.caption("Version 0.8.5 • SmartPM Alternative")

# ====================== LOAD DATA ======================
if current_file:
    with st.spinner("🔄 Parsing Current Schedule..."):
        xer_current = parse_xer_file(current_file)
        if xer_current:
            projects = list(xer_current.projects) if hasattr(xer_current, 'projects') else []
            if projects:
                proj_names = [safe_get(p, 'proj_short_name', f"Project {i}") for i, p in enumerate(projects)]
                selected = st.selectbox("Select Project", proj_names, key="curr_select")
                idx = proj_names.index(selected)
                project_current = projects[idx]
                
                st.success(f"✅ Loaded: **{safe_get(project_current, 'proj_name')}**")
                st.session_state['xer_current'] = xer_current
                st.session_state['project_current'] = project_current
                st.session_state['activities'] = getattr(project_current, 'activities', []) or []
                st.session_state['relationships'] = getattr(xer_current, 'relations', []) or []

if baseline_file and 'project_current' in st.session_state:
    with st.spinner("🔄 Parsing Baseline..."):
        xer_base = parse_xer_file(baseline_file)
        if xer_base and hasattr(xer_base, 'projects'):
            st.session_state['project_baseline'] = list(xer_base.projects)[0]
            st.success("✅ Baseline Loaded")

# ====================== TABS ======================
if 'project_current' in st.session_state:
    project = st.session_state['project_current']
    activities = st.session_state.get('activities', [])
    relationships = st.session_state.get('relationships', [])

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Summary", "📅 Activities", "🔥 Critical Path", 
        "🔍 Quality Dashboard", "🔗 Relationships", "📈 S-Curves"
    ])

    with tab1:
        st.subheader("Project Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Activities", f"{len(activities):,}")
        with col2: st.metric("Relationships", f"{len(relationships):,}")
        with col3: st.metric("Data Date", safe_get(project, 'last_recalc_date', 'N/A'))
        with col4: st.metric("Project ID", safe_get(project, 'proj_short_name', 'N/A'))

    with tab2:
        st.subheader("Activities List")
        if st.button("Load Activities Table", key="load_acts"):
            with st.spinner("Loading activities..."):
                act_data = [{
                    "ID": safe_get(act, 'task_code', ''),
                    "Name": safe_get(act, 'task_name', ''),
                    "Duration (days)": round(safe_get(act, 'target_drtn_hr_cnt', 0) / 8, 1),
                    "Start": get_activity_date(act, ['early_start_date', 'act_start_date', 'target_start_date']),
                    "% Complete": safe_get(act, 'phys_complete_pct', 0),
                    "Total Float (days)": round(safe_get(act, 'total_float_hr_cnt', 0) / 8, 1)
                } for act in activities[:2000]]
                df_acts = pd.DataFrame(act_data)
                st.dataframe(df_acts, use_container_width=True, hide_index=True)
                st.download_button("📥 Download Activities CSV", df_acts.to_csv(index=False).encode('utf-8'), "activities.csv", "text/csv")

    with tab3:
        st.subheader("🔥 Critical Path Analysis")
        if st.button("🔄 Analyze Critical Path & Generate Gantt", type="primary"):
            with st.spinner("Building Critical Path Gantt..."):
                # Filter real activities only (exclude milestones)
                critical_acts = [act for act in activities 
                               if safe_get(act, 'total_float_hr_cnt', 999) <= 0 
                               and safe_get(act, 'target_drtn_hr_cnt', 0) > 0]

                st.success(f"**{len(critical_acts)} Critical Activities** (Milestones excluded)")

                crit_data = []
                for act in critical_acts[:600]:
                    start_d = get_activity_date(act, ['act_start_date', 'early_start_date', 'target_start_date'])
                    finish_d = get_activity_date(act, ['act_end_date', 'early_finish_date', 'target_end_date'])
                    full_name = safe_get(act, 'task_name', 'Unnamed Activity')
                    short_name = (full_name[:55] + '...') if len(full_name) > 55 else full_name
                    
                    crit_data.append({
                        "Activity Name": short_name,
                        "Full Name": full_name,
                        "ID": safe_get(act, 'task_code', ''),
                        "Duration (days)": round(safe_get(act, 'target_drtn_hr_cnt', 0)/8, 1),
                        "Early Start": start_d.strftime("%Y-%m-%d") if start_d else None,
                        "Early Finish": finish_d.strftime("%Y-%m-%d") if finish_d else None,
                    })

                crit_df = pd.DataFrame(crit_data)
                st.dataframe(crit_df[["ID", "Activity Name", "Duration (days)", "Early Start", "Early Finish"]], 
                           use_container_width=True)

                # ==================== CLEAN GANTT ====================
                if not crit_df.empty:
                    gantt_df = crit_df.copy()
                    gantt_df['Start'] = pd.to_datetime(gantt_df['Early Start'], errors='coerce')
                    gantt_df['Finish'] = pd.to_datetime(gantt_df['Early Finish'], errors='coerce')
                    gantt_df = gantt_df.dropna(subset=['Start', 'Finish']).sort_values('Start')

                    if not gantt_df.empty:
                        fig = px.timeline(
                            gantt_df,
                            x_start="Start",
                            x_end="Finish",
                            y="Activity Name",
                            title="Critical Path Gantt Chart",
                            hover_data=["ID", "Full Name", "Duration (days)"],
                            color="Duration (days)",
                            color_continuous_scale="Reds"
                        )
                        
                        # Removed text inside bars as requested
                        fig.update_traces(text=None)
                        
                        fig.update_yaxes(autorange="reversed", title="Activity Name")
                        fig.update_layout(
                            height=850,
                            showlegend=False,
                            xaxis_title="Timeline",
                            margin=dict(l=50, r=50, t=80, b=50)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No valid dates found for Gantt chart.")
                else:
                    st.info("No critical activities with duration > 0 found.")

    with tab4:
        st.subheader("📊 SmartPM-Style Quality Dashboard")
        if st.button("🔄 Run Full Quality Analysis", type="primary"):
            with st.spinner("Running SmartPM-level analysis..."):
                # === Calculations ===
                open_ends = sum(1 for a in activities if not safe_get(a, 'predecessors', None) or not safe_get(a, 'successors', None))
                negative_lags = sum(1 for r in relationships if safe_get(r, 'lag_hr_cnt', 0) < 0)
                positive_lags = sum(1 for r in relationships if safe_get(r, 'lag_hr_cnt', 0) > 0)
                high_duration = sum(1 for a in activities if safe_get(a, 'target_drtn_hr_cnt', 0)/8 > 30)
                high_float = sum(1 for a in activities if safe_get(a, 'total_float_hr_cnt', 0)/8 > 60)
                neg_float = sum(1 for a in activities if safe_get(a, 'total_float_hr_cnt', 0) < 0)
                hard_constraints = sum(1 for a in activities if safe_get(a, 'constraint_type', ''))
                resource_loaded = sum(1 for a in activities if len(getattr(a, 'resources', [])) > 0)

                total_acts = len(activities)
                total_rels = len(relationships)

                # === Main Table ===
                metrics_data = {
                    "Metric": [
                        "Open Ends (Dangling Logic)",
                        "Negative Lags (Leads)",
                        "Positive Lags",
                        "Activities >30 days",
                        "High Float Activities (>60d)",
                        "Negative Float",
                        "Hard Constraints",
                        "Resource Loaded Activities"
                    ],
                    "Value": [open_ends, negative_lags, positive_lags, high_duration, high_float, neg_float, hard_constraints, resource_loaded],
                    "Target": ["≤ 5", "0", "≤ 5%", "≤ 10%", "≤ 5%", "0", "≤ 5", "≥ 30%"],
                    "Status": [
                        "Review" if open_ends > 5 else "Good",
                        "⚠️ Critical" if negative_lags > 0 else "Good",
                        "Review" if positive_lags > total_rels*0.05 else "Good",
                        "Review" if high_duration > total_acts*0.1 else "Good",
                        "Review" if high_float > total_acts*0.05 else "Good",
                        "⚠️ Critical" if neg_float > 0 else "Good",
                        "Review" if hard_constraints > 5 else "Good",
                        "Good"
                    ]
                }

                df = pd.DataFrame(metrics_data)
                st.dataframe(df[["Metric", "Value", "Target", "Status"]], use_container_width=True, hide_index=True)

                # Overall Score
                score = 100
                if open_ends > 10: score -= 30
                elif open_ends > 5: score -= 15
                if negative_lags > 0: score -= 25
                if neg_float > 0: score -= 20
                if hard_constraints > 5: score -= 15
                score = max(0, score)

                st.subheader("Overall Schedule Quality")
                st.progress(score / 100)
                if score >= 75:
                    st.success(f"**{score}/100** - Good")
                elif score >= 60:
                    st.warning(f"**{score}/100** - Fair")
                else:
                    st.error(f"**{score}/100** - Poor")

                st.success("✅ Quality Analysis Complete!")

    with tab5:
        st.subheader("🔗 Detailed Relationships")
        if st.button("Load Relationships", key="load_rels"):
            with st.spinner("Loading relationships with Activity Names..."):
                try:
                    # === SUPER ROBUST ID → NAME MAPPING ===
                    activity_map = {}
                    for act in activities:
                        name = safe_get(act, 'task_name', 'Unnamed Activity')
                        
                        # Try all possible ID fields
                        for id_field in ['task_code', 'act_code', 'task_id', 'activity_id', 'id']:
                            act_id = safe_get(act, id_field, '')
                            if act_id:
                                activity_map[act_id] = name
                                # Also store as string and stripped
                                activity_map[str(act_id).strip()] = name
                        
                    st.info(f"✅ Mapped **{len(activity_map)}** activity names for lookup")

                    # === Build Relationships ===
                    rel_data = []
                    loaded = 0
                    
                    for rel in relationships:
                        if loaded >= 5000:
                            break
                        try:
                            pred_id = str(safe_get(rel, 'pred_task_id', '')).strip()
                            succ_id = str(safe_get(rel, 'task_id', '')).strip()
                            rel_type = safe_get(rel, 'pred_type', 'Unknown')
                            lag_hrs = safe_get(rel, 'lag_hr_cnt', 0)
                            lag_days = round(lag_hrs / 8, 2)

                            pred_name = activity_map.get(pred_id, "Unknown Activity")
                            succ_name = activity_map.get(succ_id, "Unknown Activity")

                            # Quality Status
                            if lag_hrs < 0:
                                status = "🔴 Critical (Lead)"
                            elif lag_hrs > 480:
                                status = "🟠 Long Lag"
                            elif lag_hrs > 0:
                                status = "🟡 Positive Lag"
                            else:
                                status = "🟢 Normal"

                            rel_data.append({
                                "Predecessor ID": pred_id,
                                "Predecessor Name": pred_name,
                                "Successor ID": succ_id,
                                "Successor Name": succ_name,
                                "Type": rel_type,
                                "Lag (days)": lag_days,
                                "Status": status
                            })
                            loaded += 1
                        except:
                            continue

                    if rel_data:
                        rel_df = pd.DataFrame(rel_data)
                        st.dataframe(
                            rel_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Predecessor Name": st.column_config.TextColumn("Predecessor Name", width="large"),
                                "Successor Name": st.column_config.TextColumn("Successor Name", width="large")
                            }
                        )
                        st.success(f"✅ Loaded **{len(rel_df)}** relationships")
                        st.download_button(
                            "📥 Download Relationships CSV",
                            rel_df.to_csv(index=False).encode('utf-8'),
                            "relationships.csv",
                            "text/csv"
                        )
                    else:
                        st.warning("No relationships could be loaded.")

                except Exception as e:
                    st.error(f"Could not load relationships: {str(e)[:150]}")

    with tab6:
        st.subheader("📈 S-Curves (Early / Late / Actual % Complete)")
        if 'project_baseline' not in st.session_state:
            st.warning("Upload a Baseline .XER to generate proper S-Curves (uses Baseline for timeline)")
        else:
            if st.button("📊 Generate S-Curves (Early / Late / Actual %)", type="primary"):
                with st.spinner("Building S-Curves using Baseline as Commitment..."):
                    base_proj = st.session_state['project_baseline']
                    curr_proj = st.session_state['project_current']

                    # === Get data from Baseline (for timeline & planned curves) ===
                    base_data = []
                    for act in getattr(base_proj, 'activities', []):
                        es = get_activity_date(act, ['early_start_date', 'act_start_date', 'target_start_date'])
                        ef = get_activity_date(act, ['early_finish_date', 'act_end_date', 'target_end_date'])
                        ls = get_activity_date(act, ['late_start_date']) or es
                        lf = get_activity_date(act, ['late_end_date']) or ef
                        if es and ef:
                            base_data.append({
                                "Early_Start": es,
                                "Early_Finish": ef,
                                "Late_Start": ls,
                                "Late_Finish": lf,
                            })
                    df_base = pd.DataFrame(base_data)

                    # === Get Actual % Complete from Current Update ===
                    actual_data = []
                    total_pct = 0
                    for act in getattr(curr_proj, 'activities', []):
                        pct = safe_get(act, 'phys_complete_pct', 0)
                        total_pct += pct
                        actual_data.append({"Pct_Complete": pct})
                    df_actual = pd.DataFrame(actual_data)

                    overall_complete = total_pct / len(df_actual) if len(df_actual) > 0 else 0
                    st.info(f"**Overall Physical % Complete**: {overall_complete:.2f}%")

                    if df_base.empty:
                        st.error("No valid dates found in Baseline.")
                    else:
                        total_acts = len(df_base)

                        def build_planned_curve(df, start_col, finish_col):
                            monthly = []
                            for _, row in df.iterrows():
                                months = pd.date_range(row[start_col], row[finish_col], freq='MS')
                                if len(months) == 0:
                                    months = [row[start_col]]
                                prog = 100.0 / total_acts / len(months)
                                for m in months:
                                    monthly.append({"Month": m.strftime("%Y-%m"), "Progress": prog})
                            return pd.DataFrame(monthly).groupby("Month")["Progress"].sum().cumsum()

                        early_curve = build_planned_curve(df_base, "Early_Start", "Early_Finish")
                        late_curve = build_planned_curve(df_base, "Late_Start", "Late_Finish")

                        # Simple Actual Progress (cumulative)
                        actual_curve = pd.Series()
                        if overall_complete > 0:
                            project_start = df_base['Early_Start'].min()
                            today = pd.Timestamp.today()
                            months = pd.date_range(project_start, today, freq='MS')
                            if len(months) > 0:
                                monthly_progress = overall_complete / len(months)
                                cum = 0
                                for m in months:
                                    cum += monthly_progress
                                    actual_curve[m.strftime("%Y-%m")] = cum

                        # Full timeline from Baseline start
                        project_start = df_base['Early_Start'].min()
                        all_months = pd.date_range(project_start, early_curve.index.max(), freq='MS').strftime("%Y-%m")

                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=early_curve.index, y=early_curve.values, 
                                               name="Early Curve (Planned)", line=dict(color="blue", width=3)))
                        fig.add_trace(go.Scatter(x=late_curve.index, y=late_curve.values, 
                                               name="Late Curve", line=dict(color="red", width=3, dash="dash")))
                        fig.add_trace(go.Scatter(x=actual_curve.index, y=actual_curve.values, 
                                               name="Actual Progress (% Complete)", line=dict(color="green", width=4)))

                        fig.update_layout(
                            title="S-Curve: Early vs Late vs Actual % Complete",
                            xaxis_title="Month",
                            yaxis_title="Cumulative Progress (%)",
                            height=650,
                            hovermode="x unified",
                            yaxis=dict(range=[0, 105]),
                            xaxis=dict(tickangle=45)
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # Download
                        combined = pd.DataFrame({
                            "Month": all_months,
                            "Early Curve (%)": early_curve.reindex(all_months, fill_value=0),
                            "Late Curve (%)": late_curve.reindex(all_months, fill_value=0),
                            "Actual % Complete": actual_curve.reindex(all_months, fill_value=0)
                        })
                        st.download_button("📥 Download S-Curve Data", 
                                         combined.to_csv(index=False).encode('utf-8'),
                                         "s_curve.csv", "text/csv")
else:
    st.info("👆 Upload a Current .XER file to begin.")

st.caption("SmartPM Python Alternative • v0.8.5")