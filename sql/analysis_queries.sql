-- Standalone analysis queries for the racial equity grantmaking database.
-- All queries target the SQLite schema defined in create_tables.sql.

-- ---------------------------------------------------------
-- 1. Overall summary statistics
-- ---------------------------------------------------------

SELECT
    COUNT(*)                                        AS total_grants,
    COUNT(DISTINCT funder_ein)                      AS unique_funders,
    COUNT(DISTINCT recipient_ein)                   AS unique_recipients,
    ROUND(SUM(grant_amount) / 1e6, 1)              AS total_dollars_m,
    ROUND(AVG(grant_amount))                        AS avg_grant_size,
    MIN(tax_year)                                   AS earliest_year,
    MAX(tax_year)                                   AS latest_year
FROM grants
WHERE is_racial_equity = 1;


-- ---------------------------------------------------------
-- 2. Racial equity grants by year (time series)
-- ---------------------------------------------------------

SELECT
    tax_year,
    COUNT(*)                                        AS grant_count,
    COUNT(DISTINCT funder_ein)                      AS unique_funders,
    ROUND(SUM(grant_amount) / 1e6, 2)              AS total_dollars_m,
    ROUND(AVG(grant_amount))                        AS avg_grant_size
FROM grants
WHERE is_racial_equity = 1
  AND tax_year IS NOT NULL
GROUP BY tax_year
ORDER BY tax_year;


-- ---------------------------------------------------------
-- 3. Pre- vs. post-2020 comparison
-- ---------------------------------------------------------

SELECT
    CASE WHEN tax_year >= 2020 THEN 'Post-2020' ELSE 'Pre-2020' END AS period,
    COUNT(*)                                                          AS grant_count,
    COUNT(DISTINCT funder_ein)                                        AS unique_funders,
    ROUND(SUM(grant_amount) / 1e6, 1)                               AS total_dollars_m,
    ROUND(AVG(grant_amount))                                          AS avg_grant_size,
    COUNT(DISTINCT tax_year)                                          AS years_covered,
    ROUND(SUM(grant_amount) / COUNT(DISTINCT tax_year) / 1e6, 1)   AS avg_annual_dollars_m
FROM grants
WHERE is_racial_equity = 1
  AND tax_year IS NOT NULL
GROUP BY period;


-- ---------------------------------------------------------
-- 4. Top 20 funders by total racial equity giving
-- ---------------------------------------------------------

SELECT
    g.funder_ein,
    f.name                                          AS funder_name,
    f.state                                         AS funder_state,
    COUNT(*)                                        AS grant_count,
    ROUND(SUM(g.grant_amount) / 1e6, 2)            AS total_dollars_m,
    MIN(g.tax_year)                                 AS first_year,
    MAX(g.tax_year)                                 AS last_year
FROM grants g
LEFT JOIN foundations f ON g.funder_ein = f.ein
WHERE g.is_racial_equity = 1
GROUP BY g.funder_ein
ORDER BY SUM(g.grant_amount) DESC
LIMIT 20;


-- ---------------------------------------------------------
-- 5. Racial equity giving as share of total giving by funder
-- ---------------------------------------------------------

SELECT
    funder_ein,
    COUNT(*)                                        AS total_grants,
    SUM(CASE WHEN is_racial_equity = 1 THEN 1 ELSE 0 END)  AS re_grants,
    ROUND(SUM(CASE WHEN is_racial_equity = 1 THEN grant_amount ELSE 0 END) / 1e6, 2)
                                                    AS re_dollars_m,
    ROUND(SUM(grant_amount) / 1e6, 2)              AS total_dollars_m,
    ROUND(
        100.0 * SUM(CASE WHEN is_racial_equity = 1 THEN grant_amount ELSE 0 END)
        / NULLIF(SUM(grant_amount), 0),
        1
    )                                               AS re_pct_of_total
FROM grants
GROUP BY funder_ein
HAVING total_grants >= 10    -- filter to funders with meaningful activity
ORDER BY re_pct_of_total DESC;


-- ---------------------------------------------------------
-- 6. Geographic distribution of racial equity grant recipients
-- ---------------------------------------------------------

SELECT
    recipient_state,
    COUNT(*)                                        AS grant_count,
    COUNT(DISTINCT recipient_ein)                   AS unique_orgs,
    ROUND(SUM(grant_amount) / 1e6, 2)              AS total_dollars_m
