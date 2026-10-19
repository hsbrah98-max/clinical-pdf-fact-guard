# Quote-Verified Clinical & School Intake Digester

**Author:** Harman Brah, MD

High schools get free depression and anxiety screening, teacher ADHD ratings, and a place for IEP, 504, and testing records. Families who want care choose a child and adolescent psychiatrist. The practice receives the packet already organized and pays a flat listing fee, never a fee per referral.

**Open `snowpine-schools.html`.** It is one file with five screens that pass data to each other live:

1. **Student check-in.** PHQ-A and GAD-7 on a school Chromebook. Only students with parent consent are listed.
2. **Counselor.** Roster with severity, consent tracking, same-day safety alerts, teacher form requests, and record uploads.
3. **Teacher.** The Vanderbilt form, prefilled with the student, feeds back to the counselor when submitted.
4. **Family.** Plain-language results, nearby practices, and per-item consent to share.
5. **Psychiatrist.** Referral inbox and packet. Records the family did not share stay hidden. Gaps that Snowpine itself filled are marked green.

For pitching:

- **▶ Tour** (top right) resets the demo and walks Jordan through all five screens in 13 steps, filling in the forms itself. Use the arrow keys or Next.
- **Counselors** and **Practices** are pitch pages that answer each audience's first objections: after-hours safety alerts, "are you selling my students", liability for a positive screen, and getting flooded with referrals.
- The family directory includes free school, community, and county options, filters by insurance, and sorts by distance only.
- The practice's **Listing settings** (ages, conditions, insurance, weekly cap, pause) decide which referrals it can receive. A practice can decline a referral, and the family goes back to the directory.

Rebuild after changing anything: `python3 build_app.py`. It bakes `samples/summary.model.json` and `teacher-vanderbilt.html` into the app.

## Why practices pay a flat listing, not per lead

- **FERPA:** a school cannot release student results without parent consent.
- **HIPAA:** a practice holding the data cannot sell it.
- **State referral laws:** many states, including California under B&P §650, bar paying per patient referred.
- **PPRA:** screening needs prior written parent consent.

Get healthcare counsel to review this before any practice pays.

> **Synthetic documents only.** `digest.py` calls the local `claude -p` CLI on a consumer account with no BAA. Never run it on a real patient record.

## Files

| File | What it does |
|---|---|
| `digest.py` | Turns IEP, 504, neuropsych, or note PDFs into `summary.html` and `summary.pdf`, plus `summary.model.json` with the raw model output. |
| `teacher-vanderbilt.html` | A single-file teacher form. It scores in the browser, prints a one-page result, and sends nothing anywhere. |
| `app_template.html`, `build_app.py` | The five-screen app source and the build step that produces `snowpine-schools.html`. |
| `make_samples.py` | Builds three fake PDFs for a fictional student in `samples/`. |

## Run

```
python3 make_samples.py
python3 digest.py samples/*_sample.pdf --out samples/summary.html   # about 1 minute
python3 digest.py samples/*_sample.pdf --from-json samples/summary.model.json --out samples/summary.html   # re-render, no model call
```

## How the digester keeps numbers honest

- Every fact carries a verbatim quote and a file and page. If the quote is not found on that page, the fact moves to a red **Unverified** box.
- A score or percentile must appear as a whole number inside its quote, so "10" does not pass for 104.
- Gaps and the suggested letter are the model's own inferences. Any number in them that does not appear in the documents is flagged inline.
- Scanned PDFs with no text layer go to the model as files, and their facts are marked "scan, not checked".

## Teacher form scoring (NICHQ Vanderbilt, Teacher)

A symptom counts when it is rated 2 or 3.

- Inattentive: 6 or more of items 1 to 9.
- Hyperactive: 6 or more of items 10 to 18.
- ODD/CD: 3 or more of items 19 to 28.
- Anxiety/depression: 3 or more of items 29 to 35.
- Impairment: any performance item rated 4 or 5.

The ADHD screen is positive only when the symptom criteria and impairment are both met. Any anxiety or mood item the teacher endorses is surfaced regardless of the ADHD result.

## Before this ships

- **Vanderbilt wording is copyrighted by the AAP and NICHQ.** Commercial use needs a license, or a different scale.
- **School records bring in FERPA as well as HIPAA,** plus parent consent to release. The hosted portal needs a consent step.
- **The model call needs a BAA-covered endpoint.** The site's compliance claims are still unverified.
- The Vanderbilt is normed for ages 6 to 12. For high schoolers, use it as one input and collect from 2 or more teachers.
- A school using this needs a named person who answers same-day safety alerts.
- The app is a front end only. There is no backend, login, or real upload, and state resets on reload.
