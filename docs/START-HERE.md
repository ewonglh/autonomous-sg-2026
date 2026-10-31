# Start here

## What happens

You describe what you want in plain English. The agent helps build it, then opens a pull request for the team to review. A pull request is a proposed change; it joins the shared project when merged.

## Joining the team from zero

Before starting, do these by hand: sign in to GitHub in your browser, open the cloned folder in your agent app, and get a secrets key from a teammate one-to-one if the project uses one. The repo owner must add you as a collaborator first.

Paste this prompt into your agent app:

```text
I'm joining a hackathon team. I don't code and I'm not sure what's installed on this computer. Please set me up, step by step, in plain English, one step at a time, and wait for me after each step.

The team's repo is: <paste the repo URL here>

Do this:
1. Check whether git, the GitHub CLI (`gh`) and a POSIX shell (`sh`, from Git Bash on Windows) are installed. Tell me what is missing. Before installing anything, tell me what it is and ask me to say yes.
2. I need to sign in to GitHub. Run `gh auth login` for me to see, but I will do the sign-in myself in the browser. Do not ask me for my password, and never type or store any credentials.
3. Check that I can see the repo (`gh repo view <url>`). If not, tell me to ask my teammate to add my GitHub username as a collaborator.
4. Clone the repo to a SHORT path such as C:\hk\<repo-name> on Windows or ~/hk/<repo-name> elsewhere (long paths break git on Windows).
5. Tell me to open that folder in my agent app, and to start a new session there and paste the team's "start of session" prompt. Stop there.

Rules: ask before installing or deleting anything, never ask for passwords or secret keys, and if something fails twice, stop and tell me exactly what to send my teammate.
```

## Every session

Paste this prompt at the start of each session:

```text
I'm a teammate on a hackathon team. I don't write code and I don't know git, so please work with me in plain English. This repo is already set up for the team.

Before anything else:
1. Read AGENTS.md and docs/START-HERE.md, then run `sh scripts/status` (if `sh` is not found, use Git Bash or WSL). Tell me in two or three plain sentences what state the project is in and what matters for me. Do not fix setup problems unless I ask.
2. If I ask for a feature or change, follow docs/INTAKE.md: ask me what I want to see when it works, then show me a short checklist ("I will build... I will not build...") and wait for my yes before you create an issue or write any code. Check first that someone hasn't already built or requested it.
3. Do the work the way the repo says: one branch and one worktree per change, small changes, and open a pull request. Do not merge anything yourself, and never push to main.

Rules for working with me:
- Explain what you did and what I should look at in plain English. No jargon without a one-line explanation.
- Ask before deleting files, discarding changes, or running anything you are not sure about. If I say "always allow" by mistake, still ask me for anything destructive.
- Never ask me for passwords, API keys or secret values, and never print or paste them. If I paste one by accident, tell me to tell a teammate so it can be replaced.
- Do only what I asked. If you have extra ideas, write them down as an idea issue for the team instead of building them.
- If something fails and you can't fix it in a couple of tries, stop and tell me what to ask a teammate. Do not work around a failing check or change the project's scripts or CI to make it pass.

My first request: <describe what you want in your own words>

Final report, 6 lines max: what changed per file, leftovers in files you do not own, doubts.
```

## Rules for everyone

- Never paste passwords, API keys or `.env.keys` into chat, issues or pull requests. If you do by accident, tell a teammate so the key can be replaced.
- If you are stuck for 10 minutes, ask a teammate.
- Never click "always allow" for something you do not understand. Say no to deleting files or discarding work.
- Do not merge unless the reviewer said "Looks good" (if there is a reviewer) and CI is green. If you are unsure, ask a teammate who codes.
