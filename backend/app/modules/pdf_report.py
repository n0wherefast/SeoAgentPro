from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
import os, json

def generate_pdf_report(path, report: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    story = []

    def add(text):
        story.append(Paragraph(text, styles["Normal"]))
        story.append(Spacer(1, 12))

    add("<b>SEO REPORT</b>")

    for k, v in report.items():
        try:
            if isinstance(v, (dict, list)):
                v = json.dumps(v, indent=2)
            add(f"<b>{k}</b>:<br/>{v}")
        except Exception as e:
            add(f"<b>{k}</b>: ERROR - {e}")

    doc.build(story)
    return path
