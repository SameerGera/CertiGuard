"""PDF report generation."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class ReportSection:
    title: str
    content: str


class ReportGenerator:
    def generate_header(self, tender_id: str, tender_name: str) -> List[ReportSection]:
        return [
            ReportSection("Tender ID", tender_id),
            ReportSection("Tender Name", tender_name),
            ReportSection("Generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") + " UTC")
        ]

    def generate_bidder_section(self, bidder_id: str, bidder_name: str, verdict: str, confidence: float) -> List[ReportSection]:
        color = "GREEN" if verdict == "ELIGIBLE" else "RED" if verdict == "NOT_ELIGIBLE" else "YELLOW"
        return [
            ReportSection("Bidder ID", bidder_id),
            ReportSection("Bidder Name", bidder_name),
            ReportSection("Verdict", f"{verdict} ({color})"),
            ReportSection("Confidence", f"{confidence:.2f}")
        ]

    def generate_criterion_result(self, criterion_id: str, label: str, verdict: str, reason: str) -> List[ReportSection]:
        return [
            ReportSection("Criterion", criterion_id),
            ReportSection("Label", label),
            ReportSection("Result", verdict),
            ReportSection("Reason", reason)
        ]

    def generate_pdf(self, tender_id: str, bidders: List[Dict], output_path: str) -> bool:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet

            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()

            story.append(Paragraph(f"CertiGuard Evaluation Report", styles["Title"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"Tender: {tender_id}", styles["Normal"]))
            story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
            story.append(Spacer(1, 24))

            summary_data = [["Bidder", "Verdict", "Confidence"]]
            for bidder in bidders:
                bidder_name = bidder.get("bidder_name", "Unknown")
                verdict = bidder.get("overall_verdict", "NEEDS_REVIEW")
                confidence = bidder.get("overall_confidence", 0.0)
                summary_data.append([bidder_name, verdict, f"{confidence:.2f}"])

            t = Table(summary_data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(t)
            story.append(Spacer(1, 24))

            for bidder in bidders:
                bidder_name = bidder.get("bidder_name", "Unknown")
                verdict = bidder.get("overall_verdict", "NEEDS_REVIEW")
                confidence = bidder.get("overall_confidence", 0.0)

                story.append(Paragraph(f"Bidder: {bidder_name}", styles["Heading2"]))
                story.append(Paragraph(f"Verdict: {verdict} | Confidence: {confidence:.2f}", styles["Normal"]))
                story.append(Spacer(1, 6))

                for crit in bidder.get("criterion_results", []):
                    crit_id = crit.get("criterion_id", "")
                    crit_label = crit.get("criterion_label", "")
                    crit_verdict = crit.get("verdict", "")
                    reason = crit.get("reason", "")
                    
                    story.append(Paragraph(f"  {crit_id} - {crit_label}: {crit_verdict}", styles["Normal"]))
                    story.append(Paragraph(f"    Reason: {reason}", styles["Normal"]))
                    
                    for flag in crit.get("yellow_flags", []):
                        story.append(Paragraph(f"    ⚠ {flag.get('trigger_type', '')}: {flag.get('reason', '')}", styles["Normal"]))

                story.append(Spacer(1, 18))

            doc.build(story)
            return True
        except Exception as e:
            print(f"PDF generation failed: {e}")
            return False

    def generate_summary(self, results: List[Dict]) -> Dict[str, int]:
        summary = {"eligible": 0, "not_eligible": 0, "needs_review": 0}
        for r in results:
            v = r.get("overall_verdict", "NEEDS_REVIEW").lower()
            if v in summary:
                summary[v] += 1
        return summary


report_generator = ReportGenerator()