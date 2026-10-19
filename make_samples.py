#!/usr/bin/env python3
"""Build three synthetic school documents for one fictional student.

Everything here is invented. These files exist so digest.py can be tested
without touching a real patient record.
"""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table

OUT = Path(__file__).parent / "samples"
STYLES = getSampleStyleSheet()


def build(name, pages):
    story = []
    for i, page in enumerate(pages):
        if i:
            story.append(PageBreak())
        for kind, content in page:
            if kind == "h":
                story.append(Paragraph(content, STYLES["Heading2"]))
            elif kind == "p":
                story.append(Paragraph(content, STYLES["BodyText"]))
            elif kind == "t":
                story.append(Table(content, hAlign="LEFT"))
            story.append(Spacer(1, 6))
    SimpleDocTemplate(str(OUT / name), pagesize=letter).build(story)


IEP = [
    [
        ("h", "Westview Unified School District: Individualized Education Program"),
        ("p", "SYNTHETIC SAMPLE. Fictional student for software testing."),
        ("p", "Student: Jordan Avery Test  |  DOB: 03/14/2011  |  Grade: 10  |  School: Westview High School"),
        ("p", "IEP meeting date: 09/18/2026  |  Next annual review: 09/17/2027  |  Triennial reevaluation due: 09/2028"),
        ("p", "Primary eligibility: Other Health Impairment (OHI). Secondary eligibility: Specific Learning Disability (SLD) in written expression."),
        ("p", "Basis for OHI: outside diagnosis of Attention-Deficit/Hyperactivity Disorder, combined presentation, provided by the family's pediatrician."),
    ],
    [
        ("h", "Present Levels of Performance"),
        ("p", "Teacher report (Ms. Rivera, English 10): Jordan completes about half of independent writing assignments, frequently leaves his seat, and needs repeated redirection during whole-class instruction."),
        ("p", "Parent concern: homework takes over three hours nightly and ends in arguments; Jordan says he is 'stupid at school' and has stopped seeing friends on weekends."),
        ("h", "Services"),
        ("t", [["Service", "Frequency", "Location"],
               ["Specialized academic instruction (writing)", "150 minutes weekly", "Resource room"],
               ["School counseling", "30 minutes monthly", "Counseling office"]]),
        ("h", "Accommodations"),
        ("p", "Extended time (time and a half) on tests and written assignments. Preferential seating near instruction. Chunked assignments with check-ins. Access to word processor for writing tasks."),
    ],
]

PLAN_504 = [
    [
        ("h", "Section 504 Accommodation Plan"),
        ("p", "SYNTHETIC SAMPLE. Fictional student for software testing."),
        ("p", "Student: Jordan Avery Test  |  Grade: 8  |  School: Cedar Ridge Middle School  |  Plan date: 10/02/2024"),
        ("p", "Qualifying condition: ADHD, substantially limiting the major life activities of concentrating and learning."),
        ("p", "Accommodations: preferential seating; movement breaks every 30 minutes; teacher-initiated reminders for homework."),
        ("p", "Note: this plan was superseded when the student entered Westview High School and qualified for an IEP."),
    ],
]

NEUROPSYCH = [
    [
        ("h", "Neuropsychological Evaluation Summary"),
        ("p", "SYNTHETIC SAMPLE. Fictional student for software testing."),
        ("p", "Patient: Jordan Avery Test  |  Age at testing: 15 years 2 months  |  Dates of testing: 05/04/2026 and 05/11/2026"),
        ("p", "Examiner: Dana Okafor, PhD (fictional), Licensed Psychologist"),
        ("h", "Cognitive Testing (WISC-V)"),
        ("t", [["Index", "Standard Score", "Percentile"],
               ["Full Scale IQ (FSIQ)", "104", "61"],
               ["Verbal Comprehension (VCI)", "112", "79"],
               ["Working Memory (WMI)", "86", "18"],
               ["Processing Speed (PSI)", "79", "8"]]),
    ],
    [
        ("h", "Academic Achievement (WIAT-4)"),
        ("t", [["Composite", "Standard Score"],
               ["Written Expression", "81"],
               ["Reading Comprehension", "101"],
               ["Math Problem Solving", "97"]]),
        ("h", "Diagnostic Impressions"),
        ("p", "1. Attention-Deficit/Hyperactivity Disorder, combined presentation. 2. Specific learning disorder with impairment in written expression. 3. Rule out generalized anxiety disorder; parent and self-report elevations warrant follow-up."),
        ("h", "Recommendations"),
        ("p", "Referral to child and adolescent psychiatry for medication evaluation. Extended time and reduced-distraction setting for testing. Assistive technology for writing. Teacher ADHD rating scales should be collected before the psychiatry visit."),
    ],
]

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    build("iep_sample.pdf", IEP)
    build("504_sample.pdf", PLAN_504)
    build("neuropsych_sample.pdf", NEUROPSYCH)
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*_sample.pdf"))))
