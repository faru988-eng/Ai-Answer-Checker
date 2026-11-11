import hashlib, json, secrets, re, runpy
from io import BytesIO
import streamlit as st
import database as db

st.set_page_config(page_title="Smart Teacher Assistant", page_icon="🎓", layout="wide")
db.init_db()

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310000).hex()
    return value, salt

def check_password(password, user):
    value, _ = hash_password(password, user["salt"])
    return secrets.compare_digest(value, user["password_hash"])

def read_file(file):
    data = file.getvalue()
    if file.name.lower().endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    if file.name.lower().endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(data)).pages)
    if file.name.lower().endswith(".docx"):
        from docx import Document
        return "\n".join(p.text for p in Document(BytesIO(data)).paragraphs)
    raise ValueError("Only PDF, DOCX and TXT are supported.")

def ai_client(key):
    from google import genai
    return genai.Client(api_key=key)

def parse_json(value):
    value = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", value or "", flags=re.I)
    return json.loads(value)

# ---------- Login / registration ----------
if "user" not in st.session_state:
    st.title("🎓 Smart Teacher Assistant")
    st.write("A shared learning platform for teachers and students.")
    login_tab, signup_tab = st.tabs(["Login", "Create account"])
    with login_tab:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            go = st.form_submit_button("Login", type="primary", use_container_width=True)
        if go:
            account = db.get_user_by_email(email.strip())
            if account and check_password(password, account):
                st.session_state.user = account
                st.rerun()
            st.error("Incorrect email or password.")
    with signup_tab:
        role = st.radio("I am a", ["Teacher", "Student"], horizontal=True)
        with st.form("signup"):
            name = st.text_input("Full name")
            new_email = st.text_input("Email address")
            new_password = st.text_input("Password (minimum 8 characters)", type="password")
            confirm = st.text_input("Confirm password", type="password")
            code = st.text_input("Teacher's class code") if role == "Student" else ""
            create = st.form_submit_button("Create account", type="primary")
        if create:
            if not name.strip() or not new_email.strip() or not new_password:
                st.error("Complete all fields.")
            elif len(new_password) < 8:
                st.error("Password must contain at least 8 characters.")
            elif new_password != confirm:
                st.error("Passwords do not match.")
            elif role == "Student" and not db.get_teacher_by_code(code.strip()):
                st.error("Class code not found. Ask your teacher for the correct code.")
            else:
                digest, salt = hash_password(new_password)
                class_code = secrets.token_hex(3).upper() if role == "Teacher" else code.strip().upper()
                try:
                    db.create_user(name.strip(), new_email.strip(), digest, salt, role.lower(), class_code)
                    st.success("Account created. Please log in.")
                    if role == "Teacher":
                        st.info(f"Your class code is {class_code}. Share it with your students.")
                except Exception:
                    st.error("This email may already be registered.")
    st.stop()

user = st.session_state.user
st.sidebar.title("🎓 Smart Teacher")
st.sidebar.write(f"Signed in: **{user['name']}**")
st.sidebar.caption(user["role"].title())
if user["role"] == "teacher":
    st.sidebar.success(f"Student join code: {user['class_code']}")
if st.sidebar.button("Log out", use_container_width=True):
    del st.session_state["user"]
    st.rerun()
api_key = st.sidebar.text_input("Gemini API key", type="password",
    help="Used for the chatbot and AI test generation. Keep your key private.")

