import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="مقارنة بيانات الموظفين", layout="wide")
st.title("مقارنة مرنة بين ملفي بيانات الموظفين")

def normalize_name(name):
    if pd.isnull(name):
        return ""
    name = str(name).strip()
    name = name.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return name.lower()

# رفع الملفات
old_file = st.file_uploader("ارفع ملف البيانات القديمة", type=["xlsx", "csv"])
new_file = st.file_uploader("ارفع ملف البيانات الجديدة", type=["xlsx", "csv"])

if old_file and new_file:

    # قراءة الملفات + تحويل إلى نص (حل مشكلة PyArrow)
    old_df = (pd.read_csv(old_file) if old_file.name.endswith(".csv") else pd.read_excel(old_file)).astype(str)
    new_df = (pd.read_csv(new_file) if new_file.name.endswith(".csv") else pd.read_excel(new_file)).astype(str)

    st.success("تم تحميل الملفين")

    # البحث عن عمود الاسم
    name_col = None
    for col in old_df.columns:
        if "الرقم" in col and "الوظيفي" in col:
            name_col = col
            break

    if not name_col:
        st.error("لم يتم العثور على عمود اسم الموظف")
        st.stop()

    # تنظيف الأسماء
    old_df["normalized_name"] = old_df[name_col].apply(normalize_name)
    new_df["normalized_name"] = new_df[name_col].apply(normalize_name)

    # الأعمدة المشتركة
    shared_cols = list(set(old_df.columns).intersection(set(new_df.columns)))
    shared_cols = [
        col for col in shared_cols
        if col not in [name_col, "normalized_name"] and "تاريخ التعيين" not in col
    ]

    # الدمج
    merged = pd.merge(
        old_df,
        new_df,
        on="normalized_name",
        suffixes=('_old', '_new'),
        how='outer',
        indicator=True
    )

    differences = []
    changed_names = set()

    # المقارنة
    for col in shared_cols:
        col_old = col + "_old"
        col_new = col + "_new"

        if col_old in merged.columns and col_new in merged.columns:
            both_mask = merged["_merge"] == "both"
            compare = merged.loc[both_mask].copy()

            # تنظيف القيم (حل المشاكل)
            compare[col_old] = compare[col_old].astype(str).fillna("").str.strip()
            compare[col_new] = compare[col_new].astype(str).fillna("").str.strip()

            # معالجة خاصة
            if col == "الوحدة التنظيمية":
                compare[col_new] = compare[col_new].str[3:]

            # المقارنة
            diff_mask = compare[col_old] != compare[col_new]

            if diff_mask.any():
                diff_rows = compare.loc[diff_mask, [name_col + "_old", col_old, col_new]].copy()

                diff_rows.rename(columns={
                    name_col + "_old": "اسم الموظف",
                    col_old: "القيمة القديمة",
                    col_new: "القيمة الجديدة"
                }, inplace=True)

                diff_rows["اسم العمود"] = col

                differences.append(
                    diff_rows[["اسم الموظف", "اسم العمود", "القيمة القديمة", "القيمة الجديدة"]]
                )

                changed_names.update(diff_rows["اسم الموظف"].unique())

    # صفوف مفقودة
    new_only = merged[merged["_merge"] == "right_only"]
    old_only = merged[merged["_merge"] == "left_only"]

    # التابات
    tab1, tab2, tab3, tab4 = st.tabs(["الاختلافات", "المفقودون", "رسم بياني", "فلترة"])

    # الاختلافات
    with tab1:
        if differences:
            final_df = pd.concat(differences, ignore_index=True)
            st.subheader("الاختلافات:")
            st.dataframe(final_df, use_container_width=True)
            st.markdown(f"عدد الموظفين المتغيرين: `{len(changed_names)}`")

            csv_data = final_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("تحميل النتائج", data=csv_data, file_name="التغير.csv")

        else:
            st.success("لا توجد اختلافات")

    # المفقودين
    with tab2:
        st.subheader("الموظفون المفقودون")
        if not old_only.empty:
            missing_rows = old_df[old_df["normalized_name"].isin(old_only["normalized_name"])]
            st.dataframe(missing_rows, use_container_width=True)
        else:
            st.info("لا يوجد مفقودين")

    # الرسم البياني
    with tab3:
        if differences:
            chart_df = pd.concat(differences)["اسم العمود"].value_counts().reset_index()
            chart_df.columns = ["العامود", "عدد التغييرات"]

            fig = px.bar(chart_df, x="العامود", y="عدد التغييرات", color="العامود")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا يوجد بيانات")

    # الفلترة
    with tab4:
        if differences:
            final_df = pd.concat(differences, ignore_index=True)

            selected_col = st.selectbox("اختاري العمود:", sorted(final_df["اسم العمود"].unique()))

            filtered_df = final_df[final_df["اسم العمود"] == selected_col]

            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info("لا توجد بيانات")
