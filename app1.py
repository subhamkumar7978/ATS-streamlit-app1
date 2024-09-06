
from dotenv import load_dotenv
import base64
import streamlit as st
import os
import io
from PIL import Image
import fitz  # PyMuPDF
import google.generativeai as genai
import re
import concurrent.futures
import hashlib

# Load environment variables
load_dotenv()

# Configure the generative AI model with API key
genai.configure(api_key='AIzaSyCbUpPCrYvJUJAKYkF3JJ5AsjxNUUBMe2M')

# Function to get response from Gemini AI model
def get_gemini_response(input, pdf_content, prompt):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([input, pdf_content[0], prompt])
    return response.text

# Function to convert PDF pages to images using PyMuPDF
def convert_pdf_to_images(uploaded_file):
    pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    images = []
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        pix = page.get_pixmap()
        images.append(pix.tobytes())  # Convert to bytes format for further processing
    return images

# Hash the content of the resume to use it as a cache key
def hash_resume(uploaded_file):
    file_content = uploaded_file.read()
    return hashlib.md5(file_content).hexdigest()

# Function to handle resume uploads
def input_pdf_setup(uploaded_file):
    pdf_contents = []

    # Process resume
    resume_images = convert_pdf_to_images(uploaded_file)
    first_resume_image = resume_images[0]

    # Convert first resume page to bytes
    resume_img_byte_arr = io.BytesIO()
    resume_img = Image.open(io.BytesIO(first_resume_image))
    resume_img.save(resume_img_byte_arr, format='JPEG')
    resume_img_byte_arr = resume_img_byte_arr.getvalue()

    resume_part = {
        "mime_type": "image/jpeg",
        "data": base64.b64encode(resume_img_byte_arr).decode()
    }
    pdf_contents.append(resume_part)
    
    return pdf_contents

# Function to extract percentage from AI response
def extract_percentage(response_text):
    match = re.search(r'(\d+)%', response_text)
    if match:
        return int(match.group(1))
    return 0

# Function to cache the resume evaluation results
@st.cache_data
def process_resume(uploaded_file, resume_name, input_prompt, input_text):
    file_hash = hash_resume(uploaded_file)  # Hash resume content
    uploaded_file.seek(0)  # Reset file pointer after hashing
    pdf_content = input_pdf_setup(uploaded_file)
    response = get_gemini_response(input_prompt, pdf_content, input_text)
    percentage = extract_percentage(response)
    return (resume_name, percentage, response)

# Streamlit App
st.set_page_config(page_title="ATS Resume Expert")
st.header("ATS Tracking System")

# Input job description
input_text = st.text_area("Job Description: ", key="input")

# New Input for Additional Information and Skills
additional_info = st.text_area("Additional Information:", key="additional_info")
skills_input = st.text_area("Skills:", key="skills_input")

# Multiple file uploader for resumes
uploaded_files = st.file_uploader("Upload your resumes (PDFs)...", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"{len(uploaded_files)} PDF(s) Uploaded Successfully")

# Define button actions
submit1 = st.button("Evaluate Resumes")
submit3 = st.button("Find Top Matching Resumes")

# Simplified Prompts
input_prompt1 = f"""
Review the resume considering the job description, additional info: {additional_info}, and skills: {skills_input}.
For every resume Provide the description why the given resume is getting the percentage. For every resume give same type of description points.
"""

input_prompt3 = f"""
Evaluate the following resumes against the job description, additional info: {additional_info}, and skills: {skills_input}. 
For each resume, return the following details in table format:

1. **Resume Name**: The name of the resume.
2. **Resume Score**: The percentage match based on the job description.
3. **Reason for Score**: A short explanation of why the resume received this score.
4. **Missing Keywords**: List the important keywords or skills missing from the resume.
5. **Description**: A concise evaluation summary (max 50 words).

Format the output as a single consolidated table for all resumes, with the columns: 
Resume Name, Resume Score, Reason for Score, Missing Keywords, and Description.
Ensure the table is sorted by Resume Score in descending order (from high to low).
"""

#If "Evaluate Resumes" is clicked
if submit1:
    if uploaded_files:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(process_resume, uploaded_file, uploaded_file.name, input_prompt1, input_text)
                for uploaded_file in uploaded_files
            ]
            for future in concurrent.futures.as_completed(futures):
                resume_name, _, response = future.result()
                st.subheader(f"Evaluation for {resume_name}:")
                st.write(response)
    else:
        st.write("Please upload at least one resume.")

#If "Find Top Matching Resumes" is clicked
elif submit3:
    if uploaded_files:
        results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(process_resume, uploaded_file, uploaded_file.name, input_prompt3, input_text)
                for uploaded_file in uploaded_files
            ]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        # Sort results by percentage match
        sorted_results = sorted(results, key=lambda x: x[1], reverse=True)

        st.subheader("Top Matching Resumes (High to Low):")
        for resume_name, percentage, response in sorted_results:
            st.write(f"Resume: {resume_name}")
            st.write(f"Percentage Match: {percentage}%")
            st.write(f"Response: {response}")
            #st.write("---")
            st.markdown(response, unsafe_allow_html=True)
    else:
        st.write("Please upload at least one resume.")
