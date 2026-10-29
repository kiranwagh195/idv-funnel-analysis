-- Q1. Overall funnel: how many sessions survive each stage, and where is the biggest leak?
SELECT 'Started'          AS stage, COUNT(*)       AS sessions, 100.0 AS pct_of_start, NULL AS step_conversion_pct FROM verification_sessions
UNION ALL
SELECT 'Upload OK',  SUM(upload_ok), ROUND(100.0*SUM(upload_ok)/COUNT(*),1), ROUND(100.0*SUM(upload_ok)/COUNT(*),1) FROM verification_sessions
UNION ALL
SELECT 'OCR OK',     SUM(ocr_ok),    ROUND(100.0*SUM(ocr_ok)/COUNT(*),1),    ROUND(100.0*SUM(ocr_ok)/SUM(upload_ok),1) FROM verification_sessions
UNION ALL
SELECT 'Face match OK', SUM(face_ok), ROUND(100.0*SUM(face_ok)/COUNT(*),1),  ROUND(100.0*SUM(face_ok)/SUM(ocr_ok),1) FROM verification_sessions
UNION ALL
SELECT 'Approved',   SUM(approved),  ROUND(100.0*SUM(approved)/COUNT(*),1),  ROUND(100.0*SUM(approved)/SUM(face_ok),1) FROM verification_sessions;
