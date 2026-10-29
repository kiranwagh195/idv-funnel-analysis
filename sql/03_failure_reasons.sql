-- Q3. "Why did this verification fail?"  Pareto of failure reasons with cumulative share.
WITH f AS (
    SELECT failure_stage, failure_reason, COUNT(*) AS n
    FROM verification_sessions
    WHERE approved = 0
    GROUP BY failure_stage, failure_reason
),
t AS (SELECT SUM(n) AS total FROM f)
SELECT
    f.failure_stage,
    f.failure_reason,
    f.n                                          AS failed_sessions,
    ROUND(100.0 * f.n / t.total, 1)              AS pct_of_all_failures,
    ROUND(100.0 * SUM(f.n) OVER (ORDER BY f.n DESC) / t.total, 1) AS cumulative_pct
FROM f, t
ORDER BY f.n DESC;
