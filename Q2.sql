-- SQLite
--Q2: Hourly transaction count and share percentage
SELECT strftime('%H', txn_ts) AS hour_of_day,
        COUNT(*) AS transaction_count,
        ROUND(100.0* COUNT(*)/SUM(COUNT(*)) OVER(),1) AS share_percentage
FROM transactions
GROUP BY hour_of_day
ORDER BY transaction_count DESC;
-- Takeaway: Traffic peaks sharply in the evening (5 PM - 8 PM), with 6 PM being the busiest hour.
-- Action: Agents must ensure they have enough cash and e-float before 5 PM to handle the evening rush.

--Q3: Average daily transactions and value for salary period vs rest of the month
WITH daily AS(
    SELECT DATE(txn_ts) AS txn_date,
           COUNT(*) AS daily_txns,
           SUM(amount) AS daily_value
    FROM transactions
    WHERE status = 'success'
    GROUP BY DATE(txn_ts)
)

SELECT 
    CASE 
    WHEN(CAST(strftime '%d', txn_date) AS INT) BETWEEN 25 AND 31
    THEN 'Salary Period'
    WHEN(CAST(strftime '%d', txn_date) AS INT) BETWEEN 1 AND 2
    THEN 'Salary Period'
    ELSE 'Rest of the month'
    END AS period,
    AVG(daily_txns) AS avg_daily_txns,
        AVG(daily_value) AS avg_daily_value
FROM daily
GROUP BY period;
-- Salary window (25th-2nd) sees roughly 2x the daily traffic and 2.3x the daily value.
-- Action: Agents must prepare for extreme cash and e-float demand ahead of the 25th.


--Q4: Average daily transactions by day of the week
WITH daily AS(
    SELECT DATE(txn_ts) AS txn_date,
           COUNT(*) AS daily_txns,
    FROM transactions
    WHERE status = 'success'
    GROUP BY DATE(txn_ts)
)
SELECT 
        CASE strftime('%w', txn_date)
        WHEN '0' THEN 'Sunday'
        WHEN '1' THEN 'Monday'
        WHEN '2' THEN 'Tuesday'
        WHEN '3' THEN 'Wednesday'
        WHEN '4' THEN 'Thursday'
        WHEN '5' THEN 'Friday'
        WHEN '6' THEN 'Saturday'
        END AS day_of_the_week,
        AVG(daily_txns) AS avg_daily_txns
FROM daily
GROUP BY strftime('%w', txn_date) -- <--- HIDDEN SORT KEY 1
ORDER BY strftime('%w', txn_date); -- <--- HIDDEN SORT KEY 2
-- Takeaway: Weekdays maintain steady volume (~850/day), Saturday is the busiest (907), 
-- while Sunday is the quietest (658).
-- Action: Schedule system maintenance for early Sunday mornings when traffic is lowest, 
-- and ensure agent float is maxed out on Mondays and Tuesdays.


--Q5: Top 10 customers by total sent value and their share of total sent value, 
--and distribution of customers by percentiles of total sent value
WITH customer_sends AS(
    SELECT customer_id,
           COUNT(*) AS snds_count,
           SUM(amount) AS total_sent
           FROM transactions
           WHERE status = 'success' AND txn_type = 'send_money'
           GROUP BY customer_id
),
ranked_customers AS(
      SELECT customer_id,
             total_sent,
       NTILE(10) OVER (ORDER BY total_sent DESC) AS percent_rank
       FROM customer_sends
)

SELECT
      customer_id,
      total_sent,
      ROUND(100.0* total_sent/SUM(total_sent) OVER(),1) AS share_pct
FROM customer_sends
ORDER BY total_sent DESC
LIMIT 10;

SELECT percent_rank,
       COUNT(*) AS num_customers,
       SUM(total_sent) AS total_sent_by_group,
        ROUND(100.0* SUM(total_sent)/SUM(SUM(total_sent)) OVER(),1) AS share_of_total_value_pct
FROM ranked_customers
GROUP BY percent_rank
ORDER BY percent_rank;
-- Takeaway: The top 10% of customers (452 people) account for 54.5% of all send_money value. 
-- The top 20% (Deciles 1 & 2) account for 71% (54.5% + 16.4%).
-- Action: We should focus retention efforts (VIP support, loyalty perks) on that top 10% 
-- to protect over half of our platform's transaction volume.

