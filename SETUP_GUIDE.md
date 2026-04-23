# Resume Builder — Complete Setup Guide

> This guide assumes you have never set up a Python project before. Follow every step in order and don't skip anything. Choose your operating system below.

---

## What This Tool Does

This is an AI-powered resume builder. You give it a job posting URL and your existing resume, and a team of specialized AI agents rewrites and tailors your resume (and optionally a cover letter) for that specific job. The more you use it, the smarter it gets — it learns your editing preferences over time and applies them automatically.

---

## Choose Your Setup Path

- [I am on a Mac](#setup-for-mac)
- [I am on Windows](#setup-for-windows)

---

---

# Setup for Mac

---

## Step 1 — Get a Claude Subscription

Go to [claude.ai](https://claude.ai) and create an account with a paid plan (Pro or higher). The tool uses Claude AI to do its work, and it runs entirely through your subscription — no extra charges per use.

---

## Step 2 — Install Homebrew (Mac Package Manager)

Homebrew is a tool that makes installing software on Mac much easier. Open the **Terminal** app (press `Cmd + Space`, type "Terminal", press Enter) and paste this command:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Press Enter and follow the on-screen instructions. It will ask for your Mac password — type it and press Enter (you won't see the characters as you type, that's normal).

When it finishes, close the Terminal and open a new one before continuing.

> **Already have Homebrew?** Skip this step.

---

## Step 3 — Install Node.js

In Terminal, run:

```
brew install node
```

Verify it installed correctly:

```
node --version
```

It should show a version number like `v20.11.0`.

---

## Step 4 — Install Claude Code CLI

In Terminal, run:

```
npm install -g @anthropic-ai/claude-code
```

Then log in to Claude Code:

```
claude
```

This opens a browser window. Log in with the same account you use on claude.ai. You will see a code — paste it in the browser when asked. You only need to do this once.

> After logging in, you can close the Terminal session that opened. Claude Code is now authenticated on your Mac.

---

## Step 5 — Install Python

Go to [python.org/downloads](https://python.org/downloads) and download Python 3.10 or higher. Run the installer and follow the default steps.

Verify Python is installed:

```
python3 --version
```

It should show something like `Python 3.11.4`.

> **Note for Mac:** use `python3` and `pip3` instead of `python` and `pip` in all commands below.

---

## Step 6 — Download the Claude Code Desktop App

Go to [claude.ai/download](https://claude.ai/download) and download Claude Code for Mac. Install it by dragging it to your Applications folder.

Open it once to make sure it launches correctly, then close it — you will use it after cloning the project.

---

## Step 7 — Clone the Project

In Terminal, navigate to the folder where you want to save the project. For example, to put it in your Documents:

```
cd ~/Documents
```

Then clone the project:

```
git clone https://github.com/Raitza/resume-builder.git
```

This creates a folder called `resume-builder` inside Documents with all the project files.

---

## Step 8 — Open the Project in Claude Code Desktop

1. Open **Claude Code Desktop** from your Applications folder.
2. Click **Open Folder** (or "Add project") and navigate to the `resume-builder` folder you just cloned.
3. Select it and open it.

You are now inside the project. From this point, Claude Code can guide you through the rest of the setup. Type this in the Claude Code chat:

> *"Help me set up this resume builder project. Install dependencies, and guide me through editing config.py and the candidate profile."*

Claude Code will run `pip3 install -r requirements.txt`, open the files that need editing, and walk you through each one step by step.

---

## What Claude Code Will Help You Configure

Once inside the project, there are two files you must personalize before using the tool:

### `config.py` — Your contact information
Claude Code will open this file and ask you to fill in:
- Your full name
- Your LinkedIn URL
- Your email
- Your phone number
- Your location (City, Country)

### `src/agents/prompts/_candidate_profile.md` — Your professional profile
This tells the AI agents who you are. Claude Code will guide you through each section:
- **Background:** where you are from, languages, work authorization context
- **Experience:** total years, how to frame your seniority
- **Education:** your degree and how to position it
- **Core strengths:** your main skills (only what you can speak to in an interview)
- **Perceived identity:** how you want to be seen by hiring managers

---

## Step 9 — Add Your Files

**Your resume:**
Put your existing resume (`.docx` Word format only — no PDFs) into the `resumes/` folder inside the project.

> Tip: use your most complete resume — all experience, all roles. The AI decides what to include per job.

**Formatting reference:**
Put a `.docx` resume formatted the way you want your outputs to look into `feedback/resume.docx`. This tells the AI your preferred visual style (fonts, margins, heading format). If you skip this, a default style is used.

---

## Step 10 — Run the App

In Claude Code Desktop chat, type:

> *"Run the app"*

Or open Terminal, navigate to the project folder, and run:

```
cd ~/Documents/resume-builder
streamlit run app.py
```

Your browser opens automatically at `http://localhost:8501`. The tool is ready to use.

---

## Mac Quick Start Checklist

- [ ] Claude account with paid plan
- [ ] Homebrew installed
- [ ] Node.js installed (`brew install node`)
- [ ] Claude Code CLI installed (`npm install -g @anthropic-ai/claude-code`)
- [ ] Logged in to Claude Code (`claude` in Terminal → browser login)
- [ ] Python 3.10+ installed
- [ ] Claude Code Desktop app installed
- [ ] Project cloned (`git clone https://github.com/Raitza/resume-builder.git`)
- [ ] Project opened in Claude Code Desktop
- [ ] Dependencies installed (`pip3 install -r requirements.txt`)
- [ ] `config.py` filled with your info
- [ ] `_candidate_profile.md` filled with your profile
- [ ] Your resume `.docx` added to `resumes/`
- [ ] Reference resume added to `feedback/resume.docx`
- [ ] App running (`streamlit run app.py`)

---

---

# Setup for Windows

---

## Step 1 — Get a Claude Subscription

Go to [claude.ai](https://claude.ai) and create an account with a paid plan (Pro or higher). The tool uses Claude AI to do its work, and it runs entirely through your subscription — no extra charges per use.

---

## Step 2 — Install Node.js

Go to [nodejs.org](https://nodejs.org), download the installer, and run it with all default options.

Verify it installed correctly — open **Command Prompt** (press `Win + R`, type `cmd`, press Enter) and run:

```
node --version
```

It should show a version number like `v20.11.0`.

---

## Step 3 — Install Claude Code CLI

In Command Prompt, run:

```
npm install -g @anthropic-ai/claude-code
```

---

## Step 4 — Install Git for Windows

Go to [git-scm.com/downloads/win](https://git-scm.com/downloads/win) and download the installer. Run it with all the default options — do not change anything. This installs Git Bash, which Claude Code requires to run on Windows.

After installing, **close Command Prompt and open a new one** before continuing.

---

## Step 5 — Log In to Claude Code

In Command Prompt, run:

```
claude
```

This opens a browser window. Log in with the same account you use on claude.ai. You will see a code — paste it in the browser when asked. You only need to do this once.

---

## Step 6 — Install Python

Go to [python.org/downloads](https://python.org/downloads) and download Python 3.10 or higher. During installation, **check the box that says "Add Python to PATH"** before clicking Install — this is important.

Verify Python installed correctly:

```
python --version
```

It should show something like `Python 3.11.4`.

---

## Step 7 — Download the Claude Code Desktop App

Go to [claude.ai/download](https://claude.ai/download) and download Claude Code for Windows. Install it and open it once to confirm it launches, then close it.

---

## Step 8 — Clone the Project

Open **Command Prompt** and navigate to where you want to save the project. For example:

```
cd C:\Users\YourName\Documents
```

Then clone the project:

```
git clone https://github.com/Raitza/resume-builder.git
```

This creates a folder called `resume-builder` in Documents with all the project files.

---

## Step 9 — Open the Project in Claude Code Desktop

1. Open **Claude Code Desktop** from the Start menu.
2. Click **Open Folder** and navigate to the `resume-builder` folder you just cloned.
3. Select it and open it.

Type this in the Claude Code chat:

> *"Help me set up this resume builder project. Install dependencies, and guide me through editing config.py and the candidate profile."*

Claude Code will run `pip install -r requirements.txt`, open the files that need editing, and walk you through each one step by step.

---

## What Claude Code Will Help You Configure

### `config.py` — Your contact information
- Your full name
- Your LinkedIn URL
- Your email
- Your phone number
- Your location (City, Country)

### `src/agents/prompts/_candidate_profile.md` — Your professional profile
- **Background:** where you are from, languages, work authorization context
- **Experience:** total years, how to frame your seniority
- **Education:** your degree and how to position it
- **Core strengths:** your main skills
- **Perceived identity:** how you want to be seen by hiring managers

---

## Step 10 — Add Your Files

**Your resume:**
Put your existing resume (`.docx` Word format only — no PDFs) into the `resumes/` folder inside the project.

**Formatting reference:**
Put a `.docx` resume formatted the way you want your outputs to look into `feedback/resume.docx`.

---

## Step 11 — Run the App

In Claude Code Desktop chat, type:

> *"Run the app"*

Or open Command Prompt, navigate to the project folder, and run:

```
cd C:\Users\YourName\Documents\resume-builder
streamlit run app.py
```

Your browser opens automatically at `http://localhost:8501`.

---

## Windows Quick Start Checklist

- [ ] Claude account with paid plan
- [ ] Node.js installed
- [ ] Claude Code CLI installed (`npm install -g @anthropic-ai/claude-code`)
- [ ] Git for Windows installed
- [ ] Logged in to Claude Code (`claude` in Command Prompt → browser login)
- [ ] Python 3.10+ installed (with "Add to PATH" checked)
- [ ] Claude Code Desktop app installed
- [ ] Project cloned (`git clone https://github.com/Raitza/resume-builder.git`)
- [ ] Project opened in Claude Code Desktop
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `config.py` filled with your info
- [ ] `_candidate_profile.md` filled with your profile
- [ ] Your resume `.docx` added to `resumes/`
- [ ] Reference resume added to `feedback/resume.docx`
- [ ] App running (`streamlit run app.py`)

---

---

# How to Use the Tool

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

# How to Train the Tool Over Time

This is where the tool gets smarter. Every time you edit a Claude-generated resume before sending it to an employer, you can feed those edits back in. The tool learns your preferences and applies them automatically in future runs.

**Step 1 — After the tool generates a resume, download it.**
The file goes to the `output/` folder automatically (one subfolder per run, named after the company and role).

**Step 2 — Open the resume in Word and make your edits.**
Change whatever you would change before sending it — rework a bullet, fix the tone, reorder a section. These edits are the training signal.

**Step 3 — Save your edited file with this naming convention:**

`resume_<companytag>.docx`

Examples:
- `resume_giin.docx`
- `resume_mckinsey.docx`

For cover letters: `cover_letter_<companytag>.docx`

**Step 4 — Put the file in the `feedback/` folder.**

**Step 5 — The tool processes this feedback automatically on the next run.**
It compares your edits against what it originally generated, extracts your patterns, and stores them as hard rules in `memory/memory.json`. All future outputs will follow those rules.

### What the tool learns
- Phrases you consistently rewrite or remove
- Tone preferences (more direct, less formal, etc.)
- Bullet point style
- Length preferences
- Formatting choices

### Tips
- Be consistent — applying the same corrections across multiple feedback sessions makes the rules stick faster.
- You do not need to give feedback after every run. Even 3–4 sessions over time make a meaningful difference.

---

# Folder Structure Reference

```
resume-builder/
│
├── app.py                  ← The main app. Run this to start.
├── config.py               ← YOUR personal info goes here
├── requirements.txt        ← Python dependencies
│
├── src/
│   └── agents/
│       └── prompts/
│           ├── _candidate_profile.md   ← YOUR profile goes here
│           └── (other files — do not edit)
│
├── resumes/                ← Put YOUR resume .docx files here
├── feedback/               ← Put YOUR edited resumes here + reference resume.docx
├── profiles/               ← Auto-generated (do not touch)
├── memory/                 ← Auto-generated (do not touch)
└── output/                 ← Generated resumes — download from here
```

**Rule of thumb:** You only ever touch `config.py`, `_candidate_profile.md`, and the `resumes/` and `feedback/` folders. Everything else is managed automatically.

---

# Troubleshooting

**"claude is not recognized" or "claude: command not found"**
1. Close the terminal and open a new one, then try again.
2. If it still fails, run `npm bin -g` to find where npm installed it, then add that folder to your system PATH.
3. On Windows, restart the computer after installing Git and Node.js.

**"Git is required for local sessions" in Claude Code Desktop**
Git is not in the PATH that Claude Code Desktop sees. Close Claude Code Desktop completely and reopen it. If it persists, restart your computer — this resolves it in nearly all cases.

**"streamlit: command not found"**
Run `pip install -r requirements.txt` (Mac: `pip3 install -r requirements.txt`) from inside the project folder.

**The job URL didn't scrape correctly**
Some job boards block automated scrapers. Copy and paste the full job description text directly into the text area below the URL field.

**The resume came out too long**
Normal on the first run. Use the refinement step to ask the tool to shorten it. The tool will remember what to cut for next time.

**The app crashes mid-run**
Restart with `streamlit run app.py` — the tool has session recovery and will offer to restore your last session.

**PDF files are not supported**
Convert to `.docx` first — in Word (File → Open PDF → Save as .docx) or a free online converter.
