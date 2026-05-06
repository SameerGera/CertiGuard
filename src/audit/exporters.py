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
            ws.title = "Results"

            ws.append(["Bidder ID", "Bidder Name", "Criterion", "Verdict", "Confidence", "Reason"])

            for bidder in data.get("bidders", []):
                bid = bidder.get("bidder_id", "")
                name = bidder.get("bidder_name", "")
                for crit in bidder.get("criteria_results", []):
                    ws.append([
                        bid,
                        name,
                        crit.get("criterion_id", ""),
                        crit.get("verdict", ""),
                        crit.get("confidence", 0.0),
                        crit.get("reason", "")
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