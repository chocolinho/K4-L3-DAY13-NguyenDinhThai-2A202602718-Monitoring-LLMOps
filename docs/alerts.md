# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1 — High latency P95

- Tên: `high_latency_p95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: P95 `response_sent.latency_ms`, mục tiêu <= 3000 ms
- Điều kiện: `p95(response_sent.latency_ms) > 3000` trong 5 phút
- Ảnh hưởng: người dùng chờ lâu trước khi nhận câu trả lời.
- Kiểm tra: xác nhận panel latency; lọc `data/logs.jsonl` theo `latency_ms`; mở trace cùng `correlation_id` và so sánh retrieval/generation.
- Mitigation: giảm tải practice scenario, rollback prompt nếu generation tăng, hoặc khôi phục cấu hình gây latency.
- Owner: `student-on-call`

## Alert 2 — Elevated error rate

- Tên: `elevated_error_rate`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: request success và error budget 0.5%
- Điều kiện: `error_rate_pct > 2` trong 3 phút
- Ảnh hưởng: request có thể trả lỗi hoặc không hoàn thành.
- Kiểm tra: xác nhận panel errors; nhóm log `request_failed` theo `error_type`; lấy `correlation_id` và mở trace lỗi.
- Mitigation: tắt incident practice đang bật, khôi phục dependency/configuration, rồi chạy smoke test.
- Owner: `student-on-call`

## Alert 3 — Low retrieval success

- Tên: `low_retrieval_success`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: retrieval success rate >= 90%
- Điều kiện: `retrieval_success_rate_pct < 90` trong 5 phút
- Ảnh hưởng: câu trả lời dễ rơi vào fallback hoặc thiếu context.
- Kiểm tra: xác nhận panel errors/retrieval; lọc `tool_success=false`; mở trace và kiểm tra observation `retrieval`.
- Mitigation: kiểm tra vector store/retriever, giảm tải hoặc rollback cấu hình retrieval, sau đó xác nhận `tool_success` trở lại true.
- Owner: `student-on-call`
