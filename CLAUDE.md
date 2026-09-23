# Repo rules — personal project

This is a **personal** repository on a **personal GitHub account** (`satwick07`).
It has nothing to do with any employer. Treat it that way in everything you commit.

## Identity (hard rule)

Every commit here is authored with the personal Gmail identity:

```
Name:  satwick07
Email: satwicknalli@gmail.com
```

- **Never** use a work/employer email address (`*@protium.co.in` or any other company
  domain) as author or committer here.
- **Never** use a work email, work name, work URL, work ticket id, or work hostname in
  commit messages, code, comments, docs, issues or workflow files.
- Before the first commit in a fresh clone, pin the identity locally:

  ```bash
  git config user.name  "satwick07"
  git config user.email "satwicknalli@gmail.com"
  ```

  Do this per-clone rather than relying on the global config, which may be set to a work
  address on a work machine.
- Check before you push:

  ```bash
  git log --format='%an <%ae> | %cn <%ce>' | sort -u
  ```

  If anything other than `satwick07 <satwicknalli@gmail.com>` or the GitHub Actions bot
  (`paradise-watch <noreply@github.com>`) appears, stop and fix the history before pushing.

## Secrets

The Google Chat webhook is a **repo secret** (`GCHAT_WEBHOOK`) or a gitignored `.webhook`
file. It never goes into a tracked file, a commit message, or a log line.

## Everything else

See `README.md` for what this watcher does and how to arm it.
