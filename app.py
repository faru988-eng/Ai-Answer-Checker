import json
import re
from io import BytesIO

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(page_title="AI Answer Checker", page_icon="📝", layout="wide")

st.title("📝 AI Answer Checker")
st.caption("Upload handwritten answer sheets, review AI feedback, edit marks, and confirm each copy.")

# ---------- Helpers ----------
def extract_json(text):
    """Handle JSON returned with or without Markdown code fences."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise ValueError("The AI response was not valid JSON. Please try again.")

def analyze_copy(api_key, question, reference_answer, max_marks, images):
    client = genai.Client(api_key=api_key)
    prompt = f"""
You are a careful, fair school-exam answer checker.
Question: {question}
Teacher's reference answer: {reference_answer}
Maximum marks: {max_marks}

The attached image(s) are pages from ONE student's answer to this question.
Read the handwriting carefully. Combine the pages in their supplied order.
Evaluate meaning, correct facts, relevant points, and completeness. Do not require
the student's wording to exactly match the reference answer. Do not invent text
that is not visible. If handwriting is unclear, mention that uncertainty.
Award partial credit fairly. Never exceed the maximum marks or go below zero.

Return ONLY valid JSON with this exact structure:
{{
  "extracted_answer": "the student's readable answer, preserving its meaning",
  "marks": 0,
  "mistakes": ["specific mistake or missing point"],
  "strengths": ["correct point identified"],
  "feedback": "short teacher-style feedback",
  "confidence": "High, Medium, or Low"
}}
"""
    content = [prompt]
    for uploaded in images:
        uploaded.seek(0)
        img = Image.open(uploaded).convert("RGB")
        content.append(img)

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=content,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    data = extract_json(response.text)
    data["marks"] = max(0.0, min(float(max_marks), float(data.get("marks", 0))))
    for key in ("mistakes", "strengths"):
        if not isinstance(data.get(key), list):
            data[key] = []
    return data

def init_session():
    defaults = {
        "started": False,
        "question": "",
        "reference": "",
        "max_marks": 10,
        "copy_count": 1,
        "copy_uploads": {},
        "results": [],
        "current_index": 0,
        "analysis": None,
        "analysis_for_index": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session()

# ---------- Setup ----------
if not st.session_state.started:
    st.subheader("1. Set up the checking session")
    with st.form("setup_form"):
        question = st.text_area("Question", placeholder="Enter the exam question...")
        reference = st.text_area("Correct / reference answer", height=180,
                                 placeholder="Enter the answer you want the students' answers compared against...")
        c1, c2 = st.columns(2)
        with c1:
            max_marks = st.number_input("Maximum marks", min_value=1, max_value=100,
                                        value=10, step=1)
        with c2:
            copy_count = st.number_input("Number of copies", min_value=1, max_value=200,
                                         value=5, step=1)
        submitted = st.form_submit_button("Start checking", type="primary", use_container_width=True)

    if submitted:
        if not question.strip() or not reference.strip():
            st.error("Please enter both the question and the reference answer.")
        else:
            st.session_state.question = question.strip()
            st.session_state.reference = reference.strip()
            st.session_state.max_marks = int(max_marks)
            st.session_state.copy_count = int(copy_count)
            st.session_state.started = True
            st.rerun()

# ---------- Copy-by-copy workflow ----------
else:
    total = st.session_state.copy_count
    idx = st.session_state.current_index

    with st.sidebar:
        st.header("Session")
        st.write(f"**Question:** {st.session_state.question}")
        st.write(f"**Maximum marks:** {st.session_state.max_marks}")
        st.write(f"**Copies:** {total}")
        st.progress(min(len(st.session_state.results) / total, 1.0))
        st.write(f"Confirmed: **{len(st.session_state.results)} / {total}**")
        if st.button("Start a new session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    if idx < total:
        st.subheader(f"2. Copy {idx + 1} of {total}")
        st.caption("You can upload more than one page for the same student's answer. Upload pages in reading order.")

        uploads = st.file_uploader(
            f"Upload photo(s) for copy {idx + 1}",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key=f"uploader_{idx}",
            help="Use clear, well-lit photos. Each upload here belongs to this one student's copy.",
        )
        student_name = st.text_input(
            "Student name / roll number (optional)",
            value=st.session_state.copy_uploads.get(idx, {}).get("student", ""),
            key=f"student_{idx}",
        )
        st.session_state.copy_uploads[idx] = {
            "student": student_name,
            "files": uploads,
        }

        api_key = st.text_input(
            "Gemini API key",
            type="password",
            key="gemini_api_key",
            help="Get an API key from Google AI Studio. It is used only for this app session.",
        )

        if uploads:
            cols = st.columns(min(3, len(uploads)))
            for i, file in enumerate(uploads):
                with cols[i % len(cols)]:
                    st.image(file, caption=f"Page {i + 1}", use_container_width=True)

        if st.button("Check this copy with AI", type="primary",
                     disabled=not uploads or not api_key.strip(),
                     use_container_width=True):
            try:
                with st.spinner("Reading handwriting and evaluating the answer..."):
                    result = analyze_copy(
                        api_key.strip(),
                        st.session_state.question,
                        st.session_state.reference,
                        st.session_state.max_marks,
                        uploads,
                    )
                st.session_state.analysis = result
                st.session_state.analysis_for_index = idx
                st.rerun()
            except Exception as e:
                st.error(f"Could not check this copy: {e}")
                st.info("Check your internet connection and Gemini API key. You can retry.")

        if st.session_state.analysis is not None and st.session_state.analysis_for_index == idx:
            st.divider()
            st.subheader("3. Review and edit AI assessment")
            result = st.session_state.analysis

            st.info(f"AI confidence: {result.get('confidence', 'Not provided')}. Please review before confirming.")
            extracted = st.text_area(
                "Extracted student answer — edit if handwriting was misread",
                value=result.get("extracted_answer", ""),
                height=180,
                key=f"extracted_{idx}",
            )
            marks = st.number_input(
                "Marks awarded",
                min_value=0.0,
                max_value=float(st.session_state.max_marks),
                value=float(result.get("marks", 0)),
                step=0.5,
                key=f"marks_{idx}",
            )
            mistakes_text = st.text_area(
                "Mistakes / missing points (one per line)",
                value="\n".join(result.get("mistakes", [])),
                height=120,
                key=f"mistakes_{idx}",
            )
            strengths_text = st.text_area(
                "Correct points / strengths (one per line)",
                value="\n".join(result.get("strengths", [])),
                height=100,
                key=f"strengths_{idx}",
            )
            feedback = st.text_area(
                "Teacher feedback",
                value=result.get("feedback", ""),
                height=90,
                key=f"feedback_{idx}",
            )

            if st.button("Continue — confirm marks and next copy",
                         type="primary", use_container_width=True):
                st.session_state.results.append({
                    "copy_number": idx + 1,
                    "student": student_name.strip() or f"Copy {idx + 1}",
                    "answer": extracted,
                    "marks": float(marks),
                    "max_marks": st.session_state.max_marks,
                    "mistakes": [x.strip() for x in mistakes_text.splitlines() if x.strip()],
                    "strengths": [x.strip() for x in strengths_text.splitlines() if x.strip()],
                    "feedback": feedback.strip(),
                })
                st.session_state.current_index += 1
                st.session_state.analysis = None
                st.session_state.analysis_for_index = None
                st.rerun()

    else:
        st.balloons()
        st.subheader("✅ All copies checked")
        st.write(f"Confirmed marks for **{len(st.session_state.results)}** copies.")

        rows = []
        for r in st.session_state.results:
            rows.append({
                "Copy": r["copy_number"],
                "Student": r["student"],
                "Marks": r["marks"],
                "Out of": r["max_marks"],
                "Percentage": round((r["marks"] / r["max_marks"]) * 100, 1),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

        csv_lines = ["Copy,Student,Marks,Out of,Percentage,Feedback"]
        for r in st.session_state.results:
            pct = round((r["marks"] / r["max_marks"]) * 100, 1)
            safe_student = '"' + r["student"].replace('"', '""') + '"'
            safe_feedback = '"' + r["feedback"].replace('"', '""') + '"'
            csv_lines.append(f'{r["copy_number"]},{safe_student},{r["marks"]},{r["max_marks"]},{pct},{safe_feedback}')
        st.download_button(
            "Download marks as CSV",
            data="\n".join(csv_lines),
            file_name="answer_checking_results.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )

        with st.expander("View detailed feedback for each copy"):
            for r in st.session_state.results:
                st.markdown(f"**{r['student']} — {r['marks']} / {r['max_marks']}**")
                st.write(r["feedback"])
                if r["mistakes"]:
                    st.write("Mistakes / missing points:", ", ".join(r["mistakes"]))
                if r["strengths"]:
                    st.write("Correct points:", ", ".join(r["strengths"]))
                st.divider()
