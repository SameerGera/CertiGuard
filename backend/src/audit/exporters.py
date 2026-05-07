"""Export utilities."""

import json
import zipfile
from typing import List, Dict, Any
from pathlib import Path


class Exporters:
    def export_json(self, data: Dict, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"JSON export failed: {e}")
            return False

    def export_xlsx(self, data: Dict, output_path: str) -> bool:
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Summary"

            ws.append(["Bidder ID", "Bidder Name", "Overall Verdict", "Confidence", "Verdict Reason"])

            for bidder in data.get("bidders", []):
                ws.append([
                    bidder.get("bidder_id", ""),
                    bidder.get("bidder_name", ""),
                    bidder.get("overall_verdict", ""),
                    bidder.get("overall_confidence", 0.0),
                    bidder.get("verdict_reason", "")
                ])

            ws.append([])
            ws.append(["Criterion Results"])
            ws.append(["Bidder", "Criterion ID", "Criterion Label", "Verdict", "AI Confidence", "Reason"])

            for bidder in data.get("bidders", []):
                bid = bidder.get("bidder_name", bidder.get("bidder_id", ""))
                for crit in bidder.get("criterion_results", []):
                    ws.append([
                        bid,
                        crit.get("criterion_id", ""),
                        crit.get("criterion_label", ""),
                        crit.get("verdict", ""),
                        crit.get("ai_confidence", 0.0),
                        crit.get("reason", "")
                    ])

            ws.append([])
            ws.append(["Yellow Flags"])
            ws.append(["Bidder", "Criterion", "Trigger Type", "Reason"])

            for bidder in data.get("bidders", []):
                bid = bidder.get("bidder_name", bidder.get("bidder_id", ""))
                for crit in bidder.get("criterion_results", []):
                    for flag in crit.get("yellow_flags", []):
                        ws.append([
                            bid,
                            crit.get("criterion_id", ""),
                            flag.get("trigger_type", ""),
                            flag.get("reason", "")
                        ])

            wb.save(output_path)
            return True
        except Exception as e:
            print(f"XLSX export failed: {e}")
            return False

    def export_zip(self, file_list: List[str], output_path: str) -> bool:
        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in file_list:
                    zf.write(f, Path(f).name)
            return True
        except Exception as e:
            print(f"ZIP export failed: {e}")
            return False

    def export_all(self, data: Dict, output_dir: str, tender_id: str) -> Dict[str, str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        base = f"{output_dir}/{tender_id}"

        if self.export_json(data, f"{base}.json"):
            results["json"] = f"{base}.json"

        if self.export_xlsx(data, f"{base}.xlsx"):
            results["xlsx"] = f"{base}.xlsx"

        pdf_path = f"{base}.pdf"
        from .report_generator import report_generator
        if report_generator.generate_pdf(data.get("tender_id", tender_id), data.get("bidders", []), pdf_path):
            results["pdf"] = pdf_path

        return results


exporters = Exporters()