FROM grants
WHERE is_racial_equity = 1
  AND recipient_state IS NOT NULL
GROUP BY recipient_state
ORDER BY SUM(grant_amount) DESC;


-- ---------------------------------------------------------
-- 7. Racial equity grants by NTEE major category
-- ---------------------------------------------------------

SELECT
    r.ntee_major,
    COUNT(g.id)                                     AS grant_count,
    COUNT(DISTINCT g.recipient_ein)                 AS unique_orgs,
    ROUND(SUM(g.grant_amount) / 1e6, 2)            AS total_dollars_m,
    ROUND(AVG(g.grant_amount))                      AS avg_grant_size
FROM grants g
JOIN recipients r ON g.recipient_ein = r.ein
WHERE g.is_racial_equity = 1
  AND r.ntee_major IS NOT NULL
GROUP BY r.ntee_major
ORDER BY SUM(g.grant_amount) DESC;


-- ---------------------------------------------------------
-- 8. Grant size distribution buckets
-- ---------------------------------------------------------

SELECT
    CASE
        WHEN grant_amount < 10000              THEN 'Under $10K'
        WHEN grant_amount < 50000              THEN '$10K–$50K'
        WHEN grant_amount < 100000             THEN '$50K–$100K'
        WHEN grant_amount < 500000             THEN '$100K–$500K'
        WHEN grant_amount < 1000000            THEN '$500K–$1M'
        WHEN grant_amount < 5000000            THEN '$1M–$5M'
        ELSE '$5M+'
    END                                             AS size_bucket,
    COUNT(*)                                        AS grant_count,
    ROUND(SUM(grant_amount) / 1e6, 2)              AS total_dollars_m
FROM grants
WHERE is_racial_equity = 1
GROUP BY size_bucket
ORDER BY MIN(grant_amount);


-- ---------------------------------------------------------
-- 9. Most common racial equity grant purposes (keyword frequency)
--    (rough proxy — purpose text is free-form)
-- ---------------------------------------------------------

SELECT
    CASE
        WHEN LOWER(grant_purpose) LIKE '%voting%'           THEN 'Voting / Civic Rights'
        WHEN LOWER(grant_purpose) LIKE '%criminal justice%' THEN 'Criminal Justice Reform'
        WHEN LOWER(grant_purpose) LIKE '%education%'        THEN 'Education'
        WHEN LOWER(grant_purpose) LIKE '%health%'           THEN 'Health'
        WHEN LOWER(grant_purpose) LIKE '%housing%'          THEN 'Housing'
        WHEN LOWER(grant_purpose) LIKE '%economic%'         THEN 'Economic Development'
        WHEN LOWER(grant_purpose) LIKE '%immigration%'      THEN 'Immigration'
        WHEN LOWER(grant_purpose) LIKE '%environment%'      THEN 'Environment / Climate'
        WHEN LOWER(grant_purpose) LIKE '%arts%'
          OR LOWER(grant_purpose) LIKE '%culture%'          THEN 'Arts & Culture'
        ELSE 'Other / General'
    END                                             AS issue_area,
    COUNT(*)                                        AS grant_count,
    ROUND(SUM(grant_amount) / 1e6, 2)              AS total_dollars_m
FROM grants
WHERE is_racial_equity = 1
GROUP BY issue_area
ORDER BY SUM(grant_amount) DESC;


-- ---------------------------------------------------------
-- 10. Demographics: leadership diversity of funded orgs
--     (populated after Candid API key is active)
-- ---------------------------------------------------------

SELECT
    CASE
        WHEN d.board_poc_pct >= 50 THEN 'Majority POC Board'
        WHEN d.board_poc_pct > 0   THEN 'Minority POC Board'
        ELSE 'No Data / All White'
    END                                             AS board_diversity_category,
    COUNT(DISTINCT g.recipient_ein)                 AS org_count,
    ROUND(SUM(g.grant_amount) / 1e6, 2)            AS total_dollars_m,
    ROUND(AVG(g.grant_amount))                      AS avg_grant_size
FROM grants g
JOIN demographics d ON g.recipient_ein = d.ein
WHERE g.is_racial_equity = 1
GROUP BY board_diversity_category
ORDER BY SUM(g.grant_amount) DESC;