# ===================== TEACHER =====================
if user["role"] == "teacher":
    st.title("👩‍🏫 Teacher Dashboard")
    page = st.sidebar.radio("Teacher menu", [
        "Overview", "AI Answer Checker", "Chatbot & Materials",
        "Create Tests", "Learning Tasks", "Students & Results"
    ])

    if page == "Overview":
        stats = db.get_dashboard_stats(user["id"])
        a,b,c,d = st.columns(4)
        a.metric("Students", stats["students"])
        b.metric("Tests", stats["tests"])
        c.metric("Test attempts", stats["attempts"])
        d.metric("Class average", f"{stats['average']}%")
        st.subheader("Recent results")
        rows = db.get_teacher_results(user["id"])
        st.dataframe(rows[:10], use_container_width=True) if rows else st.info("No student submissions yet.")

    elif page == "AI Answer Checker":
        st.header("📝 Handwritten Answer Checker")
        st.write("Your existing Gemini image checker is preserved in this module.")
        runpy.run_path("legacy_answer_checker.py")

    elif page == "Chatbot & Materials":
        st.header("📚 Upload teaching material")
        files = st.file_uploader("Upload PDF, DOCX or TXT", type=["pdf","docx","txt"], accept_multiple_files=True)
        if files and st.button("Save materials"):
            for f in files:
                try:
                    content = read_file(f)
                    if content.strip():
                        db.add_material(user["id"], f.name, content)
                    else:
                        st.warning(f"No readable text found in {f.name}. Scanned PDFs need OCR.")
                except Exception as exc:
                    st.error(f"{f.name}: {exc}")
            st.success("Materials saved to your account.")
            st.rerun()
        materials = db.get_materials(user["id"])
        st.subheader("Your knowledge library")
        for m in materials:
            st.write(f"📄 {m['filename']} · {len(m['content'])} characters")
        st.divider()
        prompt = st.text_area("Ask something from your uploaded material",
            placeholder="Summarize a chapter, explain a topic, or create revision notes...")
        if st.button("Ask AI assistant", type="primary", disabled=not api_key or not prompt.strip()):
            if not materials:
                st.warning("Upload study material first.")
            else:
                source = "\n\n".join(f"FILE: {m['filename']}\n{m['content'][:18000]}" for m in materials)
                instruction = ("You are a teacher's study assistant. Answer using the provided material only. "
                    "If the answer is not present, say so. Never invent facts. Mention relevant source filenames.\n\n"
                    f"MATERIAL:\n{source[:60000]}\n\nQUESTION:\n{prompt}")
                try:
                    with st.spinner("Reading your material..."):
                        answer = ai_client(api_key).models.generate_content(
                            model="gemini-2.0-flash", contents=instruction)
                    st.session_state.teacher_chat_answer = answer.text
                except Exception as exc:
                    st.error(f"AI request failed: {exc}")
        if st.session_state.get("teacher_chat_answer"):
            st.subheader("Answer")
            st.write(st.session_state.teacher_chat_answer)

    elif page == "Create Tests":
        st.header("🧪 Generate tests from your material")
        materials = db.get_materials(user["id"])
        with st.form("test_generation"):
            title = st.text_input("Test title")
            subject = st.text_input("Subject")
            topic = st.text_area("Topic / chapter / instructions")
            amount = st.number_input("Number of MCQs", 1, 30, 5)
            source_from_files = st.checkbox("Use my uploaded materials", value=bool(materials))
            generate = st.form_submit_button("Generate test with AI", type="primary")
        if generate:
            if not api_key:
                st.error("Enter your Gemini API key in the sidebar.")
            elif source_from_files and not materials:
                st.error("Upload material in Chatbot & Materials first.")
            else:
                source = ("\n\n".join(m["content"][:15000] for m in materials)[:50000]
                          if source_from_files else topic)
                if not source.strip():
                    st.error("Enter a topic or upload material.")
                else:
                    instruction = f"""Create {int(amount)} student-friendly MCQs based only on this source.
Return valid JSON only: {{"questions":[{{"question":"...","options":["...","...","...","..."],"correct":"A","explanation":"..."}}]}}
Correct must be A, B, C or D. Do not add facts not in the source.
SOURCE:
{source}"""
                    try:
                        with st.spinner("Creating questions..."):
                            response = ai_client(api_key).models.generate_content(
                                model="gemini-2.0-flash", contents=instruction)
                        questions = parse_json(response.text)["questions"]
                        questions = [q for q in questions if len(q.get("options",[])) == 4 and q.get("correct") in ["A","B","C","D"]]
                        if questions:
                            st.session_state.test_draft = {
                                "title": title.strip() or "New test",
                                "subject": subject.strip() or "General",
                                "questions": questions
                            }
                        else:
                            st.error("No valid MCQs returned. Try again.")
                    except Exception as exc:
                        st.error(f"Test generation failed: {exc}")
        draft = st.session_state.get("test_draft")
        if draft:
            st.subheader("Review before publishing")
            for i,q in enumerate(draft["questions"],1):
                st.markdown(f"**{i}. {q['question']}**")
                for letter, option in zip("ABCD", q["options"]):
                    st.write(f"{letter}. {option}")
                st.caption(f"Answer: {q['correct']} — {q.get('explanation','')}")
            if st.button("Publish test to my students", type="primary"):
                db.add_test(user["id"], draft["title"], draft["subject"], "Choose the best answer.", draft["questions"])
                del st.session_state["test_draft"]
                st.success("Test published for students in your class.")
                st.rerun()

    elif page == "Learning Tasks":
        st.header("📌 Assign learning tasks")
        with st.form("new_task"):
            task_title = st.text_input("What should students learn?")
            task_subject = st.text_input("Subject")
            details = st.text_area("Pages, key points or preparation instructions")
            assign = st.form_submit_button("Assign to class", type="primary")
        if assign:
            if task_title.strip() and task_subject.strip():
                db.add_learning_task(user["id"], task_title, task_subject, details)
                st.success("Task assigned.")
            else:
                st.warning("Enter task title and subject.")

    elif page == "Students & Results":
        st.header("👥 Your students")
        students = db.get_teacher_students(user["id"])
        st.dataframe(students, use_container_width=True) if students else st.info("No students have joined. Share your class code.")
        st.subheader("Test results")
        results = db.get_teacher_results(user["id"])
        st.dataframe(results, use_container_width=True) if results else st.info("No test results yet.")
        if results:
            import pandas as pd
            st.download_button("Download CSV", pd.DataFrame(results).to_csv(index=False),
                               "class_results.csv", "text/csv")

