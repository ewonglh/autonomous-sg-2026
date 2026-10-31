# Demo and submission

A hackathon is judged on the demo, not the code. Plan the ending from the start.

## Freeze
- **Code freeze:** set a time, for example 2 hours before the deadline (30 minutes for a 6-hour event). Write it in `docs/PROJECT.md`.
- After the freeze only fixes to the demo path are allowed. No new features, no dependency changes.
- Anything unfinished stays behind a flag or off the demo path.

## Known-good tag
When the demo path works end to end on `main` (also at each big milestone):
```sh
git checkout main && git pull --ff-only
sh scripts/install && sh scripts/lint && sh scripts/build && sh scripts/smoke
git tag demo-ok-$(date +%H%M) && git push origin --tags
```
Tag only after `smoke` passes. If anything breaks later, roll back with GitHub's **Revert** button on the merged PR that caused it; this opens a new PR. You can also run the demo from the latest `demo-ok-*` tag.

## Rollback
If `main` breaks near the deadline, use GitHub's **Revert** button on the merged PR that caused the problem. GitHub opens a new PR; have it reviewed and merged. Do not push a direct `git revert` to `main`.

If reverting is not practical in time, run the demo from the latest known-good tag:
```sh
git fetch --tags
git tag -l 'demo-ok-*'          # pick the latest
```
Check out `demo-ok-<time>` to run from that tag. Never force-push `main`.

## Deploy
Decide at kickoff where the demo runs: on a laptop, or hosted. If hosted, write the one command or button here (TODO: filled in at kickoff) and test it once in the first third of the event, not at the end.

## Submission checklist
- [ ] Demo path from `docs/PROJECT.md` runs from a clean checkout (`sh scripts/install && sh scripts/dev`).
- [ ] A second device or browser opens the demo link (if hosted).
- [ ] No real personal data in the demo. Use made-up names and data.
- [ ] README says what it is, how to run it, and who built it.
- [ ] Screenshots or a 60-second screen recording saved, in case the live demo fails.
- [ ] Submission form filled in and submitted before the deadline, by a named person: ______
- [ ] Licence and credits for any third-party code, images or data (check the event rules).
- [ ] Rotate or delete any secret that was shared in chat.
