# StudyForge

A study assistant that runs entirely in your browser. Paste a study guide, and it will:

- make practice questions (definitions, fill-in-the-blank, lists, and "explain" questions)
- answer your questions with a summary pulled from your own notes
- learn from your feedback so answers get more accurate over time
- keep a separate folder for each class you're taking

No server, no account, no API key, and it's free to host on GitHub Pages.

## Put it on GitHub (about 5 minutes)

1. Go to github.com, sign in, and click **New repository**. Name it `studyforge`, set it to Public, and click **Create repository**.
2. Click **uploading an existing file**, drag in `index.html` and `README.md`, and click **Commit changes**.
3. Open **Settings → Pages**. Under "Branch," choose `main` and `/ (root)`, then click **Save**.
4. After a minute, your app is live at `https://YOUR-USERNAME.github.io/studyforge/`. Bookmark it.

You can also just double-click `index.html` to run it on your computer.

## How to use it

1. **Add a class** in the left sidebar (for example "Biology 101").
2. **Study guides tab:** paste your study guide and click *Add guide and make questions*.
3. **Ask a question tab:** type a question. You get a summary from your notes plus a match score.
   - 👍 tells it that answer was right.
   - 👎 shows other parts of your notes; click *This is better* on the right one.
   - *Write the correct answer* saves your answer, and it will show it for similar questions later.
4. **Practice tab:** flashcard-style review. Grade yourself Again / Hard / Good / Easy. Optionally type your answer first and it will suggest a grade.
5. **Progress tab:** see what's mastered, what you miss most, and what the model has learned.

Notes format tip: lines like `Osmosis: diffusion of water across a membrane` or `The nucleus is ...` produce the best questions. Headings followed by bullet points become list questions.

## How the machine learning works

| Part | Technique | What it does |
|---|---|---|
| Finding answers | TF-IDF vectors + cosine similarity | Matches your question to the most relevant sentences in your notes |
| Summaries | Extractive summarization with term-importance ranking | Picks the key sentences and shows the best one first |
| Learning answers | Relevance feedback (word-to-sentence weights) | Your 👍 / 👎 / "This is better" clicks change how sentences rank for those words |
| Memory | Similarity search over saved answers | Answers you approved or wrote yourself come back for similar questions |
| Better questions | Per-type weights | Removing bad questions lowers that question type's priority for new guides |
| Scheduling | SM-2 spaced repetition | Cards you miss come back sooner; cards you know come back later |

Everything learned is stored per class, so feedback in Biology never affects Chemistry.

## Your data

Data is saved in your browser's local storage on the device you use. To move it to another computer or keep it safe, click **Download backup** and later **Restore from backup**. Clearing your browser data erases it, so download a backup now and then.

## Limits to know about

Answers only come from the notes you paste in; it won't know anything outside them. It picks and summarizes sentences rather than writing new ones, so if your notes are wrong or missing something, the answer will be too. That's also why it stays accurate to what your teacher gave you.
