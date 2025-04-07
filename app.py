from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()
import gspread
import os
import json
import base64
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Base64 encoded Google credentials
base64_string = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_BASE64')

app = Flask(__name__)
app.secret_key = 'your_secret_key'
CORS(app, resources={r"/*": {"origins": "*"}})

USERNAME = 'admin'
PASSWORD = 'password123'

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if not base64_string:
    raise ValueError("The environment variable 'GOOGLE_APPLICATION_CREDENTIALS_BASE64' is not set")

creds_dict = json.loads(base64.b64decode(base64_string).decode('utf-8'))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

google_sheet_url = "https://docs.google.com/spreadsheets/d/1bHaPVjApOZFDJ3VA7uXitbvgEISsfTOiabMs2pttzNI"
spreadsheet = client.open_by_url(google_sheet_url)
sheet = spreadsheet.worksheet("AttendanceData")
response_sheet = spreadsheet.worksheet("FormResponses")
chapters_sheet = spreadsheet.worksheet("Chapters")

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('attendance_form'))
        else:
            error = 'Invalid credentials. Please try again.'
            return render_template('login.html', error=error)
    return render_template('login.html')

@app.route('/attendance_form')
def attendance_form():
    if 'logged_in' in session and session['logged_in']:
        return render_template('index.html')
    else:
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/get_data')
def get_data():
    try:
        student_records = sheet.get_all_records()

        # Extract dropdown values
        branches = sorted(set(row['Branch'] for row in student_records if row['Branch']))
        teachers = sorted(set(row['Teacher'] for row in student_records if row['Teacher']))
        grades = sorted(set(row['Grade'] for row in student_records if row['Grade']))
        batches = sorted(set(row['Batch'] for row in student_records if row['Batch']))

        # Students for dropdown
        students = [{'studentName': row['Student'], 'batchName': row['Batch']} for row in student_records if row['Student'] and row['Batch']]

        # Grade → Chapter Mapping
        grade_chapter_map = {}
        for row in student_records:
            grade = row['Grade']
            chapter = row['Chapter Name']
            if grade and chapter:
                grade_chapter_map.setdefault(grade, set()).add(chapter)

        # Grade + Chapter → Sub-topic Mapping
        subtopic_map = {}
        for row in student_records:
            key = f"{row['Grade']}|{row['Chapter Name']}"
            subtopic = row['Sub-Topic']
            if row['Grade'] and row['Chapter Name'] and subtopic:
                subtopic_map.setdefault(key, set()).add(subtopic)

        # Convert sets to sorted lists for JSON response
        grade_chapter_map = {grade: sorted(list(chapters)) for grade, chapters in grade_chapter_map.items()}
        subtopic_map = {k: sorted(list(v)) for k, v in subtopic_map.items()}

        return jsonify({
            'branches': branches,
            'teachers': teachers,
            'grades': grades,
            'batches': batches,
            'students': students,
            'gradeChapterMap': grade_chapter_map,
            'subtopicMap': subtopic_map
        })
    except Exception as e:
        print("Error in /get_data:", str(e))
        return jsonify({'error': 'Failed to fetch dropdown data'}), 500

@app.route('/get_chapters', methods=['GET'])
def get_chapters():
    grade = request.args.get('grade')
    subject = request.args.get('subject')
    try:
        all_data = chapters_sheet.get_all_records()
        chapters = [
            row['Chapter'] for row in all_data
            if str(row.get('Grade', '')).strip().lower() == str(grade).strip().lower() and
               str(row.get('Subject', '')).strip().lower() == str(subject).strip().lower()
        ]
        return jsonify({'chapters': chapters})
    except Exception as e:
        print(f'Error in get_chapters: {e}')
        return jsonify({'error': str(e)})

@app.route('/get_batches', methods=['GET'])
def get_batches():
    branch = request.args.get('branch')
    try:
        batches = sorted(list(set([rec['Batch'] for rec in sheet.get_all_records() if rec['Branch'] == branch])))
        return jsonify({'batches': batches})
    except Exception as e:
        print(f"Error in get_batches: {e}")
        return jsonify({'error': str(e)})

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.json
        date = data.get('date', datetime.now().strftime("%d-%b-%y"))
        time = data.get('time', datetime.now().strftime("%H:%M:%S"))

        branch_name = data['branchName']
        batch_name = data['batchName']
        grade = data['grade']
        teacher_name = data['teacherName']
        chapter_name = data['chapterName']
        student_data = data['studentData']
        
        subtopic_name = data['subtopicName']
        comments = data.get('comments', '')

        print("Student Data:", student_data)

        rows_to_add = []
        for student in student_data:
            row = [
                student['studentName'],      # A - Student
                student['present'],          # B - Present/Absent
                grade,                       # C - Grade
                chapter_name,                # D - Chapter Name
                subtopic_name,               # E - Sub-topic
                teacher_name,                # F - Teacher
                branch_name,                 # G - Branch
                batch_name,                  # H - Batch
                date,                        # I - Date
                time,                        # J - Time
                data.get('comments', '')     # K - Comments
            ]
            rows_to_add.append(row)

        print("Submitting rows:", rows_to_add)

        response_sheet.append_rows(rows_to_add)

        # Store recent submissions in session
        session['recent_submissions'] = rows_to_add

        return jsonify({'message': 'Form submitted successfully', 'redirect': url_for('view_submissions')})
    except Exception as e:
        print(f"Error in /submit: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal Server Error'}), 500

@app.route('/view_submissions')
def view_submissions():
    try:
        data = session.pop('recent_submissions', [])
        return render_template('submissions.html', submissions=data)
    except Exception as e:
        print(f"Error in /view_submissions: {e}")
        return "Error loading submissions."

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)