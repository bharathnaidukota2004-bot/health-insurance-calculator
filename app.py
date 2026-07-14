import streamlit as st
import pandas as pd
from datetime import date, datetime
import tempfile
import os

# Import your existing calculator functions
from premium_calculator import (
    get_all_premiums,
    export_to_pdf,
    calculate_completed_age,
    ICICI_SI_OPTIONS,
    TATA_SI_OPTIONS,
)

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Health Insurance Premium Calculator",
    page_icon="🩺",
    layout="wide",
)

st.title("🩺 Health Insurance Premium Calculator")
st.markdown("Compare ICICI Elevate & Tata AIG Medicare Select Base Premiums")

# ============================================================
# SIDEBAR - INPUTS
# ============================================================
with st.sidebar:
    st.header("📋 Input Details")

    # Insurer selection
    insurer_choice = st.multiselect(
        "Select Insurers",
        options=["ICICI", "Tata"],
        default=["ICICI", "Tata"],
    )

    if not insurer_choice:
        st.warning("Please select at least one insurer.")
        st.stop()

    # Policy Start Date
    policy_start = st.date_input("Policy Start Date", value=date.today())

    # Family Members
    st.subheader("👨‍👩‍👧‍👦 Family Members")
    num_members = st.number_input(
        "Number of members",
        min_value=1,
        max_value=10,
        value=1,
        step=1,
    )

    members = []
    for i in range(num_members):
        cols = st.columns([2, 3])
        with cols[0]:
            name = st.text_input(f"Name {i+1}", value=f"Member {i+1}", key=f"name_{i}")
        with cols[1]:
            dob = st.date_input(
                f"DOB {i+1}",
                value=date(1990, 1, 1),
                key=f"dob_{i}",
                max_value=date.today(),
            )
        members.append((name, dob))

    # Zone
    zone_options = ["Zone_A", "Zone_B", "Zone_C", "Zone_D"]
    zone = st.selectbox("Zone", zone_options, index=0)

    # Sum Insured
    st.subheader("💰 Sum Insured Options")

    # Predefined SI options based on selection (allow custom)
    all_si_options = list(set(ICICI_SI_OPTIONS + TATA_SI_OPTIONS))
    si_input = st.text_input(
        "Enter SI values (comma separated, e.g., 5L,10L,50L)",
        value="5L,10L,25L,50L",
    )
    si_list = [s.strip().upper() for s in si_input.split(",") if s.strip()]

    # Tenure
    tenure = st.slider("Policy Tenure (years)", min_value=1, max_value=5, value=2)
    if "Tata" in insurer_choice and tenure > 3:
        st.info("Tata supports max 3 years. Tenure will be capped for Tata.")

    # Discounts
    st.subheader("🎯 Optional Discounts")
    prof_disc = st.checkbox("Professional Discount (7.5%)")
    young_disc = st.checkbox("Young Family Discount (10%)")

    calculate_btn = st.button("🧮 Calculate Premiums", type="primary")

