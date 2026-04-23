# Resume Builder — Complete Setup Guide

> This guide assumes you have never set up a Python project before. Follow every step in order and don't skip anything.

---

## What This Tool Does

This is an AI-powered resume builder. You give it a job posting URL and your existing resume, and a team of specialized AI agents rewrites and tailors your resume (and optionally a cover letter) for that specific job. The more you use it, the smarter it gets — it learns your editing preferences over time and applies them automatically.

---

## What You Need Before You Start

You need three things installed on your computer:

### 1. A Claude subscription
Go to [claude.ai](https://claude.ai) and create an account with a paid plan (Pro or higher). The tool uses Claude AI to do its work, and it runs entirely through your subscription — no extra charges per use.

### 2. Claude Code CLI
Claude Code is a command-line tool made by Anthropic. Open a terminal and run:

```
npm install -g @anthropic-ai/claude-code
```

> **Don't have npm?** You need to install Node.js first. Go to [nodejs.org](https://nodejs.org), download the installer, run it, then come back and run the command above.

After installing, log in to Claude Code by running:

```
claude
```

It will open a browser window. Log in with the same account you use on claude.ai. You only need to do this once.

### 3. Python
Go to [python.org/downloads](https://python.org/downloads) and download Python 3.10 or higher. During installation, **make sure to check the box that says "Add Python to PATH"** before clicking Install.

To verify Python installed correctly, open a terminal and run:
```
python --version
```
It should show a version number like `Python 3.11.4`.

---

## Step 1 — Download the Project

Download or clone this repository to a folder on your computer. For example:

```
C:\Users\YourName\resume_builder
```

or on Mac:

```
/Users/YourName/resume_builder
```

---

## Step 2 — Install Dependencies

Open a terminal, navigate to the project folder, and run:

```
pip install -r requirements.txt
```

This installs all the Python libraries the tool needs. It may take a minute or two. Wait for it to finish.

---

## Step 3 — Fill In Your Personal Information

Open the file `config.py` in any text editor (Notepad, VS Code, TextEdit, anything).

You will see this:

```python
CANDIDATE_NAME          = "Your Full Name"
CANDIDATE_LINKEDIN_URL  = "https://www.linkedin.com/in/your-profile/"
CANDIDATE_EMAIL         = "your.email@example.com"
CANDIDATE_PHONE         = "+1 (555) 000 0000"
CANDIDATE_LOCATION      = "City, Country"
```

Replace each value with your real information. For example:

```python
CANDIDATE_NAME          = "Jane Smith"
CANDIDATE_LINKEDIN_URL  = "https://www.linkedin.com/in/jane-smith-123/"
CANDIDATE_EMAIL         = "jane.smith@gmail.com"
CANDIDATE_PHONE         = "+1 (212) 555 7890"
CANDIDATE_LOCATION      = "New York, USA"
```

Save the file.

> **Important:** Keep the quotes around each value. Do not remove them.

---

## Step 4 — Write Your Candidate Profile

Open the file `src/agents/prompts/_candidate_profile.md` in a text editor.

This file tells the AI agents who you are. It is the most important piece of "training" you will do. The agents read this every single time they work on your resume.

Replace the placeholder text with honest, specific information about yourself. Here is what each section means and what to write:

---

**Background:**
Where you are from, what languages you speak, and any relevant context about your work authorization or location. Be specific. For example:
> *Latin American professional, fluent in English and Spanish, currently based in New York on a work visa.*

---

**Experience:**
How many total years of professional experience you have. Also write a note about how to frame your seniority — for example, whether you want to be positioned as senior, mid-level, or let the role determine it. For example:
> *8 years total. Frame seniority based on the target role — do not default to a fixed level.*

---

**Education:**
Your highest degree and how you want it positioned. For example:
> *Master's degree in Public Policy. Position it as a differentiator when the role values analytical rigor or research skills.*

---

**Core strengths:**
List your main skills separated by commas. Be honest — only list things you can actually speak to in an interview. For example:
> *Financial modeling, data visualization, strategy and advisory, stakeholder management, policy analysis, KPI frameworks.*

---

**Perceived identity:**
How you want hiring managers to see you. What is your personal brand? For example:
> *Impact-driven strategic thinker with a data-driven approach. Adapt the dominant angle to what each specific role demands.*

---

Do not change or delete the last two lines of the file — they are instructions for the AI and should stay as-is.

Save the file.

---

## Step 5 — Add Your Resume

Put your existing resume (in `.docx` format — Word document) into the `resumes/` folder.

This is the file the AI will use as the source of truth for your experience and achievements. The agents will never invent credentials — they reframe and tailor what is already in your resume.

> **Important:** The file must be a `.docx` Word document. PDF files will not work.

> **Tip:** Put your most complete resume here — all your experience, all your roles. The AI will decide what to include or leave out depending on each job. You can always add multiple resume versions.

---

## Step 6 — Add a Reference Resume for Formatting

This step is for formatting only — it tells the AI what your resume should look like visually.

Put a `.docx` file named exactly `resume.docx` inside the `feedback/` folder:

```
feedback/resume.docx
```

This should be a resume formatted exactly the way you want all your outputs to look — your preferred font, margins, heading style, etc. It can be your current resume or a template you like.

> If you skip this step, the tool will use a default formatting style.

---

## Step 7 — Run the App

Open a terminal, navigate to the project folder, and run:

```
streamlit run app.py
```

Your browser will open automatically with the app at `http://localhost:8501`.

If the browser does not open automatically, open it yourself and go to that address.

---

## How to Use the Tool

### Basic workflow

1. **Paste a job posting URL** into the URL field. The tool will scrape the job description automatically.
   - If the URL doesn't work (some job boards block scrapers), paste the full job description text directly into the text box below the URL field.

2. **Select your resume file** from the dropdown. It will show the files you put in the `resumes/` folder.

3. **Choose whether to generate a cover letter** (Yes or No radio button).

4. **Click "Analyze & Build"** and wait. The pipeline runs several AI agents in sequence. It usually takes 3–6 minutes for a full run.

5. **Review the Strategy** — after the first phase, the tool shows you the strategic plan before writing anything. You can approve it or ask for changes.

6. **Review the Drafts** — after writing, you see the resume (and cover letter if requested). You can ask the AI to refine specific sections.

7. **Download your files** — when done, download the `.docx` files from the final screen.

### Application Questions tab

If the job has essay questions or application form prompts (common on foundation or nonprofit applications), click the **App Questions** tab and paste them in. The AI will write tailored answers using the same strategy as your resume.

---

## How to Train the Tool Over Time

This is where the tool gets smarter. Every time you edit a Claude-generated resume before sending it to an employer, you can feed those edits back in. The tool learns your preferences and applies them automatically in future runs.

### Step-by-step

**Step 1 — After the tool generates a resume, download it.**

The file goes to the `output/` folder automatically (one subfolder per run, named after the company and role).

**Step 2 — Open the resume in Word and make your edits.**

Change whatever you would change before actually sending it — rework a bullet, reorder a section, fix the tone of the summary, etc. These edits are the training signal.

**Step 3 — Save your edited file with a specific naming convention.**

Name it: `resume_<companytag>.docx`

Where `<companytag>` is a short identifier for the company. Examples:
- `resume_giin.docx`
- `resume_mckinsey.docx`
- `resume_hewlett.docx`

For cover letters: `cover_letter_<companytag>.docx`

**Step 4 — Put the file in the `feedback/` folder.**

```
feedback/resume_giin.docx
feedback/cover_letter_giin.docx
```

**Step 5 — The tool will process this feedback on the next run automatically.**

The Feedback Analyst agent compares your edited version against what it originally generated, extracts the patterns (what you changed, what style choices you made), and stores them in `memory/memory.json`.

From that point on, all future resumes and cover letters will follow those patterns as hard rules.

### What the tool learns

- Phrases or structures you consistently remove or rewrite
- Tone adjustments (more direct, less formal, etc.)
- Bullet point style preferences
- Length preferences (cutting certain sections, adding detail elsewhere)
- Formatting choices

### Tips for good feedback

- **Be consistent.** If you always remove a certain type of filler phrase, removing it every time you give feedback makes the rule stick faster.
- **Only give feedback on things you actually want to change.** If you accepted something as-is, that is also a signal.
- **You do not need to give feedback after every run.** Even feedback from 3–4 runs over time will meaningfully improve the output.

---

## Folder Structure Reference

```
resume_builder/
│
├── app.py                  ← The main app. Run this to start.
├── main.py                 ← Pipeline entry point (runs without the UI)
├── config.py               ← YOUR personal info goes here
├── requirements.txt        ← Python dependencies
│
├── src/
│   ├── agents/
│   │   ├── prompts/
│   │   │   ├── _candidate_profile.md   ← YOUR profile goes here
│   │   │   └── (other prompt files — do not edit these)
│   │   └── (agent files — do not edit these)
│   └── (other source files — do not edit these)
│
├── resumes/                ← Put YOUR resume .docx files here
├── feedback/               ← Put YOUR edited resumes here (for training)
│                              Also put reference resume.docx here
├── profiles/               ← Auto-generated job profiles (do not touch)
├── memory/                 ← Auto-generated memory files (do not touch)
└── output/                 ← Auto-generated resume outputs (download from here)
```

**Rule of thumb:** You only ever touch two files (`config.py` and `_candidate_profile.md`) and two folders (`resumes/` and `feedback/`). Everything else is managed by the tool.

---

## Troubleshooting

**"claude: command not found"**
Claude Code CLI is not installed or not in your PATH. Re-run `npm install -g @anthropic-ai/claude-code` and make sure Node.js is installed first.

**"streamlit: command not found"**
Run `pip install -r requirements.txt` again. Make sure you are in the project folder when you run it.

**The job URL didn't scrape correctly**
Some job boards (LinkedIn, Greenhouse, Lever) block automated scrapers. If the URL fails, copy and paste the full job description text directly into the text area below the URL field.

**The resume came out too long**
This is normal on the first run. Use the refinement step to ask the tool to shorten it. Give it feedback on what to cut — it will remember for next time.

**The app crashes mid-run**
Restart the app (`streamlit run app.py`) — it has session recovery built in and will offer to restore your last session.

**PDF files are not supported**
The feedback system only reads `.docx` Word documents. Convert any PDF to `.docx` before placing it in the `resumes/` or `feedback/` folders. You can do this in Word (File → Open the PDF → Save as .docx) or using a free online converter.

---

## Quick Start Checklist

- [ ] Claude account with paid plan
- [ ] Claude Code CLI installed (`npm install -g @anthropic-ai/claude-code`)
- [ ] Logged in to Claude Code (`claude` in terminal → browser login)
- [ ] Python 3.10+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `config.py` filled with your info
- [ ] `src/agents/prompts/_candidate_profile.md` filled with your profile
- [ ] Your resume `.docx` added to `resumes/`
- [ ] Reference resume added to `feedback/resume.docx`
- [ ] App running (`streamlit run app.py`)
