import streamlit as st


def write_css():
    st.write(
        """
            <style type="text/css">
            table td:nth-child(1) {
                display: none;
            }
            table th:nth-child(1) {
                display: none;
            }
            table thead th {
                text-align: left;
            }
            table.dataframe {
                display: block;
                overflow-x: scroll;
                overflow-y: scroll;
                height: 600px;
            }
            .row_heading.level0 {
                display:none;
            }
            .blank {
                display:none;
            }
            </style>
        """,
        unsafe_allow_html=True,
    )
