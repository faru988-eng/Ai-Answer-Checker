# AI Answer Checker (Streamlit)

## Features
- Teacher enters a question, reference answer, maximum marks and number of copies.
- Upload multiple photos/pages for each student's answer.
- Gemini AI reads handwriting and evaluates the answer.
- Teacher can edit extracted text, marks, mistakes, strengths and feedback.
- Continue confirms the current copy and advances to the next one.
- Final marks table and CSV export.

## Requirements
- Python 3.10+
- Internet connection
- Gemini API key from Google AI Studio: https://aistudio.google.com/app/apikey

## Run on Windows
1. Extract the project ZIP.
2. Open Command Prompt in the project folder.
3. Create and activate a virtual environment (optional but recommended):

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Run:

   ```bash
   streamlit run app.py
   ```

6. Open the local URL shown in the terminal (usually http://localhost:8501).
7. Enter your Gemini API key inside the app when prompted.

## Important notes
- Each copy can have multiple page photos. Upload them together for that student, in page order.
- This is an AI-assisted marking tool, not a fully reliable replacement for a teacher. Always review the extracted handwriting and marks before confirming.
- Clear, straight, well-lit photos improve handwriting recognition.
- Do not upload sensitive student information unless you have permission and are comfortable sending those images to the AI provider.
- API usage may incur charges or be subject to the provider's free-tier limits.
- The current MVP keeps results in Streamlit session memory. Download the CSV before closing or refreshing the session.
