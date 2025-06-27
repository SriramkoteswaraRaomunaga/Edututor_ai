
import streamlit as st
import json
import os
from datetime import datetime
from core.quiz_generator import generate_quiz
from model_setup import load_model_and_tokenizer
from dotenv import load_dotenv
import torch
import pandas as pd
import plotly.express as px
from collections import defaultdict

if not hasattr(torch.classes, "__path__"):
    torch.classes.__path__ = []

USERS_FILE = "users.json"
RESULTS_FILE = "quiz_results.json"

load_dotenv()

def load_data(file_path, default={}):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return default

def save_data(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f)

users = load_data(USERS_FILE)
results = load_data(RESULTS_FILE)

# --- SESSION INITIALIZATION ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.session_state.model = None
    st.session_state.tokenizer = None
    st.session_state.device = None

# --- LOGIN AND REGISTRATION ---
if not st.session_state.logged_in:
    st.set_page_config(page_title="EduTutor AI", layout="centered")
    st.title("EduTutor AI: Personalized Learning with Generative AI")
    tabs = st.tabs(["Login", "Register"])

    with tabs[0]:
        st.subheader("Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        role = st.selectbox("Role", ["student", "educator"], key="login_role")
        if st.button("Login"):
            if username in users and users[username]["password"] == password:
                actual_role = users[username]["role"]
                if role != actual_role:
                    st.error(f"❌ You are registered as a {actual_role}. Please choose the correct role.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    st.session_state.role = actual_role
                    st.rerun()
            else:
                st.error("❌ Invalid username or password")

    with tabs[1]:
        st.subheader("Register")
        new_username = st.text_input("New Username", key="reg_user")
        new_password = st.text_input("Password", type="password", key="reg_pass")
        new_email = st.text_input("Email (optional)", key="reg_email")
        new_college = st.text_input("College / School Name", key="reg_college")
        reg_role = st.selectbox("Role", ["student", "educator"], key="reg_role")
        if st.button("Register"):
            if new_username not in users:
                users[new_username] = {
                    "password": new_password,
                    "role": reg_role,
                    "library": []
                }
                save_data(USERS_FILE, users)
                st.success(f"✅ Registered {new_username} as {reg_role}")
            else:
                st.error("⚠️ Username already exists")

# --- LOGGED-IN VIEW ---
else:
    st.sidebar.title("Menu")
    if st.session_state.role == "student":
        page = st.sidebar.selectbox("Go to", [
            "Dashboard", "Learning Modules", "Quiz", "Quiz History", "My Library"
        ])
    else:
        page = st.sidebar.selectbox("Go to", [
            "Dashboard", "Student Data", "Learning Modules"
        ])

    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # --- STUDENT PAGES ---
    if st.session_state.role == "student":
        if page == "Dashboard":
            user = st.session_state.user
            info = users.get(user, {})
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"- **Name**: {user}")
                st.markdown(f"- **Role**: `{info.get('role', 'N/A')}`")
                count = sum(1 for r in results.values() if r.get("user_id") == user)
                st.markdown(f"- **Quizzes attended**: `{count}`")

        elif page == "Quiz":
            if st.session_state.model is None:
                with st.spinner("Loading model..."):
                    st.session_state.model, st.session_state.tokenizer, st.session_state.device = load_model_and_tokenizer()

            st.header("📘 Generate a Quiz")
            default_topic = st.session_state.get("prefill_topic", "")
            text_input = st.text_input("Enter Topic or Text for Quiz", value=default_topic)
            if "prefill_topic" in st.session_state:
                del st.session_state.prefill_topic
            level = st.selectbox("Select Level", ["easy", "medium", "hard"])

            if "quiz" not in st.session_state:
                st.session_state.quiz = None
            if "answers" not in st.session_state:
                st.session_state.answers = {}

            if st.button("Generate Quiz"):
                if text_input.strip():
                    with st.spinner("Generating quiz..."):
                        quiz = generate_quiz(
                            text_input,
                            level,
                            st.session_state.model,
                            st.session_state.tokenizer,
                            st.session_state.device
                        )
                        st.session_state.quiz = quiz
                        st.session_state.answers = {}
                        st.success("✅ Quiz generated successfully!")
                else:
                    st.warning("⚠️ Please enter a topic.")

            if st.session_state.quiz:
                st.subheader("📝 Take the Quiz")
                with st.form("quiz_form"):
                    for i, q in enumerate(st.session_state.quiz):
                        st.write(f"**Q{i+1}: {q['question']}**")
                        st.session_state.answers[str(i)] = st.radio(
                            label="Choose your answer:",
                            options=q["options"],
                            key=f"answer_{i}"
                        )
                    submitted = st.form_submit_button("Submit")

                if submitted:
                    score = 0
                    st.subheader("📊 Quiz Results")
                    for i, q in enumerate(st.session_state.quiz):
                        user_ans = st.session_state.answers.get(str(i))
                        correct_ans = q["answer"]
                        is_correct = user_ans == correct_ans
                        if is_correct:
                            score += 1
                        st.markdown(f"**Q{i+1}: {q['question']}**")
                        st.write(f"Your Answer: {user_ans}")
                        st.write(f"✅ Correct Answer: {correct_ans}")
                        st.success("Correct!" if is_correct else "Incorrect.")

                    st.info(f"🏁 Final Score: {score} / {len(st.session_state.quiz)}")

                    quiz_id = f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    results[quiz_id] = {
                        "user_id": st.session_state.user,
                        "quiz_id": quiz_id,
                        "topic": text_input,
                        "score": score,
                        "total": len(st.session_state.quiz),
                        "timestamp": datetime.now().isoformat()
                    }
                    save_data(RESULTS_FILE, results)

                    st.session_state.quiz = None
                    st.session_state.answers = {}

        elif page == "Learning Modules":
            st.header("📚 Learning Module")
            topic = st.text_input("Enter a topic to learn about:")

            if "learning_response" not in st.session_state:
                st.session_state.learning_response = None

            if st.button("Get Learning Content"):
                if topic.strip():
                    with st.spinner("🔍 Generating learning content..."):
                        #learning modules
                        prompt = f"Write a short explanation or introduction (8-9 sentences) about '{topic}' suitable for students."
                        model, tokenizer, device = load_model_and_tokenizer()
                        inputs = tokenizer(prompt, return_tensors="pt").to(device)
                        output = model.generate(**inputs, max_new_tokens=200, do_sample=True, temperature=0.7)
                        response = tokenizer.decode(output[0], skip_special_tokens=True)
                        st.session_state.learning_response = response
                else:
                    st.warning("⚠️ Please enter a topic first.")

            if st.session_state.learning_response:
                st.markdown("### 📖 Learning Content:")
                st.write(st.session_state.learning_response)
                if st.button("📌 Save to My Library"):
                    user = st.session_state.user
                    if "library" not in users[user]:
                        users[user]["library"] = []
                    users[user]["library"].append({
                        "topic": topic,
                        "content": st.session_state.learning_response
                    })
                    save_data(USERS_FILE, users)
                    st.success("✅ Module saved to your library!")

        elif page == "My Library":
            st.header("📚 My Saved Learning Modules")
            user = st.session_state.user
            library = users.get(user, {}).get("library", [])
            if library:
                for idx, entry in enumerate(library):
                    with st.expander(f"📘 {entry['topic']}"):
                        st.write(entry["content"])
                        if st.button("🗑️ Remove from Library", key=f"delete_{idx}"):
                            del users[user]["library"][idx]
                            save_data(USERS_FILE, users)
                            st.success("✅ Removed from your library.")
                            st.experimental_rerun()
            else:
                st.info("You haven't saved any modules yet.")

        elif page == "Quiz History":
            st.header("📜 Your Quiz History")
            user_history = [r for r in results.values() if r["user_id"] == st.session_state.user]
            topic_map = defaultdict(list)
            for r in user_history:
                topic_map[r["topic"]].append(r)

            if user_history:
                for topic, quizzes in topic_map.items():
                    with st.expander(f"📘 Topic: {topic} ({len(quizzes)} attempts)"):
                        st.markdown(f"**Total Attempts**: `{len(quizzes)}`")
                        for q in quizzes:
                            st.markdown(f"- 📝 **Quiz ID**: `{q['quiz_id']}` | Score: **{q['score']}/{q['total']}** | 🕒 {q['timestamp']}")
                        if st.button(f"🔁 Retake Quiz on '{topic}'", key=f"retake_{topic}"):
                            st.session_state.page = "Quiz"
                            st.session_state.prefill_topic = topic
                            st.experimental_rerun()
            else:
                st.info("You haven't taken any quizzes yet.")

    # --- EDUCATOR PAGES ---
    elif st.session_state.role == "educator":
        if page == "Dashboard":
            info = users.get(st.session_state.user, {})
            st.write(f"Welcome, {st.session_state.user} 👋")
            st.write("### 🧑‍🏫 Educator Dashboard Summary")

            df = pd.DataFrame(results.values())
            if not df.empty:
                st.subheader("📊 Quizzes Taken Per Student")
                quiz_counts = df['user_id'].value_counts().reset_index()
                quiz_counts.columns = ['Student', 'Quizzes Taken']
                bar_fig = px.bar(quiz_counts, x='Student', y='Quizzes Taken', color='Student')
                st.plotly_chart(bar_fig, use_container_width=True)

                st.subheader("🥧 Average Score Distribution")
                df["percentage"] = (df["score"] / df["total"]) * 100
                avg_scores = df.groupby("user_id")["percentage"].mean().reset_index()
                avg_scores.columns = ["Student", "Average Score (%)"]
                pie_fig = px.pie(avg_scores, names="Student", values="Average Score (%)")
                st.plotly_chart(pie_fig, use_container_width=True)
            else:
                st.info("No quiz data available yet.")

        elif page == "Student Data":
            st.write("### Student Quiz Data")
            student_quiz_map = defaultdict(list)
            for r in results.values():
                student_quiz_map[r["user_id"]].append(r)

            if student_quiz_map:
                for user_id, quizzes in student_quiz_map.items():
                    with st.expander(f"👤 {user_id} - {len(quizzes)} quizzes"):
                        st.markdown(f"**Total Quizzes Attempted**: `{len(quizzes)}`")
                        quiz_data = [{
                            "Quiz ID": q['quiz_id'],
                            "Topic": q['topic'],
                            "Score": f"{q['score']}/{q['total']}",
                            "Timestamp": q['timestamp']
                        } for q in quizzes]
                        df = pd.DataFrame(quiz_data)
                        st.dataframe(df, use_container_width=True)
            else:
                st.write("No student quiz data available.")

        elif page == "Learning Modules":
            st.text_input("Search Modules", placeholder="Enter topic to search...")
            with st.expander("Educator Learning Modules"):
                st.write("Educator learning modules placeholder.")



 
