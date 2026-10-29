-- Q4. Did a specific app release hurt the face-match step? (compare step conversion by version)
SELECT
    app_version,
    SUM(ocr_ok)                                    AS reached_face_step,
    ROUND(100.0 * SUM(face_ok) / SUM(ocr_ok), 1)   AS face_match_pass_pct
FROM verification_sessions
WHERE device_type <> 'Web'
GROUP BY app_version
ORDER BY app_version;