# ============================================================
# MAIN - RESULTS
# ============================================================
if calculate_btn:
    if not si_list:
        st.error("Please enter at least one Sum Insured value.")
        st.stop()

    # Determine valid tenures per insurer
    icici_tenure = tenure if "ICICI" in insurer_choice else None
    tata_tenure = min(tenure, 3) if "Tata" in insurer_choice else None

    # We need to call get_all_premiums for each insurer
    all_results = {}
    with st.spinner("Calculating premiums..."):
        for ins in insurer_choice:
            zone_display = zone
            # Tata doesn't have Zone_D
            if ins == "Tata" and zone == "Zone_D":
                st.warning("Tata does not have Zone_D. Defaulting to Zone_A for Tata.")
                zone_display = "Zone_A"

            # Validate SI list for the insurer
            valid_sis = ICICI_SI_OPTIONS if ins == "ICICI" else TATA_SI_OPTIONS
            valid_si_list = [s for s in si_list if s in valid_sis]
            if not valid_si_list:
                st.warning(
                    f"No valid SI for {ins}. Available: {', '.join(valid_sis)}"
                )
                continue

            # Calculate
            results = get_all_premiums(
                insurer=ins,
                members=members,
                policy_start=policy_start,
                zone=zone_display,
                si_list=valid_si_list,
                tenure=tenure if ins == "ICICI" else min(tenure, 3),
                professional_discount=prof_disc,
                young_family_discount=young_disc,
            )
            all_results[ins] = results

    if not all_results:
        st.error("No valid premiums calculated. Check your inputs.")
        st.stop()

    # ---- Display Results ----
    st.subheader("📊 Premium Comparison (Inclusive of GST)")

    # Build a DataFrame
    rows = []
    # Gather all SI keys
    all_si = set()
    for results in all_results.values():
        all_si.update(results.keys())

    # Sort SIs
    def si_sort_key(si: str) -> float:
        si_upper = si.upper()
        if si_upper == "UNLIMITED":
            return float("inf")
        try:
            if "CR" in si_upper:
                return float(si_upper.replace("CR", "")) * 100
            if "L" in si_upper:
                return float(si_upper.replace("L", ""))
            return float(si_upper)
        except ValueError:
            return 999999

    sorted_sis = sorted(all_si, key=si_sort_key)

    for si in sorted_sis:
        row = {"Sum Insured": si}
        for ins, results in all_results.items():
            res = results.get(si, {})
            if "premium_including_gst" in res:
                row[ins] = f"₹{res['premium_including_gst']:,.2f}"
            else:
                row[ins] = "Error" if "error" in res else "N/A"
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # ---- Show detailed breakdown if needed ----
    with st.expander("🔍 Show Detailed Breakdown"):
        for ins, results in all_results.items():
            st.markdown(f"### {ins}")
            for si, res in results.items():
                if "error" in res:
                    st.error(f"{si}: {res['error']}")
                    continue
                st.markdown(f"**{si}**")
                if ins == "ICICI":
                    st.write(
                        f"- Eldest Age: {res.get('eldest_age')}, Family Type: {res.get('family_type')}"
                    )
                    st.write(f"- Original Base: ₹{res.get('original_base'):,}")
                    st.write(f"- Discounts: {res.get('discounts_applied')}%")
                    st.write(f"- Premium (excl. GST): ₹{res.get('premium_excluding_gst'):,.2f}")
                    st.write(f"- GST: ₹{res.get('gst_amount'):,.2f}")
                    st.write(f"- ✅ Final: ₹{res.get('premium_including_gst'):,.2f}")
                else:  # Tata
                    for name, age, prem in res.get("members", []):
                        st.write(f"  - {name} (age {age}): ₹{prem:,}")
                    st.write(f"- Original Total: ₹{res.get('original_total'):,}")
                    st.write(
                        f"- Family Floater Discount: {res.get('family_floater_discount')}%"
                    )
                    st.write(f"- Additional Discounts: {res.get('discounts_applied')}%")
                    st.write(f"- Premium (excl. GST): ₹{res.get('premium_excluding_gst'):,.2f}")
                    st.write(f"- GST: ₹{res.get('gst_amount'):,.2f}")
                    st.write(f"- ✅ Final: ₹{res.get('premium_including_gst'):,.2f}")

    # ---- PDF Export ----
    st.subheader("📄 Export Quotation")
    if st.button("Generate PDF Quotation"):
        try:
            # Determine zone to display (use first insurer's zone)
            first_ins = list(all_results.keys())[0]
            zone_display = zone
            if first_ins == "Tata" and zone == "Zone_D":
                zone_display = "Zone_A"

            # Use a temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                temp_path = tmp_file.name

            export_to_pdf(
                quotes=all_results,
                members=members,
                policy_start=policy_start,
                zone=zone_display,
                tenure=tenure,
                prof_disc=prof_disc,
                young_disc=young_disc,
                filename=temp_path,
            )

            # Read the file and offer download
            with open(temp_path, "rb") as f:
                pdf_bytes = f.read()

            st.download_button(
                label="📥 Download PDF",
                data=pdf_bytes,
                file_name="insurance_quote.pdf",
                mime="application/pdf",
            )

            # Clean up temp file
            os.unlink(temp_path)

        except Exception as e:
            st.error(f"Failed to generate PDF: {e}")