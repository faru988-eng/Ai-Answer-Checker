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


## Smart Teacher Assistant (development branch)

This branch adds teacher/student accounts and a classroom workflow.

### Run locally

```bash
git clone -b feature/teacher-student-platform https://github.com/faru988-eng/Ai-Answer-Checker.git
cd Ai-Answer-Checker
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### First-time setup

1. Open the app and create a **Teacher** account.
2. Copy the class join code shown in the sidebar.
3. Give that code to students so they can create Student accounts.
4. Add your Gemini API key in the sidebar to use the AI chatbot and test generator.
5. Upload PDF, DOCX or TXT teaching material in **Chatbot & Materials**.
6. Generate and publish MCQ tests, and assign learning tasks from the teacher menu.

### Current development scope

- Passwords are stored as PBKDF2-HMAC-SHA256 hashes with individual salts.
- SQLite stores accounts, class materials, tests, results and student learning progress.
- Students see tests and learning tasks for the class code they joined.
- The original handwritten answer checker is preserved in `legacy_answer_checker.py`.

### Important deployment note

This is an initial local prototype. Before public deployment, configure a production database, HTTPS, secrets management, rate limiting, account recovery, backups and stronger classroom/teacher authorization. Uploaded documents are currently text-extracted from PDF/DOCX/TXT; scanned PDFs need OCR before their contents can be used by the chatbot.
