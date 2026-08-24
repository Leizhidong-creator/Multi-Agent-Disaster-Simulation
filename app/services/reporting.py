from app.models.schemas import ReportComparison, ReportItem, ReportResponse
from app.services.data_loader import load_fire_code_chunks


class ReportingService:
    def __init__(self) -> None:
        self.fire_code = load_fire_code_chunks()

    def build_report(
        self,
        *,
        scenario: str,
        before_peak_density: float,
        after_peak_density: float,
    ) -> ReportResponse:
        items = self._select_relevant_items()
        reduction_ratio = 0.0
        if before_peak_density > 0:
            reduction_ratio = max(0.0, (before_peak_density - after_peak_density) / before_peak_density)

        verdict = "整改有效，已明显降低核心死角的人流对冲风险。"
        if after_peak_density >= 5:
            verdict = "整改后风险有所下降，但仍需继续优化疏散组织。"

        findings = [
            f"事故回溯场景峰值密度达到 {before_peak_density:.2f} 人/平方米，已跨越临界危险阈值。",
            f"加入虚拟护栏后二次验证峰值密度下降至 {after_peak_density:.2f} 人/平方米。",
            "热力图由中心深红转向黄绿，说明对冲人流被有效拆解。",
            "当前整改建议以疏散净宽度、导流与物理隔离措施为核心。",
        ]

        risk_statement = (
            "系统判断当前场景属于高密度人员聚集风险，"
            "其宏观表现为中心窄巷热力飙红，微观表现为双向对冲和局部受力锁死。"
        )

        return ReportResponse(
            scenario=scenario,
            title="梨泰院场景整改诊断报告",
            risk_statement=risk_statement,
            findings=findings,
            code_references=items,
            comparison=ReportComparison(
                before_peak_density=round(before_peak_density, 2),
                after_peak_density=round(after_peak_density, 2),
                reduction_ratio=round(reduction_ratio, 2),
                verdict=verdict,
            ),
        )

    def _select_relevant_items(self) -> list[ReportItem]:
        selected_ids = {"GB50016-CH-003", "GB50016-CH-004", "GB50016-CH-011", "GB50016-CH-015"}
        items: list[ReportItem] = []
        for chunk in self.fire_code["document_chunks"]:
            if chunk["chunk_id"] not in selected_ids:
                continue
            items.append(
                ReportItem(
                    title=chunk["title"],
                    article=chunk["article"],
                    reason=self._reason_for_chunk(chunk["chunk_id"]),
                    recommendation=self._recommendation_for_chunk(chunk["chunk_id"]),
                )
            )
        return items

    def _reason_for_chunk(self, chunk_id: str) -> str:
        reasons = {
            "GB50016-CH-003": "核心场景属于人员密集型通道，疏散门与走道净宽度不足会直接放大瓶颈效应。",
            "GB50016-CH-004": "事故场景存在人员密集公共场所的典型特征，需要保证通向宽敞地带的疏散通道能力。",
            "GB50016-CH-011": "双向对冲条件下，栏杆扶手或物理隔离是切断横向受力传递的有效措施。",
            "GB50016-CH-015": "疏散距离与直接通向室外的能力影响个体是否在高压区持续滞留。",
        }
        return reasons[chunk_id]

    def _recommendation_for_chunk(self, chunk_id: str) -> str:
        recommendations = {
            "GB50016-CH-003": "对瓶颈入口进行净宽度校核，并在展示中标记现有通道不足。",
            "GB50016-CH-004": "在核心拥堵区外设置强制导流口，保证疏散通道直达宽敞区域。",
            "GB50016-CH-011": "沿巷道中心增设虚拟护栏，将双向人流拆分为两股单向流。",
            "GB50016-CH-015": "缩短高密度区域到安全出口的有效疏散路径，避免持续叠压。",
        }
        return recommendations[chunk_id]


reporting_service = ReportingService()
