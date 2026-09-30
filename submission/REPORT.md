# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:**
- **MSSV:**
- **Lớp:** K4-L3B
- **Repository URL:**
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-<MSSV>`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | CP1 đạt đủ required fields, correlation ID, enrichment và PII scrubbing |
| `validate_dashboard.py` | 6/6 | 6/6 | Dashboard contract giữ đúng sáu panel |
| `pytest` | 22 passed | 25 passed | Bổ sung test CP1 và child observations CP2 |
| Số traces hợp lệ | Chưa có CP2 | 10 request workload đã gửi | Xác nhận số trace hiển thị trong evidence Langfuse `06` |
| Số PII leak | 0 | 0 | Log validator và runtime redaction đều không phát hiện PII |
| Latency P95 / TTFT P95 | — | 1054 ms / 50 ms | Tính trên `response_sent` hiện có trong `data/logs.jsonl` |
| Retrieval success rate | — | 100% | `tool_success=true` trên các response hiện có |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** middleware xóa context cũ, nhận `x-request-id` hoặc sinh `req-<8-hex>`, bind vào structlog context, trả lại qua `x-request-id` và response body.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env`, cùng timestamp, event, latency, TTFT, token, cost và `correlation_id`.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` chạy trước JSONL writer và JSON renderer; scrub đệ quy mọi string trong event/payload. Rule gồm email, phone VN, CCCD và credit card.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100; 61 correlation ID duy nhất, 0 record thiếu enrichment và 0 PII leak; test CP1/PII đạt 4 passed.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** dùng key của project cá nhân trong `.env`, restart API sau khi đổi key và chạy workload 10 request không chứa PII; chụp danh sách trace trong project đó tại `evidence/06-trace-list.png`.
- **Cấu trúc root/retrieval/generation observations:** root `lab-agent-run` chứa child `retrieval` loại `retriever` và `llm-generation` loại `generation`; generation ghi model, input/output tokens và cost.
- **Cách nối trace với log:** `correlation_id` được bind trong middleware, truyền vào `propagate_attributes(metadata=...)` và xuất hiện trong structured log.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** version 1, labels `baseline` và `production`.
- **Version/label candidate:** version 2, label `candidate`.
- **Trace ID của mỗi version:** điền theo trace thực tế sau khi chụp `evidence/08-trace-metadata.png` và `evidence/10-prompt-rollback.png`; không tự tạo ID.
- **Cách promote và rollback `production`:** promote bằng cách chuyển label `production` sang version 2; rollback bằng cách chuyển label `production` về version 1. Lưu ảnh trước/sau tại evidence 10.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** contract `config/dashboard.yaml` có latency/TTFT, traffic, errors/retrieval success, cost, tokens và quality; validator đạt 6/6.
- **SLO và lý do chọn:** 99.5% request thành công với latency <= 3000 ms trong cửa sổ 28 ngày, phù hợp mục tiêu phản hồi nhanh nhưng cho phép một lượng lỗi nhỏ.
- **Cách tính error budget:** `100% - 99.5% = 0.5%`; với 10,000 request, tối đa 50 request được phép không đạt SLO.
- **Ba alert và runbook tương ứng:** `high_latency_p95` (warning, 5m), `elevated_error_rate` (critical, 3m) và `low_retrieval_success` (warning, 5m), đều gửi Slack `#k4-l3b-alerts`; runbook tại `docs/alerts.md`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** dùng observation context manager của Langfuse v4 để tạo child span, đồng thời có fallback no-op để test/local mode không cần credential.
- **Một lỗi/blocker đã gặp:** `LANGFUSE_BASE_URL` cũ trỏ tới hostname không phân giải được và prompt `production` chưa tồn tại.
- **Cách tìm nguyên nhân và xử lý:** kiểm tra kết nối HTTPS, đổi URL về `https://cloud.langfuse.com`, tạo prompt version 1/2 và xác nhận `PROMPT_FALLBACK=False`.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics khoanh vùng triệu chứng; log chọn request bằng `correlation_id`; trace xác định retrieval hoặc generation gây chậm/lỗi.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt version giúp truy nguyên thay đổi; token/cost đo chi phí; SLO định nghĩa mức chấp nhận; rollback giảm tác động khi version mới gây regression.
- **Điều quan trọng nhất đã học:** log và trace phải dùng chung correlation ID nhưng vẫn là hai nguồn evidence khác nhau.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** cần bổ sung screenshot Langfuse/dashboard và điền thông tin cá nhân, repository URL, commit SHA, trace ID thực tế trước khi nộp.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
