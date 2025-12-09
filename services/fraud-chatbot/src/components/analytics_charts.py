"""
Analytics Charts Component
Vẽ biểu đồ Plotly cho data visualization
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def render_fraud_rate_chart(data: pd.DataFrame, x_col: str, y_col: str, title: str):
    """Vẽ biểu đồ fraud rate"""
    
    fig = px.bar(
        data,
        x=x_col,
        y=y_col,
        title=title,
        labels={y_col: "Fraud Rate (%)"},
        color=y_col,
        color_continuous_scale="Reds"
    )
    
    fig.update_layout(
        xaxis_title=x_col.title(),
        yaxis_title="Fraud Rate (%)",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_time_series_chart(data: pd.DataFrame, x_col: str, y_col: str, title: str):
    """Vẽ biểu đồ time series"""
    
    fig = px.line(
        data,
        x=x_col,
        y=y_col,
        title=title,
        markers=True
    )
    
    fig.update_layout(
        xaxis_title=x_col.title(),
        yaxis_title=y_col.title()
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_pie_chart(data: pd.DataFrame, names_col: str, values_col: str, title: str):
    """Vẽ pie chart"""
    
    fig = px.pie(
        data,
        names=names_col,
        values=values_col,
        title=title
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_scatter_plot(data: pd.DataFrame, x_col: str, y_col: str, color_col: str, title: str):
    """Vẽ scatter plot"""
    
    fig = px.scatter(
        data,
        x=x_col,
        y=y_col,
        color=color_col,
        title=title,
        size=y_col,
        hover_data=data.columns
    )
    
    st.plotly_chart(fig, use_container_width=True)
