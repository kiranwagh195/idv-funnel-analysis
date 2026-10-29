-- Q2. Which document type x device combinations have the weakest OCR success rate?
SELECT
    doc_type,
    device_type,
    SUM(upload_ok)                                   AS uploads,
    ROUND(100.0 * SUM(ocr_ok) / SUM(upload_ok), 1)   AS ocr_success_pct,
    ROUND(100.0 * SUM(approved) / COUNT(*), 1)       AS end_to_end_approval_pct
FROM verification_sessions
GROUP BY doc_type, device_type
HAVING SUM(upload_ok) >= 200
ORDER BY ocr_success_pct ASC;
