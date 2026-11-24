 M-Pesa analytics (SIMULATED DATA) - SQL question set
-- Run against mpesa.db (SQLite). Write your answer under each question.
-- Difficulty: [*] warm-up   [**] intermediate   [***] stretch
--
-- GROUND RULES (write your choices into your README - they matter):
--   * Decide how to treat FAILED / REVERSED transactions. Default: use
--     status = 'SUCCESS' for value and activity, and say so.
--   * Data covers 2026-01-01 to 2026-06-30. Use 2026-06-30 as "today".
--   * Amounts are in KES.
-- =====================================================================


-- ---------------------------------------------------------------------
-- SECTION A: Profile the data and find the rhythm
-- ---------------------------------------------------------------------

-- Q1 [*]  WORKED EXAMPLE
-- For each month and transaction type: number of transactions, total value,
-- and success rate (%).
SELECT strftime('%Y-%m', txn_ts)                                   AS month,
       txn_type,
       COUNT(*)                                                    AS txns,
       SUM(amount)                                                 AS value_kes,
       ROUND(100.0 * SUM(status = 'SUCCESS') / COUNT(*), 1)        AS success_rate_pct
FROM transactions
GROUP BY month, txn_type
ORDER BY month, txn_type;

-- Q2 [*]
-- Which 3 hours of the day are busiest? Show the transaction count per hour,
-- and each hour's share of the day's traffic.
-- Hint: strftime('%H', txn_ts); a window SUM() OVER () gives the total.

-- Q3 [**]
-- Is there a salary-day effect? Compare average DAILY transaction count and
-- average transaction value for days 25-31 and 1-2 versus the rest of the month.
-- Hint: aggregate to one row per date in a CTE first, then bucket the dates.

-- Q4 [**]
-- Weekday pattern: average daily transactions by day of week (Mon..Sun).
-- Does Saturday differ from Sunday? Hint: strftime('%w', ...) gives 0 = Sunday.


-- ---------------------------------------------------------------------
-- SECTION B: Customers - who they are and how they behave
-- ---------------------------------------------------------------------

-- Q5 [*]
-- Top 10 customers by total value SENT (send_money), with each one's share of
-- all send_money value. Then: what share of value do the top 10% of customers
-- (by value sent) account for? Hint: NTILE(10) or PERCENT_RANK().

-- Q6 [**]
-- Customers who are registered but made NO successful transaction in the six
-- months. How many are they, and what is the inactive rate by county?
-- Hint: LEFT JOIN ... IS NULL, or NOT EXISTS. Compare the two approaches.

-- Q7 [***]  RFM segmentation (the classic, and a great interview talking point)
-- As of 2026-06-30, for each active customer compute:
--   Recency   = days since last successful transaction
--   Frequency = number of successful transactions
--   Monetary  = total successful value
-- Score each 1-5 with NTILE(5) (careful: recency is "lower is better"),
-- then label segments, e.g. Champions (R>=4, F>=4, M>=4), Loyal, Big Spenders,
-- At Risk (low R, high F/M), Hibernating. Report segment sizes and the share
-- of total value each segment contributes.

-- Q8 [**]
-- New vs returning: for each month, how many distinct customers transacted,
-- and how many of them had their FIRST transaction (in this dataset) that month?
-- Hint: MIN(month) per customer in a CTE.

-- Q9 [**]
-- Product adoption: what percentage of active customers used 1, 2, 3, ... of
-- the six transaction types? Do customers who use paybill also transact more?


-- ---------------------------------------------------------------------
-- SECTION C: Revenue and product mix
-- ---------------------------------------------------------------------

-- Q10 [**]
-- Fee revenue by month and transaction type. Add month-over-month growth (%)
-- of total fee revenue using LAG().

-- Q11 [**]
-- Paybill: rank biller categories by total value, with share of paybill value.
-- Then show the single TOP biller (merchant_id) inside each category.
-- Hint: ROW_NUMBER() OVER (PARTITION BY category ORDER BY value DESC).

-- Q12 [**]
-- Average buy_goods basket size by till category and by county of the CUSTOMER.
-- Which category-county combinations have the highest average ticket
-- (ignore combinations with fewer than 30 transactions)?


-- ---------------------------------------------------------------------
-- SECTION D: Agents - cash flow and network health
-- ---------------------------------------------------------------------

-- Q13 [**]
-- Rank agents WITHIN their county by total withdrawal value (RANK or
-- DENSE_RANK with PARTITION BY county). Show the top 3 per county.

-- Q14 [***]
-- Float / cash pressure. An agent whose customers mostly WITHDRAW runs short of
-- cash; one whose customers mostly DEPOSIT runs short of e-float.
-- For each agent and month compute net cash outflow = withdrawals - deposits.
-- Which agents have a net outflow above the 90th percentile in at least 3 of
-- the 6 months? (These are the ones to replenish first.)

-- Q15 [**]
-- How "local" is cash-in/cash-out? What % of withdrawals happen at an agent in
-- the same county as the customer? Does it differ by county?
-- Hint: join transactions -> customers and -> agents.


-- ---------------------------------------------------------------------
-- SECTION E: Fraud and anomaly flags
-- (Do NOT query the _fraud_truth table until you have finished Q16-Q18.)
-- ---------------------------------------------------------------------

-- Q16 [***]  Rapid-fire transfers
-- Flag customers who make 6 or more successful send_money transactions within
-- any rolling 10-minute window. Then refine: require at least 5 DISTINCT
-- recipients in that window.
-- Hint: epoch seconds with CAST(strftime('%s', txn_ts) AS INT), then
--   COUNT(*) OVER (PARTITION BY customer_id ORDER BY epoch
--                  RANGE BETWEEN 600 PRECEDING AND CURRENT ROW)
-- For distinct recipients, try a self-join on customer_id and the time window.

-- Q17 [***]  New-recipient, large, night-time transfers
-- Flag successful send_money transactions where ALL of these hold:
--   (a) the recipient is new for that sender (first ever transfer to them),
--   (b) the amount is far above the sender's own history, e.g. > 20x their
--       average previous transfer (running AVG with ROWS BETWEEN UNBOUNDED
--       PRECEDING AND 1 PRECEDING),
--   (c) it happened between 00:00 and 05:59.
-- Try dropping conditions one at a time. What does each one cost you in
-- false positives? Compare with the naive rule "amount >= 50,000".

-- Q18 [***]  Evaluate your own rules
-- Only now: join your flags to _fraud_truth and report, per rule,
--   true positives, false positives, missed cases (false negatives),
--   precision = TP / (TP + FP) and recall = TP / (TP + FN).
-- In your README, say which rule you would put into production and why.
-- Remember: a fraud team has to review every alert, so precision matters
-- as much as recall.


-- ---------------------------------------------------------------------
-- BONUS: prepare data for the dashboard / a churn model
-- ---------------------------------------------------------------------

-- Q19 [**]
-- CREATE VIEW v_customer_features AS ...
-- One row per customer: county, age_group, account_type, tenure in days,
-- txn count, total value, avg amount, distinct recipients, share of night-time
-- transactions, days since last transaction. Export it to CSV for Power BI.