# ===================== STUDENT =====================
else:
    st.title(f"🎒 Student Dashboard — {user['name']}")
    page = st.sidebar.radio("Student menu", ["My Learning Tasks", "Available Tests", "My Results"])
    if page == "My Learning Tasks":
        st.header("📚 What I need to learn")
        tasks = db.get_student_tasks(user["class_code"], user["id"])
        if not tasks:
            st.info("Your teacher has not assigned any learning tasks yet.")
        for task in tasks:
            with st.container(border=True):
                st.subheader(task["title"])
                st.caption(task["subject"])
                st.write(task["details"])
                states = ["To learn", "Learning", "Learned", "Need revision"]
                current = task["status"] if task["status"] in states else states[0]
                selected = st.selectbox("My progress", states, index=states.index(current),
                                        key=f"progress_{task['id']}")
                if selected != current:
                    db.set_task_status(task["id"], user["id"], selected)
                    st.success("Progress saved.")
    elif page == "Available Tests":
        st.header("📝 Tests assigned to your class")
        tests = db.get_student_tests(user["class_code"])
        if not tests:
            st.info("No tests are available yet.")
        for test in tests:
            with st.container(border=True):
                st.subheader(test["title"])
                st.caption(test["subject"])
                if db.student_has_attempted(test["id"], user["id"]):
                    st.success("Submitted")
                    continue
                with st.form(f"attempt_{test['id']}"):
                    answers = []
                    for i,q in enumerate(test["questions"]):
                        st.markdown(f"**Q{i+1}. {q['question']}**")
                        choice = st.radio("Choose answer",
                            [f"A. {q['options'][0]}",f"B. {q['options'][1]}",
                             f"C. {q['options'][2]}",f"D. {q['options'][3]}"],
                            key=f"ans_{test['id']}_{i}")
                        answers.append(choice[0])
                    submit = st.form_submit_button("Submit test", type="primary")
                if submit:
                    score = sum(a == q["correct"] for a,q in zip(answers,test["questions"]))
                    total = len(test["questions"])
                    db.save_test_result(test["id"], user["id"], answers, score, total)
                    st.success(f"Your score: {score}/{total}")
                    st.rerun()
    else:
        st.header("🏆 My results")
        results = db.get_student_results(user["id"])
        st.dataframe(results, use_container_width=True) if results else st.info("You have not attempted any tests yet.")
