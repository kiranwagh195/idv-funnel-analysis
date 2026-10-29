-- Q5. (PostgreSQL) Latency benchmark per document type: p50 / p95 / share of calls above an SLA.
-- The Python pipeline computes the same table with pandas because SQLite has no PERCENTILE_CONT.
SELECT
    doc_type,
    COUNT(*)                                                            AS calls,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ocr_latency_ms)) AS p50_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ocr_latency_ms)) AS p95_ms,
    ROUND(100.0 * AVG(CASE WHEN ocr_latency_ms > 3000 THEN 1 ELSE 0 END), 1) AS pct_over_3s
FROM verification_sessions
WHERE ocr_latency_ms IS NOT NULL
GROUP BY doc_type
ORDER BY p95_ms DESC;
