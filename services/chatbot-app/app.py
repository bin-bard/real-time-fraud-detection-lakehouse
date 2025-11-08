import streamlit as st

st.set_page_config(page_title='Chatbot')
st.title('Chatbot App - Placeholder')
st.write('This is a placeholder Streamlit app for the chatbot.')

user_input = st.text_input('You:')
if user_input:
    st.write('Bot: (placeholder response)')
