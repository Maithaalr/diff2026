import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="مقارنة بيانات الموظفين", layout="wide")

st.image("logo.png", width=250)
st.title("مقارنة مرنة بين ملفي بيانات الموظفين")


def normalize_name(name):
    if pd.isnull(name):
        return ""
    name = str(name).strip()
    name = (
        name.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
    )
    return name.lower()


old_file = st.file_uploader("ارفع ملف البيانات القديمة", type=["xlsx", "csv"])
new_file = st.file_uploader("ارفع ملف البيانات الجديدة", type=["xlsx", "csv"])

if old_file and new_file:

    old_df = pd.read_csv(old_file) if old_file.name.endswith(".csv") else pd.read_excel(old_file)
    new_df = pd.read_csv(new_file) if new_file.name.endswith(".csv") else pd.read_excel(new_file)

    st.success("تم تحميل الملفين بنجاح")

    # البحث عن عمود اسم الموظف
    name_col = None
    for col in old_df.columns:
        if "اسم" in col and "الموظف" in col:
            name_col = col
            break

    if not name_col:
        st.error("لم يتم العثور على عمود اسم الموظف.")
        st.stop()

    # تنظيف الأسماء
    old_df["normalized_name"] = old_df[name_col].apply(normalize_name)
    new_df["normalized_name"] = new_df[name_col].apply(normalize_name)

    shared_cols = list(set(old_df.columns).intersection(new_df.columns))
    shared_cols = [
        c for c in shared_cols
        if c not in [name_col, "normalized_name"]
        and "تاريخ التعيين" not in c
    ]

    # دمج الملفين
    merged = pd.merge(
        old_df,
        new_df,
        on="normalized_name",
        suffixes=("_old", "_new"),
        how="outer",
        indicator=True
    )

    differences = []
    changed_names = set()

    for col in shared_cols:

        col_old = col + "_old"
        col_new = col + "_new"

        if col_old not in merged.columns or col_new not in merged.columns:
            continue

        compare = merged.loc[merged["_merge"] == "both"].copy()

        if col == "الوحدة التنظيمية":
            compare[col_old] = compare[col_old].astype(str).str.strip()
            compare[col_new] = compare[col_new].astype(str).str[3:].str.strip()

        # حل مشكلة اختلاف أنواع البيانات
        compare[col_old] = compare[col_old].apply(
            lambda x: "" if pd.isna(x) else str(x).strip()
        )

        compare[col_new] = compare[col_new].apply(
            lambda x: "" if pd.isna(x) else str(x).strip()
        )

        diff_mask = compare[col_old] != compare[col_new]

        if diff_mask.any():

            diff_rows = compare.loc[
                diff_mask,
                [name_col + "_old", col_old, col_new]
            ].copy()

            diff_rows.rename(
                columns={
                    name_col + "_old": "اسم الموظف",
                    col_old: "القيمة القديمة",
                    col_new: "القيمة الجديدة",
                },
                inplace=True,
            )

            diff_rows["اسم العمود"] = col

            differences.append(
                diff_rows[
                    [
                        "اسم الموظف",
                        "اسم العمود",
                        "القيمة القديمة",
                        "القيمة الجديدة",
                    ]
                ]
            )

            changed_names.update(diff_rows["اسم الموظف"].unique())

    new_only = merged[merged["_merge"] == "right_only"]
    old_only = merged[merged["_merge"] == "left_only"]

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "الاختلافات",
            "الموظفون المفقودون",
            "رسم بياني",
            "فلترة",
        ]
    )

    # ==========================
    # الاختلافات
    # ==========================

    with tab1:

        if differences:

            final_df = pd.concat(differences, ignore_index=True)

            st.subheader("الاختلافات")

            st.dataframe(final_df, use_container_width=True)

            st.markdown(
                f"**عدد الموظفين الذين تغيرت بياناتهم:** {len(changed_names)}"
            )

            csv_data = final_df.to_csv(index=False).encode("utf-8-sig")

            st.download_button(
                "تحميل النتائج",
                data=csv_data,
                file_name="التغيرات.csv",
                mime="text/csv",
            )

        else:

            st.success("لا توجد اختلافات.")

    # ==========================
    # الموظفون المفقودون
    # ==========================

    with tab2:

        st.subheader("الموظفون الموجودون في الملف الجديد فقط")

        if not new_only.empty:

            missing_rows = new_df[
                new_df["normalized_name"].isin(new_only["normalized_name"])
            ]

            st.dataframe(missing_rows, use_container_width=True)

            csv_missing = missing_rows.to_csv(index=False).encode("utf-8-sig")

            st.download_button(
                "تحميل الموظفين المفقودين",
                data=csv_missing,
                file_name="الموظفين_الجدد.csv",
                mime="text/csv",
            )

        else:

            st.info("لا توجد سجلات جديدة.")

    # ==========================
    # الرسم البياني
    # ==========================

    with tab3:

        if differences:

            chart_df = (
                pd.concat(differences)["اسم العمود"]
                .value_counts()
                .reset_index()
            )

            chart_df.columns = ["العمود", "عدد التغييرات"]

            fig = px.bar(
                chart_df,
                x="العمود",
                y="عدد التغييرات",
                color="العمود",
                color_discrete_sequence=px.colors.sequential.Blues,
            )

            st.plotly_chart(fig, use_container_width=True)

        else:

            st.info("لا توجد بيانات للرسم البياني.")

    # ==========================
    # الفلترة
    # ==========================

    with tab4:

        if differences:

            final_df = pd.concat(differences, ignore_index=True)

            selected_col = st.selectbox(
                "اختاري العمود",
                sorted(final_df["اسم العمود"].unique()),
            )

            values = (
                final_df[
                    final_df["اسم العمود"] == selected_col
                ]["القيمة القديمة"]
                .dropna()
                .unique()
                .tolist()
            )

            selected_value = st.selectbox(
                "اختاري القيمة القديمة",
                ["الكل"] + sorted(values),
            )

            filtered_df = final_df[
                final_df["اسم العمود"] == selected_col
            ]

            if selected_value != "الكل":
                filtered_df = filtered_df[
                    filtered_df["القيمة القديمة"] == selected_value
                ]

            st.dataframe(filtered_df, use_container_width=True)

            st.success(f"عدد النتائج: {len(filtered_df)}")

            csv_data = filtered_df.to_csv(index=False).encode("utf-8-sig")

            st.download_button(
                "تحميل النتائج",
                data=csv_data,
                file_name="الفلترة.csv",
                mime="text/csv",
            )

        else:

            st.info("لا توجد اختلافات.")
