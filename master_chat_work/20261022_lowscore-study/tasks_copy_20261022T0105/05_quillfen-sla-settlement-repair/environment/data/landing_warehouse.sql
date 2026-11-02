-- partition registry dump
SET TIME ZONE 'UTC';

INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-02-09 04:00:00', '2026-02-09 04:10:05'),
  ('fin.inventory_daily', '2026-02-09 04:00:00', '2026-02-09 04:40:55'),
  ('fin.inventory_daily', '2026-02-09 04:00:00', '2026-02-09 06:52:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-02-09 04:00:00', '2026-02-09 07:01:14'),
  ('fin.refunds_daily', '2026-02-09 04:00:00', '2026-02-09 09:05:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-02-10 04:00:00', '2026-02-10 04:14:44'),
  ('leg.forecast_daily', '2026-02-10 04:00:00', '2026-02-10 05:30:58'),
  ('leg.forecast_daily', '2026-02-10 04:00:00', '2026-02-10 07:32:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-02-13 04:00:00', '2026-02-13 04:51:42'),
  ('fin.returns_daily', '2026-02-13 04:00:00', '2026-02-13 05:19:48'),
  ('fin.returns_daily', '2026-02-13 04:00:00', '2026-02-13 07:28:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.audits_twice_monthly', '2026-02-14 04:00:00', '2026-02-14 04:28:26'),
  ('lake.audits_twice_monthly', '2026-02-14 04:00:00', '2026-02-14 06:12:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.audits_twice_monthly', '2026-02-14 04:00:00', '2026-02-14 07:49:34'),
  ('fin.events_hourly', '2026-02-20 00:00:00', '2026-02-20 00:13:40'),
  ('ana.fraud_hourly', '2026-02-20 00:45:00', '2026-02-20 01:09:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-20 01:00:00', '2026-02-20 01:22:06'),
  ('fin.inventory_daily', '2026-02-20 01:10:00', '2026-02-20 01:30:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-02-20 01:10:00', '2026-02-20 01:52:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 01:45:00', '2026-02-20 01:55:40'),
  ('fin.events_hourly', '2026-02-20 02:00:00', '2026-02-20 02:12:11'),
  ('leg.tickets_four_hourly', '2026-02-20 02:15:00', '2026-02-20 02:17:52'),
  ('lake.alerts_daily', '2026-02-20 03:00:00', '2026-02-20 03:03:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 02:45:00', '2026-02-20 03:18:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-20 03:00:00', '2026-02-20 03:23:33'),
  ('fin.catalog_weekday', '2026-02-20 04:45:00', '2026-02-20 05:07:11'),
  ('ana.limits_weekday', '2026-02-20 04:20:00', '2026-02-20 05:40:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-20 05:00:00', '2026-02-20 05:45:35'),
  ('ana.fraud_hourly', '2026-02-20 04:45:00', '2026-02-20 06:07:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 05:45:00', '2026-02-20 06:13:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-02-20 05:45:00', '2026-02-20 06:13:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-20 06:15:00', '2026-02-20 06:17:45'),
  ('fin.events_hourly', '2026-02-20 06:00:00', '2026-02-20 06:23:33'),
  ('ana.fraud_hourly', '2026-02-20 06:45:00', '2026-02-20 06:59:34'),
  ('ana.fraud_hourly', '2026-02-20 07:45:00', '2026-02-20 07:56:43'),
  ('ana.renewals_four_hourly', '2026-02-20 07:30:00', '2026-02-20 07:58:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-20 08:00:00', '2026-02-20 08:19:05'),
  ('lake.events_weekday', '2026-02-20 07:30:00', '2026-02-20 08:19:56'),
  ('lake.search_weekday', '2026-02-20 07:15:00', '2026-02-20 08:56:27'),
  ('ana.fraud_hourly', '2026-02-20 08:45:00', '2026-02-20 09:02:36'),
  ('fin.events_hourly', '2026-02-20 09:00:00', '2026-02-20 09:06:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-20 10:00:00', '2026-02-20 10:18:38'),
  ('ana.fraud_hourly', '2026-02-20 09:45:00', '2026-02-20 10:20:16'),
  ('ana.fraud_hourly', '2026-02-20 10:45:00', '2026-02-20 11:07:59'),
  ('leg.exports_daily', '2026-02-20 10:05:00', '2026-02-20 11:16:48'),
  ('fin.events_hourly', '2026-02-20 11:00:00', '2026-02-20 11:27:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 11:45:00', '2026-02-20 12:08:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-20 12:00:00', '2026-02-20 12:20:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-20 13:00:00', '2026-02-20 13:11:51'),
  ('leg.quotes_daily', '2026-02-20 13:00:00', '2026-02-20 13:35:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LAKE.AUDITS_TWICE_MONTHLY', '2026-01-25 04:00:00', '2026-01-25 05:13:09'),
  ('leg/forecast_daily', '2026-01-30 04:00:00', '2026-01-30 04:41:28'),
  ('lake.search_weekday', '2026-01-30 04:00:00', '2026-01-30 05:02:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.FORECAST_DAILY', '2026-01-30 04:00:00', '2026-01-30 06:42:23'),
  ('lake.search_weekday', '2026-01-30 04:00:00', '2026-01-30 07:37:39'),
  ('fin/renewals_daily', '2026-01-31 04:00:00', '2026-01-31 04:59:24'),
  ('fin.renewals_daily', '2026-02-01 04:00:00', '2026-02-01 04:59:58'),
  ('lake.events_weekday', '2026-02-04 04:00:00', '2026-02-04 04:24:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-02-04 04:00:00', '2026-02-04 06:32:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-02-20 13:20:00', '2026-02-20 13:53:05'),
  ('ana.fraud_hourly', '2026-02-20 13:45:00', '2026-02-20 14:13:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-02-20 13:30:00', '2026-02-20 14:36:28'),
  ('fin.events_hourly', '2026-02-20 15:00:00', '2026-02-20 15:13:16'),
  ('ana.fraud_hourly', '2026-02-20 14:45:00', '2026-02-20 15:17:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 15:45:00', '2026-02-20 16:02:37'),
  ('lake.accounts_weekday', '2026-02-20 16:15:00', '2026-02-20 16:17:21'),
  ('ana.renewals_four_hourly', '2026-02-20 15:30:00', '2026-02-20 16:38:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 16:45:00', '2026-02-20 17:13:12'),
  ('fin.events_hourly', '2026-02-20 17:00:00', '2026-02-20 17:27:18'),
  ('fin.events_hourly', '2026-02-20 18:00:00', '2026-02-20 18:06:15'),
  ('ana.fraud_hourly', '2026-02-20 17:45:00', '2026-02-20 18:15:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-20 18:15:00', '2026-02-20 18:16:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/forecast_daily', '2026-02-20 18:05:00', '2026-02-20 18:56:24'),
  ('fin/events_hourly', '2026-02-20 19:00:00', '2026-02-20 19:19:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 19:45:00', '2026-02-20 20:03:18'),
  ('leg.search_daily', '2026-02-20 19:15:00', '2026-02-20 21:04:47'),
  ('fin.events_hourly', '2026-02-20 20:00:00', '2026-02-20 21:08:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 20:45:00', '2026-02-20 21:10:08'),
  ('fin.events_hourly', '2026-02-20 21:00:00', '2026-02-20 21:16:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-20 22:15:00', '2026-02-20 22:18:21'),
  ('ana.fraud-hourly', '2026-02-20 21:45:00', '2026-02-20 22:21:46'),
  ('fin.events_hourly', '2026-02-20 22:00:00', '2026-02-20 22:25:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-20 22:45:00', '2026-02-20 23:12:09'),
  ('ana.renewals_four_hourly', '2026-02-20 23:30:00', '2026-02-20 23:39:59'),
  ('fin.events_hourly', '2026-02-21 00:00:00', '2026-02-21 00:46:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-21 01:00:00', '2026-02-21 01:09:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-02-21 00:45:00', '2026-02-21 01:11:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-02-21 01:10:00', '2026-02-21 01:49:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-21 01:45:00', '2026-02-21 02:09:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-02-21 02:15:00', '2026-02-21 02:18:23'),
  ('fin.exports_daily', '2026-02-21 01:10:00', '2026-02-21 02:25:19'),
  ('lake.alerts_daily', '2026-02-21 03:00:00', '2026-02-21 03:03:07'),
  ('fin.events_hourly', '2026-02-21 03:00:00', '2026-02-21 03:09:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-21 02:45:00', '2026-02-21 03:10:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-21 03:30:00', '2026-02-21 03:56:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-21 03:45:00', '2026-02-21 03:57:55'),
  ('ana.fraud_hourly', '2026-02-21 04:45:00', '2026-02-21 05:16:19'),
  ('fin.renewals_daily', '2026-02-21 01:20:00', '2026-02-21 05:21:47'),
  ('fin.refunds_daily', '2026-02-21 05:45:00', '2026-02-21 05:59:16'),
  ('ana.fraud-hourly', '2026-02-21 05:45:00', '2026-02-21 06:01:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-02-21 06:15:00', '2026-02-21 06:16:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-21 06:45:00', '2026-02-21 06:58:34'),
  ('fin.events_hourly', '2026-02-21 06:00:00', '2026-02-21 07:00:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-21 07:00:00', '2026-02-21 07:14:15'),
  ('ana.renewals_four_hourly', '2026-02-21 07:30:00', '2026-02-21 07:45:30'),
  ('FIN.EVENTS_HOURLY', '2026-02-21 08:00:00', '2026-02-21 08:18:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-21 08:45:00', '2026-02-21 09:01:14'),
  ('fin.events_hourly', '2026-02-21 09:00:00', '2026-02-21 09:21:33'),
  ('ana.fraud_hourly', '2026-02-21 09:45:00', '2026-02-21 10:11:48'),
  ('leg.tickets_four_hourly', '2026-02-21 10:15:00', '2026-02-21 10:16:47'),
  ('ana.fraud_hourly', '2026-02-21 10:45:00', '2026-02-21 11:15:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-21 11:00:00', '2026-02-21 11:20:09'),
  ('ana.renewals_four_hourly', '2026-02-21 11:30:00', '2026-02-21 11:40:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-02-21 10:05:00', '2026-02-21 11:49:43'),
  ('ana.fraud_hourly', '2026-02-21 11:45:00', '2026-02-21 12:19:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-21 12:00:00', '2026-02-21 12:20:29'),
  ('fin.events_hourly', '2026-02-21 13:00:00', '2026-02-21 13:14:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-02-21 13:00:00', '2026-02-21 13:23:11'),
  ('fin.events_hourly', '2026-02-21 14:00:00', '2026-02-21 14:09:47'),
  ('leg.tickets-four-hourly', '2026-02-21 14:15:00', '2026-02-21 14:16:36'),
  ('ana.churn_daily', '2026-02-21 13:30:00', '2026-02-21 14:51:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-21 14:45:00', '2026-02-21 14:59:35'),
  ('ana.fraud-hourly', '2026-02-21 13:45:00', '2026-02-21 15:13:31'),
  ('ana.renewals_four_hourly', '2026-02-21 15:30:00', '2026-02-21 15:52:46'),
  ('ana.fraud_hourly', '2026-02-21 16:45:00', '2026-02-21 17:01:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-21 16:00:00', '2026-02-21 17:06:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-21 18:00:00', '2026-02-21 18:11:25'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-02-21 18:15:00', '2026-02-21 18:18:29'),
  ('ana.fraud_hourly', '2026-02-21 17:45:00', '2026-02-21 18:47:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-21 18:45:00', '2026-02-21 18:59:10'),
  ('leg.forecast_daily', '2026-02-21 18:05:00', '2026-02-21 19:02:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-21 19:00:00', '2026-02-21 19:08:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-21 19:45:00', '2026-02-21 20:05:51'),
  ('leg.search_daily', '2026-02-21 19:15:00', '2026-02-21 20:10:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-21 20:45:00', '2026-02-21 20:52:53'),
  ('fin.events_hourly', '2026-02-21 21:00:00', '2026-02-21 21:14:01'),
  ('ana.fraud_hourly', '2026-02-21 21:45:00', '2026-02-21 22:11:26'),
  ('leg.tickets_four_hourly', '2026-02-21 22:15:00', '2026-02-21 22:16:49'),
  ('fin/events_hourly', '2026-02-21 22:00:00', '2026-02-21 22:38:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-21 22:45:00', '2026-02-21 22:56:53'),
  ('fin.events_hourly', '2026-02-21 23:00:00', '2026-02-21 23:36:31'),
  ('ana.fraud_hourly', '2026-02-22 00:45:00', '2026-02-22 01:22:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-02-22 01:10:00', '2026-02-22 01:59:50'),
  ('ana.fraud_hourly', '2026-02-22 01:45:00', '2026-02-22 02:00:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-22 02:00:00', '2026-02-22 02:16:37'),
  ('fin.renewals_daily', '2026-02-22 01:20:00', '2026-02-22 02:26:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-02-22 03:00:00', '2026-02-22 03:02:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-22 03:00:00', '2026-02-22 03:15:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-22 02:45:00', '2026-02-22 03:20:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-22 03:30:00', '2026-02-22 03:41:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-02-22 03:45:00', '2026-02-22 03:56:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-22 04:00:00', '2026-02-22 04:24:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-22 04:45:00', '2026-02-22 05:04:42'),
  ('ana.fraud_hourly', '2026-02-22 05:45:00', '2026-02-22 05:53:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-22 06:15:00', '2026-02-22 06:16:57'),
  ('fin.events_hourly', '2026-02-22 06:00:00', '2026-02-22 06:17:45'),
  ('ana.fraud_hourly', '2026-02-22 06:45:00', '2026-02-22 07:00:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-22 07:30:00', '2026-02-22 07:49:11'),
  ('fin.events-hourly', '2026-02-22 08:00:00', '2026-02-22 08:08:56'),
  ('ana.fraud_hourly', '2026-02-22 07:45:00', '2026-02-22 08:19:18'),
  ('lake.clicks_daily', '2026-02-22 08:20:00', '2026-02-22 08:34:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-22 08:45:00', '2026-02-22 09:07:05'),
  ('fin.events_hourly', '2026-02-22 09:00:00', '2026-02-22 09:17:22'),
  ('ana/fraud_hourly', '2026-02-22 09:45:00', '2026-02-22 10:01:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-22 10:00:00', '2026-02-22 10:11:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-22 10:45:00', '2026-02-22 10:58:41'),
  ('leg.exports_daily', '2026-02-22 10:05:00', '2026-02-22 11:22:42'),
  ('ana.renewals_four_hourly', '2026-02-22 11:30:00', '2026-02-22 11:39:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-22 11:45:00', '2026-02-22 11:58:07'),
  ('fin.events_hourly', '2026-02-22 12:00:00', '2026-02-22 12:23:34'),
  ('fin.events_hourly', '2026-02-22 13:00:00', '2026-02-22 13:17:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-22 14:15:00', '2026-02-22 14:16:10'),
  ('ana.fraud-hourly', '2026-02-22 12:45:00', '2026-02-22 14:17:58'),
  ('fin.events_hourly', '2026-02-22 14:00:00', '2026-02-22 14:24:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-02-22 13:30:00', '2026-02-22 14:41:53'),
  ('ana.fraud_hourly', '2026-02-22 14:45:00', '2026-02-22 15:17:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-22 15:00:00', '2026-02-22 15:18:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-02-22 16:00:00', '2026-02-22 16:06:00'),
  ('ana.fraud-hourly', '2026-02-22 15:45:00', '2026-02-22 16:42:25'),
  ('ana.fraud_hourly', '2026-02-22 16:45:00', '2026-02-22 17:08:15'),
  ('FIN.EVENTS_HOURLY', '2026-02-22 17:00:00', '2026-02-22 17:11:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-22 17:45:00', '2026-02-22 17:54:14'),
  ('fin.events_hourly', '2026-02-22 18:00:00', '2026-02-22 18:14:37'),
  ('ANA.FRAUD_HOURLY', '2026-02-22 18:45:00', '2026-02-22 19:15:05'),
  ('fin.events_hourly', '2026-02-22 19:00:00', '2026-02-22 19:16:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-02-22 19:15:00', '2026-02-22 19:17:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals-four-hourly', '2026-02-22 19:30:00', '2026-02-22 19:47:52'),
  ('leg.search_daily', '2026-02-22 19:15:00', '2026-02-22 20:10:14'),
  ('fin.events-hourly', '2026-02-22 20:00:00', '2026-02-22 20:10:59'),
  ('ana.fraud_hourly', '2026-02-22 19:45:00', '2026-02-22 20:15:33'),
  ('ana.fraud_hourly', '2026-02-22 20:45:00', '2026-02-22 21:10:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-22 21:00:00', '2026-02-22 21:11:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-22 21:45:00', '2026-02-22 22:12:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-22 22:15:00', '2026-02-22 22:16:31'),
  ('FIN.EVENTS_HOURLY', '2026-02-22 22:00:00', '2026-02-22 22:26:26'),
  ('fin.events_hourly', '2026-02-22 23:00:00', '2026-02-22 23:26:52'),
  ('fin.events-hourly', '2026-02-23 00:00:00', '2026-02-23 00:25:46'),
  ('fin.events_hourly', '2026-02-23 01:00:00', '2026-02-23 01:12:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-02-23 01:10:00', '2026-02-23 01:31:16'),
  ('fin.renewals_daily', '2026-02-23 01:20:00', '2026-02-23 01:42:01'),
  ('ana.fraud_hourly', '2026-02-23 01:45:00', '2026-02-23 02:01:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-23 00:45:00', '2026-02-23 02:11:40'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-02-23 02:15:00', '2026-02-23 02:16:45'),
  ('fin.events_hourly', '2026-02-23 02:00:00', '2026-02-23 02:17:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-02-23 02:10:00', '2026-02-23 03:01:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-23 02:45:00', '2026-02-23 03:13:01'),
  ('fin/events_hourly', '2026-02-23 03:00:00', '2026-02-23 03:16:17'),
  ('ana/renewals_four_hourly', '2026-02-23 03:30:00', '2026-02-23 03:36:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-23 03:45:00', '2026-02-23 04:16:59'),
  ('fin.events_hourly', '2026-02-23 04:00:00', '2026-02-23 04:26:40'),
  ('fin.catalog-weekday', '2026-02-23 04:45:00', '2026-02-23 05:03:48'),
  ('ana.fraud_hourly', '2026-02-23 04:45:00', '2026-02-23 05:09:21'),
  ('fin.events_hourly', '2026-02-23 05:00:00', '2026-02-23 05:53:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-02-23 05:45:00', '2026-02-23 06:01:21'),
  ('ana.fraud_hourly', '2026-02-23 05:45:00', '2026-02-23 06:01:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-23 06:00:00', '2026-02-23 07:20:29'),
  ('fin.events_hourly', '2026-02-23 07:00:00', '2026-02-23 07:22:25'),
  ('lake.search_weekday', '2026-02-23 07:15:00', '2026-02-23 07:54:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-02-23 06:45:00', '2026-02-23 08:01:32'),
  ('FIN.EVENTS_HOURLY', '2026-02-23 08:00:00', '2026-02-23 08:09:51'),
  ('ana.fraud_hourly', '2026-02-23 07:45:00', '2026-02-23 08:18:45'),
  ('lake.clicks-daily', '2026-02-23 08:20:00', '2026-02-23 08:45:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-23 09:00:00', '2026-02-23 09:10:30'),
  ('ANA.FRAUD_HOURLY', '2026-02-23 08:45:00', '2026-02-23 09:15:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-02-23 10:15:00', '2026-02-23 10:16:58'),
  ('ana.fraud_hourly', '2026-02-23 09:45:00', '2026-02-23 10:20:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-23 10:00:00', '2026-02-23 10:23:20'),
  ('leg.exports_daily', '2026-02-23 10:05:00', '2026-02-23 10:42:35'),
  ('ana.fraud_hourly', '2026-02-23 10:45:00', '2026-02-23 11:13:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-23 11:00:00', '2026-02-23 11:46:44'),
  ('ana.renewals_four_hourly', '2026-02-23 11:30:00', '2026-02-23 11:56:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-23 11:45:00', '2026-02-23 12:03:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-23 12:45:00', '2026-02-23 13:12:50'),
  ('fin/events_hourly', '2026-02-23 13:00:00', '2026-02-23 13:42:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-23 14:00:00', '2026-02-23 14:07:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-23 14:15:00', '2026-02-23 14:18:55'),
  ('LEG.QUOTES_DAILY', '2026-02-23 13:00:00', '2026-02-23 14:21:57'),
  ('ana.fraud_hourly', '2026-02-23 13:45:00', '2026-02-23 14:51:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-23 15:00:00', '2026-02-23 15:07:20'),
  ('ana/renewals_four_hourly', '2026-02-23 15:30:00', '2026-02-23 15:54:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-02-23 16:15:00', '2026-02-23 16:16:54'),
  ('ana.churn_daily', '2026-02-23 13:30:00', '2026-02-23 16:22:59'),
  ('fin.events_hourly', '2026-02-23 16:00:00', '2026-02-23 16:49:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-23 16:45:00', '2026-02-23 17:06:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-23 17:45:00', '2026-02-23 18:02:57'),
  ('FIN.EVENTS_HOURLY', '2026-02-23 18:00:00', '2026-02-23 18:11:23'),
  ('leg.tickets_four_hourly', '2026-02-23 18:15:00', '2026-02-23 18:17:17'),
  ('ana.shipments_weekday1', '2026-02-23 19:15:00', '2026-02-23 19:17:41'),
  ('fin.events_hourly', '2026-02-23 19:00:00', '2026-02-23 19:24:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/search_daily', '2026-02-23 19:15:00', '2026-02-23 19:36:27'),
  ('ana.fraud_hourly', '2026-02-23 19:45:00', '2026-02-23 20:12:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-23 20:45:00', '2026-02-23 20:57:53'),
  ('fin.events_hourly', '2026-02-23 21:00:00', '2026-02-23 21:11:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-23 21:45:00', '2026-02-23 22:03:07'),
  ('leg.tickets_four_hourly', '2026-02-23 22:15:00', '2026-02-23 22:16:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-23 22:00:00', '2026-02-23 22:30:06'),
  ('ana.fraud_hourly', '2026-02-23 22:45:00', '2026-02-23 23:18:55'),
  ('fin.events_hourly', '2026-02-23 23:00:00', '2026-02-23 23:20:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-23 23:30:00', '2026-02-23 23:51:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-23 23:45:00', '2026-02-24 00:00:54'),
  ('fin.events_hourly', '2026-02-24 00:00:00', '2026-02-24 00:14:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-24 00:45:00', '2026-02-24 01:08:00'),
  ('FIN.EVENTS_HOURLY', '2026-02-24 01:00:00', '2026-02-24 01:21:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-02-24 01:10:00', '2026-02-24 01:29:24'),
  ('ana.fraud_hourly', '2026-02-24 01:45:00', '2026-02-24 02:03:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-02-24 02:00:00', '2026-02-24 02:08:20'),
  ('leg.tickets_four_hourly', '2026-02-24 02:15:00', '2026-02-24 02:17:05'),
  ('lake.alerts_daily', '2026-02-24 03:00:00', '2026-02-24 03:01:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-24 02:45:00', '2026-02-24 03:06:01'),
  ('fin.ads_weekday', '2026-02-24 02:10:00', '2026-02-24 03:20:24'),
  ('fin.events_hourly', '2026-02-24 03:00:00', '2026-02-24 03:22:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-24 03:30:00', '2026-02-24 03:54:24'),
  ('ana.fraud-hourly', '2026-02-24 03:45:00', '2026-02-24 04:19:49'),
  ('fin.events_hourly', '2026-02-24 04:00:00', '2026-02-24 04:24:10'),
  ('ana.limits_weekday', '2026-02-24 04:20:00', '2026-02-24 04:39:08'),
  ('fin/events_hourly', '2026-02-24 05:00:00', '2026-02-24 05:16:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.catalog_weekday', '2026-02-24 04:45:00', '2026-02-24 05:44:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-24 05:45:00', '2026-02-24 05:55:11'),
  ('fin.refunds_daily', '2026-02-24 05:45:00', '2026-02-24 06:15:56'),
  ('leg.tickets_four_hourly', '2026-02-24 06:15:00', '2026-02-24 06:18:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-24 06:45:00', '2026-02-24 07:11:32'),
  ('fin.events_hourly', '2026-02-24 07:00:00', '2026-02-24 07:27:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-02-24 07:30:00', '2026-02-24 08:03:04'),
  ('ana.fraud_hourly', '2026-02-24 07:45:00', '2026-02-24 08:04:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-24 08:00:00', '2026-02-24 08:12:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LAKE.CLICKS_DAILY', '2026-02-24 08:20:00', '2026-02-24 08:39:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-02-24 07:15:00', '2026-02-24 08:52:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-24 09:00:00', '2026-02-24 09:26:39'),
  ('ana.fraud_hourly', '2026-02-24 09:45:00', '2026-02-24 10:08:45'),
  ('ANA.FRAUD_HOURLY', '2026-02-24 10:45:00', '2026-02-24 11:03:54'),
  ('fin.events_hourly', '2026-02-24 11:00:00', '2026-02-24 11:38:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-24 11:45:00', '2026-02-24 12:08:52'),
  ('fin.events_hourly', '2026-02-24 12:00:00', '2026-02-24 12:26:31'),
  ('ana.fraud_hourly', '2026-02-24 12:45:00', '2026-02-24 13:04:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-24 13:00:00', '2026-02-24 13:27:51'),
  ('leg.quotes_daily', '2026-02-24 13:00:00', '2026-02-24 13:29:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-24 14:00:00', '2026-02-24 14:25:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-24 14:15:00', '2026-02-24 14:29:39'),
  ('leg.tickets_weekday', '2026-02-24 13:20:00', '2026-02-24 14:47:07'),
  ('fin.events-hourly', '2026-02-24 15:00:00', '2026-02-24 15:11:00'),
  ('ana.churn_daily', '2026-02-24 13:30:00', '2026-02-24 15:20:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-24 14:45:00', '2026-02-24 16:04:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-02-24 16:15:00', '2026-02-24 16:17:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-24 16:00:00', '2026-02-24 16:52:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-24 17:00:00', '2026-02-24 17:10:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-24 16:45:00', '2026-02-24 17:11:38'),
  ('ana.fraud-hourly', '2026-02-24 17:45:00', '2026-02-24 17:55:50'),
  ('leg.tickets_four_hourly', '2026-02-24 18:15:00', '2026-02-24 18:17:21'),
  ('leg.forecast_daily', '2026-02-24 18:05:00', '2026-02-24 18:33:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-24 18:45:00', '2026-02-24 18:58:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-02-24 19:15:00', '2026-02-24 19:17:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-02-24 19:00:00', '2026-02-24 19:23:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-02-24 19:15:00', '2026-02-24 19:31:57'),
  ('ana.renewals_four_hourly', '2026-02-24 19:30:00', '2026-02-24 19:46:57'),
  ('fin.events_hourly', '2026-02-24 20:00:00', '2026-02-24 20:40:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-24 21:00:00', '2026-02-24 21:09:28'),
  ('ana.fraud_hourly', '2026-02-24 21:45:00', '2026-02-24 22:14:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-24 22:15:00', '2026-02-24 22:27:45'),
  ('fin.events_hourly', '2026-02-24 22:00:00', '2026-02-24 22:29:33'),
  ('ana.fraud-hourly', '2026-02-24 22:45:00', '2026-02-24 23:05:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-02-24 23:00:00', '2026-02-24 23:10:44'),
  ('ana.renewals_four_hourly', '2026-02-24 23:30:00', '2026-02-24 23:50:13'),
  ('ana.fraud_hourly', '2026-02-24 23:45:00', '2026-02-24 23:59:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-25 00:00:00', '2026-02-25 00:25:05'),
  ('fin.events_hourly', '2026-02-25 01:00:00', '2026-02-25 01:09:38'),
  ('ana.fraud_hourly', '2026-02-25 00:45:00', '2026-02-25 01:11:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-02-25 01:10:00', '2026-02-25 01:46:26'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-02-25 02:15:00', '2026-02-25 02:15:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-02-25 01:45:00', '2026-02-25 02:20:11'),
  ('lake.alerts_daily', '2026-02-25 03:00:00', '2026-02-25 03:01:31'),
  ('ana.fraud_hourly', '2026-02-25 02:45:00', '2026-02-25 03:03:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-25 03:00:00', '2026-02-25 03:17:27'),
  ('ana.renewals_four_hourly', '2026-02-25 03:30:00', '2026-02-25 03:41:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-25 03:45:00', '2026-02-25 03:53:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-25 04:00:00', '2026-02-25 04:27:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-25 04:45:00', '2026-02-25 05:05:38'),
  ('fin.events_hourly', '2026-02-25 05:00:00', '2026-02-25 05:22:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-02-25 05:45:00', '2026-02-25 06:05:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-25 06:15:00', '2026-02-25 06:16:58'),
  ('ana.limits_weekday', '2026-02-25 04:20:00', '2026-02-25 06:17:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-25 06:45:00', '2026-02-25 07:01:26'),
  ('ana.fraud_hourly', '2026-02-25 05:45:00', '2026-02-25 07:21:06'),
  ('fin.events_hourly', '2026-02-25 07:00:00', '2026-02-25 07:22:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-02-25 07:45:00', '2026-02-25 07:56:07'),
  ('ana.renewals-four-hourly', '2026-02-25 07:30:00', '2026-02-25 08:16:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-02-25 08:00:00', '2026-02-25 08:20:58'),
  ('lake.search_weekday', '2026-02-25 07:15:00', '2026-02-25 08:21:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-02-25 08:20:00', '2026-02-25 08:26:59'),
  ('ana.fraud_hourly', '2026-02-25 08:45:00', '2026-02-25 09:06:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-02-25 09:00:00', '2026-02-25 09:10:10'),
  ('lake.events_weekday', '2026-02-25 07:30:00', '2026-02-25 09:42:39'),
  ('ANA.FRAUD_HOURLY', '2026-02-25 09:45:00', '2026-02-25 10:12:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-25 10:00:00', '2026-02-25 10:25:14'),
  ('leg/exports_daily', '2026-02-25 10:05:00', '2026-02-25 10:50:30'),
  ('fin.events_hourly', '2026-02-25 11:00:00', '2026-02-25 11:10:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-25 10:45:00', '2026-02-25 11:12:28'),
  ('ana.renewals_four_hourly', '2026-02-25 11:30:00', '2026-02-25 11:54:49'),
  ('ana.fraud-hourly', '2026-02-25 11:45:00', '2026-02-25 12:18:08'),
  ('fin.events_hourly', '2026-02-25 12:00:00', '2026-02-25 12:24:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-25 13:00:00', '2026-02-25 13:15:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-25 12:45:00', '2026-02-25 13:18:16'),
  ('fin.events_hourly', '2026-02-25 14:00:00', '2026-02-25 14:14:28'),
  ('ana.fraud_hourly', '2026-02-25 13:45:00', '2026-02-25 14:17:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-02-25 13:20:00', '2026-02-25 14:56:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-25 14:45:00', '2026-02-25 15:07:08'),
  ('fin.events_hourly', '2026-02-25 15:00:00', '2026-02-25 15:10:52'),
  ('ana.renewals_four_hourly', '2026-02-25 15:30:00', '2026-02-25 15:56:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-25 16:00:00', '2026-02-25 16:14:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-02-25 16:15:00', '2026-02-25 16:18:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-25 15:45:00', '2026-02-25 16:33:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-25 17:00:00', '2026-02-25 17:33:49'),
  ('ana.fraud_hourly', '2026-02-25 17:45:00', '2026-02-25 17:59:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-02-25 18:05:00', '2026-02-25 18:13:56'),
  ('fin.events_hourly', '2026-02-25 18:00:00', '2026-02-25 19:04:08'),
  ('ana.shipments_weekday1', '2026-02-25 19:15:00', '2026-02-25 19:30:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-25 19:30:00', '2026-02-25 19:36:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-25 18:45:00', '2026-02-25 19:48:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-02-25 19:15:00', '2026-02-25 19:54:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-02-25 19:45:00', '2026-02-25 20:05:05'),
  ('fin.events_hourly', '2026-02-25 19:00:00', '2026-02-25 20:11:48'),
  ('fin.events_hourly', '2026-02-25 20:00:00', '2026-02-25 20:22:28'),
  ('ana/fraud_hourly', '2026-02-25 20:45:00', '2026-02-25 21:17:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-25 21:00:00', '2026-02-25 21:24:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-25 21:45:00', '2026-02-25 21:54:28'),
  ('leg.tickets-four-hourly', '2026-02-25 22:15:00', '2026-02-25 22:16:36'),
  ('fin.events_hourly', '2026-02-25 22:00:00', '2026-02-25 22:22:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-25 23:00:00', '2026-02-25 23:19:53'),
  ('ana.renewals_four_hourly', '2026-02-25 23:30:00', '2026-02-25 23:53:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-25 23:45:00', '2026-02-26 00:04:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-26 00:00:00', '2026-02-26 00:24:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-02-26 01:10:00', '2026-02-26 01:43:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-02-26 01:20:00', '2026-02-26 02:00:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-26 01:45:00', '2026-02-26 02:00:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-26 02:15:00', '2026-02-26 02:17:04'),
  ('fin.events_hourly', '2026-02-26 02:00:00', '2026-02-26 02:18:04'),
  ('ana.fraud_hourly', '2026-02-26 00:45:00', '2026-02-26 02:21:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-02-26 01:10:00', '2026-02-26 02:34:42'),
  ('lake.alerts_daily', '2026-02-26 03:00:00', '2026-02-26 03:02:38'),
  ('fin.events_hourly', '2026-02-26 03:00:00', '2026-02-26 03:08:24'),
  ('FIN.ADS_WEEKDAY', '2026-02-26 02:10:00', '2026-02-26 03:26:00'),
  ('ana.renewals_four_hourly', '2026-02-26 03:30:00', '2026-02-26 03:55:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-02-26 04:00:00', '2026-02-26 04:09:20'),
  ('ana.fraud_hourly', '2026-02-26 03:45:00', '2026-02-26 04:43:49'),
  ('ana/fraud_hourly', '2026-02-26 04:45:00', '2026-02-26 04:55:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-02-26 05:00:00', '2026-02-26 05:07:48'),
  ('fin.refunds_daily', '2026-02-26 05:45:00', '2026-02-26 06:10:06'),
  ('fin.events_hourly', '2026-02-26 06:00:00', '2026-02-26 06:12:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 05:45:00', '2026-02-26 06:46:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 06:45:00', '2026-02-26 07:11:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-26 07:00:00', '2026-02-26 07:13:25'),
  ('ana.renewals-four-hourly', '2026-02-26 07:30:00', '2026-02-26 07:49:40'),
  ('lake.search_weekday', '2026-02-26 07:15:00', '2026-02-26 07:57:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 07:45:00', '2026-02-26 08:00:07'),
  ('fin.events_hourly', '2026-02-26 08:00:00', '2026-02-26 08:25:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-02-26 08:20:00', '2026-02-26 08:32:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LAKE.EVENTS_WEEKDAY', '2026-02-26 07:30:00', '2026-02-26 08:40:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 08:45:00', '2026-02-26 08:55:43'),
  ('fin.events_hourly', '2026-02-26 10:00:00', '2026-02-26 10:07:23'),
  ('ana.fraud_hourly', '2026-02-26 09:45:00', '2026-02-26 10:09:13'),
  ('leg.tickets_four_hourly', '2026-02-26 10:15:00', '2026-02-26 10:17:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 10:45:00', '2026-02-26 11:09:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-26 11:00:00', '2026-02-26 11:19:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-02-26 10:05:00', '2026-02-26 11:30:41'),
  ('fin.events_hourly', '2026-02-26 12:00:00', '2026-02-26 12:28:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 11:45:00', '2026-02-26 12:49:45'),
  ('ana.fraud_hourly', '2026-02-26 12:45:00', '2026-02-26 12:56:57'),
  ('fin.events_hourly', '2026-02-26 13:00:00', '2026-02-26 13:19:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-02-26 13:00:00', '2026-02-26 13:48:57'),
  ('ana.fraud_hourly', '2026-02-26 13:45:00', '2026-02-26 14:05:44'),
  ('leg.tickets_weekday', '2026-02-26 13:20:00', '2026-02-26 14:13:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-26 14:15:00', '2026-02-26 14:34:29'),
  ('fin/events_hourly', '2026-02-26 15:00:00', '2026-02-26 15:24:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-26 15:30:00', '2026-02-26 15:56:25'),
  ('fin.events_hourly', '2026-02-26 16:00:00', '2026-02-26 16:06:37'),
  ('LAKE.ACCOUNTS_WEEKDAY', '2026-02-26 16:15:00', '2026-02-26 16:16:13'),
  ('leg/tickets_four_hourly', '2026-02-26 18:15:00', '2026-02-26 18:17:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 17:45:00', '2026-02-26 18:18:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-26 18:00:00', '2026-02-26 18:19:59'),
  ('ana.fraud_hourly', '2026-02-26 18:45:00', '2026-02-26 19:08:22'),
  ('leg.search_daily', '2026-02-26 19:15:00', '2026-02-26 20:01:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-02-26 19:30:00', '2026-02-26 20:06:23'),
  ('ana.fraud_hourly', '2026-02-26 19:45:00', '2026-02-26 20:08:19'),
  ('ana.fraud_hourly', '2026-02-26 20:45:00', '2026-02-26 21:02:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-26 21:00:00', '2026-02-26 21:14:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 21:45:00', '2026-02-26 22:00:02'),
  ('fin.events_hourly', '2026-02-26 22:00:00', '2026-02-26 22:10:05'),
  ('leg.tickets_four_hourly', '2026-02-26 22:15:00', '2026-02-26 22:17:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 22:45:00', '2026-02-26 23:11:09'),
  ('fin.events_hourly', '2026-02-26 23:00:00', '2026-02-26 23:17:15'),
  ('ana.renewals_four_hourly', '2026-02-26 23:30:00', '2026-02-26 23:53:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-26 23:45:00', '2026-02-26 23:57:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-02-27 01:10:00', '2026-02-27 01:31:20'),
  ('fin.events_hourly', '2026-02-27 01:00:00', '2026-02-27 01:34:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EXPORTS_DAILY', '2026-02-27 01:10:00', '2026-02-27 02:02:22'),
  ('leg/tickets_four_hourly', '2026-02-27 02:15:00', '2026-02-27 02:17:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-02-27 01:20:00', '2026-02-27 02:21:48'),
  ('ana.fraud_hourly', '2026-02-27 01:45:00', '2026-02-27 02:32:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-02-27 02:10:00', '2026-02-27 02:57:22'),
  ('ana/fraud_hourly', '2026-02-27 02:45:00', '2026-02-27 03:02:05'),
  ('lake.alerts_daily', '2026-02-27 03:00:00', '2026-02-27 03:02:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-27 03:45:00', '2026-02-27 04:02:48'),
  ('fin.events-hourly', '2026-02-27 04:00:00', '2026-02-27 04:10:52'),
  ('ana.limits_weekday', '2026-02-27 04:20:00', '2026-02-27 05:26:41'),
  ('FIN.CATALOG_WEEKDAY', '2026-02-27 04:45:00', '2026-02-27 05:48:54'),
  ('ana.fraud_hourly', '2026-02-27 04:45:00', '2026-02-27 05:53:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-27 05:45:00', '2026-02-27 05:56:04'),
  ('leg.tickets_four_hourly', '2026-02-27 06:15:00', '2026-02-27 06:18:25'),
  ('fin.events_hourly', '2026-02-27 06:00:00', '2026-02-27 06:24:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-02-27 05:45:00', '2026-02-27 06:35:01'),
  ('ana.fraud_hourly', '2026-02-27 06:45:00', '2026-02-27 07:13:45'),
  ('fin/events_hourly', '2026-02-27 07:00:00', '2026-02-27 07:18:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-27 07:30:00', '2026-02-27 07:56:06'),
  ('ana.fraud_hourly', '2026-02-27 07:45:00', '2026-02-27 08:10:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-02-27 07:30:00', '2026-02-27 08:11:41'),
  ('lake.search_weekday', '2026-02-27 07:15:00', '2026-02-27 08:26:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 08:00:00', '2026-02-27 08:28:03'),
  ('lake.clicks_daily', '2026-02-27 08:20:00', '2026-02-27 08:54:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 09:00:00', '2026-02-27 09:15:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-27 09:45:00', '2026-02-27 10:06:20'),
  ('leg.tickets_four_hourly', '2026-02-27 10:15:00', '2026-02-27 10:16:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 10:00:00', '2026-02-27 10:18:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-02-27 10:05:00', '2026-02-27 11:14:32'),
  ('ana.fraud_hourly', '2026-02-27 10:45:00', '2026-02-27 11:15:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 11:00:00', '2026-02-27 11:19:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-27 11:30:00', '2026-02-27 11:36:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-27 11:45:00', '2026-02-27 12:07:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/search_weekly', '2026-02-27 13:05:00', '2026-02-27 13:24:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-02-27 13:00:00', '2026-02-27 13:39:40'),
  ('ana.fraud_hourly', '2026-02-27 12:45:00', '2026-02-27 13:40:29'),
  ('leg.tickets_weekday', '2026-02-27 13:20:00', '2026-02-27 13:52:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-02-27 13:45:00', '2026-02-27 14:02:34'),
  ('ana.churn_daily', '2026-02-27 13:30:00', '2026-02-27 14:16:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-27 14:15:00', '2026-02-27 14:16:48'),
  ('fin.events_hourly', '2026-02-27 14:00:00', '2026-02-27 14:32:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 15:00:00', '2026-02-27 15:10:09'),
  ('ana.fraud_hourly', '2026-02-27 14:45:00', '2026-02-27 15:19:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-02-27 16:15:00', '2026-02-27 16:17:21'),
  ('fin.events_hourly', '2026-02-27 16:00:00', '2026-02-27 16:22:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-27 15:30:00', '2026-02-27 16:44:18'),
  ('fin.events_hourly', '2026-02-27 17:00:00', '2026-02-27 17:25:19'),
  ('ANA.FRAUD_HOURLY', '2026-02-27 17:45:00', '2026-02-27 18:00:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-02-27 18:15:00', '2026-02-27 18:18:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 18:00:00', '2026-02-27 18:22:18'),
  ('leg.forecast_daily', '2026-02-27 18:05:00', '2026-02-27 18:27:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 19:00:00', '2026-02-27 19:06:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-27 18:45:00', '2026-02-27 19:17:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-02-27 19:15:00', '2026-02-27 20:04:32'),
  ('FIN.EVENTS_HOURLY', '2026-02-27 20:00:00', '2026-02-27 20:25:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 21:00:00', '2026-02-27 21:09:58'),
  ('ana.fraud_hourly', '2026-02-27 20:45:00', '2026-02-27 21:19:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 22:00:00', '2026-02-27 22:10:37'),
  ('ana.fraud_hourly', '2026-02-27 21:45:00', '2026-02-27 22:15:59'),
  ('leg.tickets_four_hourly', '2026-02-27 22:15:00', '2026-02-27 22:16:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-27 23:00:00', '2026-02-27 23:24:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-27 23:45:00', '2026-02-28 00:11:05'),
  ('FIN.EVENTS_HOURLY', '2026-02-28 00:00:00', '2026-02-28 00:14:51'),
  ('ana.fraud_hourly', '2026-02-28 00:45:00', '2026-02-28 01:07:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-28 01:00:00', '2026-02-28 01:11:36'),
  ('fin.inventory_daily', '2026-02-28 01:10:00', '2026-02-28 01:22:45'),
  ('leg.tickets_four_hourly', '2026-02-28 02:15:00', '2026-02-28 02:18:20'),
  ('fin.events_hourly', '2026-02-28 02:00:00', '2026-02-28 02:19:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-02-28 01:10:00', '2026-02-28 02:32:16'),
  ('lake/alerts_daily', '2026-02-28 03:00:00', '2026-02-28 03:01:26'),
  ('ana.fraud_hourly', '2026-02-28 02:45:00', '2026-02-28 03:11:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-28 01:45:00', '2026-02-28 03:11:38'),
  ('fin.events_hourly', '2026-02-28 03:00:00', '2026-02-28 03:27:13'),
  ('ana.renewals_four_hourly', '2026-02-28 03:30:00', '2026-02-28 03:50:08'),
  ('fin.events_hourly', '2026-02-28 04:00:00', '2026-02-28 05:07:46'),
  ('fin.events_hourly', '2026-02-28 05:00:00', '2026-02-28 05:08:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-28 04:45:00', '2026-02-28 05:35:53'),
  ('ana.fraud_hourly', '2026-02-28 05:45:00', '2026-02-28 05:59:26'),
  ('fin.refunds_daily', '2026-02-28 05:45:00', '2026-02-28 06:20:24'),
  ('ana.fraud_hourly', '2026-02-28 06:45:00', '2026-02-28 06:55:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-02-28 07:30:00', '2026-02-28 07:40:52'),
  ('fin.events-hourly', '2026-02-28 07:00:00', '2026-02-28 07:42:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-28 08:00:00', '2026-02-28 08:21:36'),
  ('lake.clicks_daily', '2026-02-28 08:20:00', '2026-02-28 08:55:29'),
  ('ana.fraud_hourly', '2026-02-28 07:45:00', '2026-02-28 09:22:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-28 09:45:00', '2026-02-28 10:13:57'),
  ('leg/tickets_four_hourly', '2026-02-28 10:15:00', '2026-02-28 10:17:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-28 10:00:00', '2026-02-28 10:19:26'),
  ('ana.fraud_hourly', '2026-02-28 10:45:00', '2026-02-28 11:15:15'),
  ('fin.events_hourly', '2026-02-28 11:00:00', '2026-02-28 11:34:12'),
  ('ana.renewals_four_hourly', '2026-02-28 11:30:00', '2026-02-28 11:37:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-28 12:00:00', '2026-02-28 12:48:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-28 12:45:00', '2026-02-28 13:07:53'),
  ('fin.events_hourly', '2026-02-28 13:00:00', '2026-02-28 13:08:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-02-28 11:45:00', '2026-02-28 13:08:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-02-28 13:00:00', '2026-02-28 13:38:26'),
  ('leg.tickets_four_hourly', '2026-02-28 14:15:00', '2026-02-28 14:18:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-02-28 14:00:00', '2026-02-28 14:58:50'),
  ('FIN.EVENTS_HOURLY', '2026-02-28 15:00:00', '2026-02-28 15:08:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-02-28 13:30:00', '2026-02-28 15:10:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-02-28 13:45:00', '2026-02-28 15:23:14'),
  ('fin.events_hourly', '2026-02-28 16:00:00', '2026-02-28 16:57:28'),
  ('ana.fraud_hourly', '2026-02-28 17:45:00', '2026-02-28 18:00:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-28 18:00:00', '2026-02-28 18:10:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-28 19:00:00', '2026-02-28 19:07:47'),
  ('ana.fraud_hourly', '2026-02-28 18:45:00', '2026-02-28 19:10:58'),
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-02-28 19:30:00', '2026-02-28 19:53:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-02-28 19:45:00', '2026-02-28 20:05:52'),
  ('fin.events_hourly', '2026-02-28 20:00:00', '2026-02-28 20:24:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-02-28 20:45:00', '2026-02-28 21:18:00'),
  ('fin.events_hourly', '2026-02-28 21:00:00', '2026-02-28 22:07:30'),
  ('fin.events_hourly', '2026-02-28 22:00:00', '2026-02-28 22:11:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets-four-hourly', '2026-02-28 22:15:00', '2026-02-28 22:16:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-02-28 23:00:00', '2026-02-28 23:06:52'),
  ('ana.fraud_hourly', '2026-02-28 22:45:00', '2026-02-28 23:10:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-02-28 23:30:00', '2026-02-28 23:38:14'),
  ('FIN.EVENTS_HOURLY', '2026-03-01 00:00:00', '2026-03-01 00:22:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-01 00:45:00', '2026-03-01 00:53:20'),
  ('FIN.EVENTS_HOURLY', '2026-03-01 01:00:00', '2026-03-01 01:07:02'),
  ('lake.audits_twice_monthly', '2026-03-01 00:00:00', '2026-03-01 01:33:31'),
  ('fin.exports_daily', '2026-03-01 01:10:00', '2026-03-01 02:17:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-01 02:00:00', '2026-03-01 02:19:23'),
  ('leg.tickets_four_hourly', '2026-03-01 02:15:00', '2026-03-01 02:22:05'),
  ('fin.inventory_daily', '2026-03-01 01:10:00', '2026-03-01 02:28:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-01 01:20:00', '2026-03-01 02:40:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-01 03:00:00', '2026-03-01 03:01:50'),
  ('ana.fraud_hourly', '2026-03-01 02:45:00', '2026-03-01 03:11:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-01 03:00:00', '2026-03-01 03:19:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-01 03:45:00', '2026-03-01 04:51:24'),
  ('fin/events_hourly', '2026-03-01 05:00:00', '2026-03-01 05:25:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-01 05:45:00', '2026-03-01 06:06:20'),
  ('fin.events_hourly', '2026-03-01 06:00:00', '2026-03-01 06:11:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-01 06:15:00', '2026-03-01 06:15:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/refunds_daily', '2026-03-01 05:45:00', '2026-03-01 06:24:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-01 07:00:00', '2026-03-01 07:17:04'),
  ('ana.fraud_hourly', '2026-03-01 07:45:00', '2026-03-01 08:11:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-01 08:00:00', '2026-03-01 08:11:23'),
  ('ana.fraud_hourly', '2026-03-01 06:45:00', '2026-03-01 08:15:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-01 07:30:00', '2026-03-01 08:27:30'),
  ('lake.clicks_daily', '2026-03-01 08:20:00', '2026-03-01 08:32:35'),
  ('fin.events_hourly', '2026-03-01 09:00:00', '2026-03-01 09:21:11'),
  ('ana.fraud_hourly', '2026-03-01 09:45:00', '2026-03-01 10:11:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-01 10:00:00', '2026-03-01 10:14:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-01 10:15:00', '2026-03-01 10:16:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-03-01 10:05:00', '2026-03-01 10:39:12'),
  ('ana.fraud_hourly', '2026-03-01 10:45:00', '2026-03-01 11:55:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-01 11:00:00', '2026-03-01 11:57:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-01 12:00:00', '2026-03-01 12:14:42'),
  ('ana.fraud_hourly', '2026-03-01 12:45:00', '2026-03-01 12:55:38'),
  ('fin.events_hourly', '2026-03-01 13:00:00', '2026-03-01 13:21:38'),
  ('leg.quotes_daily', '2026-03-01 13:00:00', '2026-03-01 13:33:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-01 13:45:00', '2026-03-01 14:11:18'),
  ('leg.tickets_four_hourly', '2026-03-01 14:15:00', '2026-03-01 14:18:09'),
  ('fin.events_hourly', '2026-03-01 14:00:00', '2026-03-01 14:48:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-01 14:45:00', '2026-03-01 15:10:16'),
  ('fin.events_hourly', '2026-03-01 15:00:00', '2026-03-01 15:10:41'),
  ('ana.renewals_four_hourly', '2026-03-01 15:30:00', '2026-03-01 15:43:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-03-01 13:30:00', '2026-03-01 16:45:32'),
  ('fin.events_hourly', '2026-03-01 17:00:00', '2026-03-01 17:12:52'),
  ('ana.fraud-hourly', '2026-03-01 16:45:00', '2026-03-01 17:18:14'),
  ('ana.fraud_hourly', '2026-03-01 17:45:00', '2026-03-01 18:03:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-01 18:00:00', '2026-03-01 18:11:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets-four-hourly', '2026-03-01 18:15:00', '2026-03-01 18:18:56'),
  ('ANA.FRAUD_HOURLY', '2026-03-01 18:45:00', '2026-03-01 18:58:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-01 19:15:00', '2026-03-01 19:18:12'),
  ('fin.events_hourly', '2026-03-01 19:00:00', '2026-03-01 19:19:21'),
  ('leg.search_daily', '2026-03-01 19:15:00', '2026-03-01 20:10:58'),
  ('FIN.EVENTS_HOURLY', '2026-03-01 20:00:00', '2026-03-01 20:21:57'),
  ('ana.renewals_four_hourly', '2026-03-01 19:30:00', '2026-03-01 20:22:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-01 20:45:00', '2026-03-01 20:53:20'),
  ('ana.fraud_hourly', '2026-03-01 21:45:00', '2026-03-01 22:12:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-01 22:00:00', '2026-03-01 22:16:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-01 23:30:00', '2026-03-02 00:09:40'),
  ('fin.events_hourly', '2026-03-02 00:00:00', '2026-03-02 00:19:54'),
  ('ana.fraud_hourly', '2026-03-02 00:45:00', '2026-03-02 00:59:12'),
  ('ana.fraud_hourly', '2026-03-01 23:45:00', '2026-03-02 01:12:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 01:00:00', '2026-03-02 01:21:31'),
  ('fin.events_hourly', '2026-03-02 02:00:00', '2026-03-02 02:10:53'),
  ('fin.exports_daily', '2026-03-02 01:10:00', '2026-03-02 02:14:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-02 02:15:00', '2026-03-02 02:18:15'),
  ('ana.fraud-hourly', '2026-03-02 01:45:00', '2026-03-02 02:48:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-02 02:45:00', '2026-03-02 02:55:10'),
  ('fin.renewals_daily', '2026-03-02 01:20:00', '2026-03-02 02:58:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LAKE.ALERTS_DAILY', '2026-03-02 03:00:00', '2026-03-02 03:02:56'),
  ('fin.ads_weekday', '2026-03-02 02:10:00', '2026-03-02 03:17:03'),
  ('fin.events_hourly', '2026-03-02 03:00:00', '2026-03-02 03:17:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.audits-twice-monthly', '2026-03-02 00:00:00', '2026-03-02 03:30:00'),
  ('ana.renewals_four_hourly', '2026-03-02 03:30:00', '2026-03-02 03:54:43'),
  ('fin.inventory-daily', '2026-03-02 01:10:00', '2026-03-02 03:55:00'),
  ('fin.events-hourly', '2026-03-02 04:00:00', '2026-03-02 04:37:31'),
  ('ana/fraud_hourly', '2026-03-02 02:45:00', '2026-03-02 05:09:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.LIMITS_WEEKDAY', '2026-03-02 04:20:00', '2026-03-02 05:12:50'),
  ('fin.events_hourly', '2026-03-02 05:00:00', '2026-03-02 05:24:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 06:00:00', '2026-03-02 06:11:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets-four-hourly', '2026-03-02 06:15:00', '2026-03-02 06:16:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-02 03:00:00', '2026-03-02 07:01:02'),
  ('fin.events_hourly', '2026-03-02 07:00:00', '2026-03-02 07:07:53'),
  ('ana/renewals_four_hourly', '2026-03-02 07:30:00', '2026-03-02 08:08:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-02 08:00:00', '2026-03-02 08:28:36'),
  ('lake.search_weekday', '2026-03-02 07:15:00', '2026-03-02 08:43:27'),
  ('ana.fraud_hourly', '2026-03-02 07:45:00', '2026-03-02 08:55:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-02 08:45:00', '2026-03-02 09:02:18'),
  ('FIN.EVENTS_HOURLY', '2026-03-02 09:00:00', '2026-03-02 09:11:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-03-02 07:30:00', '2026-03-02 09:26:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 10:00:00', '2026-03-02 10:20:27'),
  ('fin.events-hourly', '2026-03-02 11:00:00', '2026-03-02 11:26:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-02 11:45:00', '2026-03-02 12:03:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 12:00:00', '2026-03-02 12:12:42'),
  ('lake.clicks_daily', '2026-03-02 08:20:00', '2026-03-02 12:16:12'),
  ('ana.fraud_hourly', '2026-03-02 12:45:00', '2026-03-02 13:15:29'),
  ('ana.fraud_hourly', '2026-03-02 10:45:00', '2026-03-02 13:25:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes-daily', '2026-03-02 13:00:00', '2026-03-02 13:27:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 13:00:00', '2026-03-02 14:03:30'),
  ('leg.tickets_four_hourly', '2026-03-02 14:15:00', '2026-03-02 14:15:55'),
  ('fin.events_hourly', '2026-03-02 14:00:00', '2026-03-02 14:23:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('ana.fraud_hourly', '2026-03-02 14:45:00', '2026-03-02 15:05:14'),
  ('fin.events-hourly', '2026-03-02 15:00:00', '2026-03-02 15:10:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-03-02 13:30:00', '2026-03-02 15:24:52'),
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-02 15:30:00', '2026-03-02 15:47:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-02 15:45:00', '2026-03-02 16:00:23'),
  ('fin.events_hourly', '2026-03-02 16:00:00', '2026-03-02 16:13:18'),
  ('lake.accounts_weekday', '2026-03-02 16:15:00', '2026-03-02 16:17:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-02 16:00:00', '2026-03-02 16:55:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-02 08:20:00', '2026-03-02 17:09:13'),
  ('fin.events_hourly', '2026-03-02 17:00:00', '2026-03-02 17:13:47'),
  ('ana.fraud_hourly', '2026-03-02 16:45:00', '2026-03-02 17:16:52'),
  ('ana.fraud_hourly', '2026-03-02 17:45:00', '2026-03-02 18:07:37'),
  ('leg/tickets_four_hourly', '2026-03-02 18:15:00', '2026-03-02 18:16:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 18:00:00', '2026-03-02 18:16:40'),
  ('ana.fraud_hourly', '2026-03-02 17:45:00', '2026-03-02 18:52:58'),
  ('ana.shipments_weekday1', '2026-03-02 19:15:00', '2026-03-02 19:17:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 19:00:00', '2026-03-02 19:17:18'),
  ('fin.events_hourly', '2026-03-02 20:00:00', '2026-03-02 20:12:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-02 19:30:00', '2026-03-02 20:27:13'),
  ('ana.fraud_hourly', '2026-03-02 19:45:00', '2026-03-02 20:27:40'),
  ('ana.fraud_hourly', '2026-03-02 20:45:00', '2026-03-02 20:54:25'),
  ('FIN.EVENTS_HOURLY', '2026-03-02 21:00:00', '2026-03-02 21:17:59'),
  ('leg.tickets_four_hourly', '2026-03-02 22:15:00', '2026-03-02 22:16:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-02 18:15:00', '2026-03-02 22:17:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 22:00:00', '2026-03-02 23:06:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-02 22:45:00', '2026-03-02 23:11:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 23:00:00', '2026-03-02 23:35:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-02 23:30:00', '2026-03-02 23:46:51'),
  ('ana.fraud_hourly', '2026-03-02 23:45:00', '2026-03-03 00:16:53'),
  ('fin.events-hourly', '2026-03-03 00:00:00', '2026-03-03 00:17:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-03 00:45:00', '2026-03-03 01:10:04'),
  ('fin.events_hourly', '2026-03-03 01:00:00', '2026-03-03 01:24:50'),
  ('fin.inventory_daily', '2026-03-03 01:10:00', '2026-03-03 01:27:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-03 01:20:00', '2026-03-03 02:01:44'),
  ('leg.tickets_four_hourly', '2026-03-03 02:15:00', '2026-03-03 02:16:56'),
  ('ana.fraud_hourly', '2026-03-03 01:45:00', '2026-03-03 02:31:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-02 22:15:00', '2026-03-03 02:41:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-02 23:00:00', '2026-03-03 02:48:02'),
  ('ANA.FRAUD_HOURLY', '2026-03-03 02:45:00', '2026-03-03 02:54:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-03 03:00:00', '2026-03-03 03:01:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-03 02:00:00', '2026-03-03 03:03:16'),
  ('fin.events_hourly', '2026-03-03 03:00:00', '2026-03-03 03:16:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-03 02:10:00', '2026-03-03 03:26:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-03 03:30:00', '2026-03-03 04:09:36'),
  ('ana.fraud_hourly', '2026-03-03 03:45:00', '2026-03-03 04:20:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-03 04:00:00', '2026-03-03 04:23:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-03 02:15:00', '2026-03-03 04:39:30'),
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('ana.limits_weekday', '2026-03-03 04:20:00', '2026-03-03 04:45:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.CATALOG_WEEKDAY', '2026-03-03 04:45:00', '2026-03-03 05:00:32'),
  ('fin.events-hourly', '2026-03-03 05:00:00', '2026-03-03 05:08:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-03 01:10:00', '2026-03-03 05:13:46'),
  ('ana.fraud-hourly', '2026-03-03 05:45:00', '2026-03-03 06:04:05'),
  ('fin.refunds_daily', '2026-03-03 05:45:00', '2026-03-03 06:12:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-03 06:15:00', '2026-03-03 06:18:14'),
  ('fin.events_hourly', '2026-03-03 06:00:00', '2026-03-03 06:19:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-03 06:45:00', '2026-03-03 07:13:05'),
  ('fin/events_hourly', '2026-03-03 07:00:00', '2026-03-03 07:23:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals-four-hourly', '2026-03-03 07:30:00', '2026-03-03 07:36:04'),
  ('lake.events_weekday', '2026-03-03 07:30:00', '2026-03-03 07:46:12'),
  ('lake.search-weekday', '2026-03-03 07:15:00', '2026-03-03 07:53:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-03 08:00:00', '2026-03-03 08:14:56'),
  ('ana.fraud_hourly', '2026-03-03 07:45:00', '2026-03-03 08:19:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks-daily', '2026-03-03 08:20:00', '2026-03-03 08:27:32'),
  ('ana.fraud_hourly', '2026-03-03 08:45:00', '2026-03-03 09:16:24'),
  ('fin/events_hourly', '2026-03-03 09:00:00', '2026-03-03 09:27:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-03 10:00:00', '2026-03-03 10:11:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-03 09:45:00', '2026-03-03 10:12:28'),
  ('leg.tickets_four_hourly', '2026-03-03 10:15:00', '2026-03-03 10:16:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-03-03 10:05:00', '2026-03-03 10:26:16'),
  ('fin.events_hourly', '2026-03-03 11:00:00', '2026-03-03 11:12:05'),
  ('ana.renewals_four_hourly', '2026-03-03 11:30:00', '2026-03-03 11:41:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-03 11:45:00', '2026-03-03 12:14:05'),
  ('ana.fraud_hourly', '2026-03-03 07:45:00', '2026-03-03 12:18:51'),
  ('fin.events_hourly', '2026-03-03 12:00:00', '2026-03-03 12:39:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-03 12:45:00', '2026-03-03 12:54:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-03 13:00:00', '2026-03-03 13:34:12'),
  ('leg.tickets_four_hourly', '2026-03-03 14:15:00', '2026-03-03 14:17:04'),
  ('fin/events_hourly', '2026-03-03 14:00:00', '2026-03-03 14:22:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-03 13:20:00', '2026-03-03 14:30:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-03 14:45:00', '2026-03-03 15:07:24'),
  ('fin.events_hourly', '2026-03-03 15:00:00', '2026-03-03 15:08:33'),
  ('fin.events_hourly', '2026-03-03 13:00:00', '2026-03-03 15:30:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.CHURN_DAILY', '2026-03-03 13:30:00', '2026-03-03 16:02:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-03 15:45:00', '2026-03-03 16:11:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-03-03 16:15:00', '2026-03-03 16:17:48'),
  ('ana.fraud_hourly', '2026-03-03 16:45:00', '2026-03-03 16:54:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-03 13:00:00', '2026-03-03 16:58:36'),
  ('fin.events_hourly', '2026-03-03 17:00:00', '2026-03-03 17:22:48'),
  ('leg.forecast_daily', '2026-03-03 18:05:00', '2026-03-03 18:12:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-03 17:45:00', '2026-03-03 18:13:48'),
  ('fin.events_hourly', '2026-03-03 18:00:00', '2026-03-03 18:19:21'),
  ('fin.events_hourly', '2026-03-03 17:00:00', '2026-03-03 18:35:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-03-03 18:05:00', '2026-03-03 18:48:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-03 18:45:00', '2026-03-03 19:03:42'),
  ('ana.shipments_weekday1', '2026-03-03 19:15:00', '2026-03-03 19:16:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-03-03 19:15:00', '2026-03-03 19:54:26'),
  ('fin.events_hourly', '2026-03-03 15:00:00', '2026-03-03 19:57:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-03 19:00:00', '2026-03-03 20:11:48'),
  ('ana.fraud_hourly', '2026-03-03 20:45:00', '2026-03-03 20:53:32'),
  ('fin.events_hourly', '2026-03-03 21:00:00', '2026-03-03 21:19:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-03 19:45:00', '2026-03-03 21:19:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-03 22:00:00', '2026-03-03 22:14:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-03 21:45:00', '2026-03-03 22:55:01'),
  ('ana.renewals_four_hourly', '2026-03-03 23:30:00', '2026-03-03 23:55:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-03 22:45:00', '2026-03-03 23:55:34'),
  ('ana.fraud_hourly', '2026-03-03 23:45:00', '2026-03-04 00:00:14'),
  ('fin.events_hourly', '2026-03-04 00:00:00', '2026-03-04 00:17:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-04 00:45:00', '2026-03-04 01:05:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-04 01:10:00', '2026-03-04 01:31:08'),
  ('fin.renewals_daily', '2026-03-04 01:20:00', '2026-03-04 01:46:13'),
  ('ana.fraud_hourly', '2026-03-04 01:45:00', '2026-03-04 02:12:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-04 02:00:00', '2026-03-04 02:12:32'),
  ('leg.tickets_four_hourly', '2026-03-04 02:15:00', '2026-03-04 02:17:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-04 03:00:00', '2026-03-04 03:17:44'),
  ('fin.inventory_daily', '2026-03-04 01:10:00', '2026-03-04 03:26:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-04 02:10:00', '2026-03-04 03:30:03'),
  ('ana.fraud-hourly', '2026-03-04 02:45:00', '2026-03-04 03:44:27'),
  ('ana.fraud_hourly', '2026-03-04 03:45:00', '2026-03-04 03:53:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.catalog_weekday', '2026-03-04 04:45:00', '2026-03-04 04:55:22'),
  ('ana.fraud_hourly', '2026-03-04 04:45:00', '2026-03-04 05:11:25'),
  ('fin.events_hourly', '2026-03-04 05:00:00', '2026-03-04 05:12:38'),
  ('ana.limits_weekday', '2026-03-04 04:20:00', '2026-03-04 05:35:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-04 05:45:00', '2026-03-04 05:57:06'),
  ('ana.fraud_hourly', '2026-03-04 05:45:00', '2026-03-04 06:04:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-04 06:15:00', '2026-03-04 06:17:05'),
  ('fin.events_hourly', '2026-03-04 06:00:00', '2026-03-04 06:23:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-04 05:45:00', '2026-03-04 06:45:22'),
  ('ana.fraud_hourly', '2026-03-04 06:45:00', '2026-03-04 06:57:27'),
  ('fin.events_hourly', '2026-03-04 07:00:00', '2026-03-04 07:20:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.limits_weekday', '2026-03-04 04:20:00', '2026-03-04 07:35:23'),
  ('ana.renewals_four_hourly', '2026-03-04 07:30:00', '2026-03-04 07:43:19'),
  ('fin.events_hourly', '2026-03-04 08:00:00', '2026-03-04 08:10:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search-weekday', '2026-03-04 07:15:00', '2026-03-04 08:23:32'),
  ('ana.fraud_hourly', '2026-03-04 08:45:00', '2026-03-04 08:59:14'),
  ('LAKE.EVENTS_WEEKDAY', '2026-03-04 07:30:00', '2026-03-04 09:03:04'),
  ('fin.events_hourly', '2026-03-04 09:00:00', '2026-03-04 09:07:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-04 08:45:00', '2026-03-04 09:38:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-04 09:45:00', '2026-03-04 10:07:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-04 08:20:00', '2026-03-04 10:20:57'),
  ('ANA.FRAUD_HOURLY', '2026-03-04 10:45:00', '2026-03-04 10:53:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-03-04 10:05:00', '2026-03-04 11:08:01'),
  ('fin.events_hourly', '2026-03-04 11:00:00', '2026-03-04 11:13:53'),
  ('ana.renewals_four_hourly', '2026-03-04 11:30:00', '2026-03-04 11:39:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-04 11:45:00', '2026-03-04 11:59:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-04 12:00:00', '2026-03-04 12:07:38'),
  ('FIN.EVENTS_HOURLY', '2026-03-04 07:00:00', '2026-03-04 12:37:14'),
  ('ana.fraud_hourly', '2026-03-04 12:45:00', '2026-03-04 13:12:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.QUOTES_DAILY', '2026-03-04 13:00:00', '2026-03-04 13:15:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-04 14:15:00', '2026-03-04 14:18:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-04 13:20:00', '2026-03-04 14:54:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-04 14:45:00', '2026-03-04 15:03:20'),
  ('ana.churn_daily', '2026-03-04 13:30:00', '2026-03-04 15:15:43'),
  ('ana.fraud-hourly', '2026-03-04 10:45:00', '2026-03-04 15:26:51'),
  ('ana.renewals-four-hourly', '2026-03-04 15:30:00', '2026-03-04 15:56:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-04 15:45:00', '2026-03-04 16:02:28'),
  ('leg.quotes_daily', '2026-03-04 13:00:00', '2026-03-04 16:06:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-04 16:00:00', '2026-03-04 16:22:23'),
  ('ana/fraud_hourly', '2026-03-04 16:45:00', '2026-03-04 17:01:47'),
  ('fin.events_hourly', '2026-03-04 17:00:00', '2026-03-04 17:07:00'),
  ('ana.fraud_hourly', '2026-03-04 17:45:00', '2026-03-04 18:01:10'),
  ('fin.events_hourly', '2026-03-04 18:00:00', '2026-03-04 18:29:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-04 19:00:00', '2026-03-04 19:17:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-04 19:15:00', '2026-03-04 19:17:39'),
  ('ana.fraud_hourly', '2026-03-04 18:45:00', '2026-03-04 19:19:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-04 19:30:00', '2026-03-04 19:42:51'),
  ('ana.fraud_hourly', '2026-03-04 19:45:00', '2026-03-04 20:07:24'),
  ('fin.events_hourly', '2026-03-04 20:00:00', '2026-03-04 20:13:49'),
  ('ana.fraud_hourly', '2026-03-04 20:45:00', '2026-03-04 21:13:02'),
  ('leg.tickets_four_hourly', '2026-03-04 22:15:00', '2026-03-04 22:15:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-04 22:00:00', '2026-03-04 22:21:08'),
  ('leg.search_daily', '2026-03-04 19:15:00', '2026-03-04 22:45:00'),
  ('ANA.FRAUD_HOURLY', '2026-03-04 23:45:00', '2026-03-04 23:55:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-04 22:45:00', '2026-03-05 00:12:11'),
  ('fin.events_hourly', '2026-03-05 00:00:00', '2026-03-05 00:15:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-04 19:45:00', '2026-03-05 00:35:59'),
  ('fin.inventory_daily', '2026-03-05 01:10:00', '2026-03-05 01:20:40'),
  ('fin/events_hourly', '2026-03-04 23:00:00', '2026-03-05 01:30:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-05 01:20:00', '2026-03-05 01:41:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-05 01:00:00', '2026-03-05 02:11:03'),
  ('leg.tickets_four_hourly', '2026-03-05 02:15:00', '2026-03-05 02:17:14'),
  ('fin/exports_daily', '2026-03-05 01:10:00', '2026-03-05 02:26:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-05 02:10:00', '2026-03-05 02:29:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-05 01:45:00', '2026-03-05 02:55:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake/alerts_daily', '2026-03-05 03:00:00', '2026-03-05 03:03:52'),
  ('fin.events_hourly', '2026-03-05 02:00:00', '2026-03-05 03:09:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-05 02:45:00', '2026-03-05 03:15:45'),
  ('ana.renewals_four_hourly', '2026-03-05 03:30:00', '2026-03-05 03:56:49'),
  ('ana.fraud_hourly', '2026-03-05 03:45:00', '2026-03-05 04:21:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-05 04:45:00', '2026-03-05 05:14:07'),
  ('fin.catalog_weekday', '2026-03-05 04:45:00', '2026-03-05 05:21:27'),
  ('fin.events_hourly', '2026-03-05 05:00:00', '2026-03-05 05:24:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-05 05:45:00', '2026-03-05 06:05:19'),
  ('leg.tickets_four_hourly', '2026-03-05 06:15:00', '2026-03-05 06:16:37'),
  ('fin.refunds_daily', '2026-03-05 05:45:00', '2026-03-05 06:31:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-05 06:45:00', '2026-03-05 07:10:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-05 06:00:00', '2026-03-05 07:15:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.limits_weekday', '2026-03-05 04:20:00', '2026-03-05 07:24:11'),
  ('ana/fraud_hourly', '2026-03-05 07:45:00', '2026-03-05 08:01:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-05 07:15:00', '2026-03-05 08:09:16'),
  ('fin.events_hourly', '2026-03-05 08:00:00', '2026-03-05 08:13:08'),
  ('lake.clicks_daily', '2026-03-05 08:20:00', '2026-03-05 08:26:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-05 08:45:00', '2026-03-05 09:00:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-05 09:00:00', '2026-03-05 09:16:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-05 05:45:00', '2026-03-05 10:01:38'),
  ('fin.events_hourly', '2026-03-05 10:00:00', '2026-03-05 10:10:51'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-05 10:15:00', '2026-03-05 10:16:21'),
  ('ana.fraud_hourly', '2026-03-05 09:45:00', '2026-03-05 10:52:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-03-05 10:05:00', '2026-03-05 11:00:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-05 11:00:00', '2026-03-05 11:10:58'),
  ('ana.fraud_hourly', '2026-03-05 10:45:00', '2026-03-05 11:19:07'),
  ('ana.fraud_hourly', '2026-03-05 11:45:00', '2026-03-05 12:07:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-05 12:00:00', '2026-03-05 12:15:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-05 13:00:00', '2026-03-05 13:26:00'),
  ('fin.events_hourly', '2026-03-05 13:00:00', '2026-03-05 13:40:26'),
  ('leg.tickets_weekday', '2026-03-05 13:20:00', '2026-03-05 14:15:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-05 14:15:00', '2026-03-05 14:27:27'),
  ('fin.events_hourly', '2026-03-05 11:00:00', '2026-03-05 14:55:26'),
  ('fin/events_hourly', '2026-03-05 14:00:00', '2026-03-05 14:55:37'),
  ('ana.fraud_hourly', '2026-03-05 14:45:00', '2026-03-05 15:02:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-05 15:30:00', '2026-03-05 15:39:17'),
  ('fin.events_hourly', '2026-03-05 15:00:00', '2026-03-05 15:58:44'),
  ('fin.events_hourly', '2026-03-05 16:00:00', '2026-03-05 16:10:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-05 15:45:00', '2026-03-05 16:15:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-03-05 16:15:00', '2026-03-05 16:16:13'),
  ('ana/churn_daily', '2026-03-05 13:30:00', '2026-03-05 16:17:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-05 17:00:00', '2026-03-05 17:25:30'),
  ('ana.fraud_hourly', '2026-03-05 16:45:00', '2026-03-05 17:25:48'),
  ('fin.events_hourly', '2026-03-05 18:00:00', '2026-03-05 18:12:24'),
  ('leg.tickets_four_hourly', '2026-03-05 18:15:00', '2026-03-05 18:16:35'),
  ('ana.shipments_weekday1', '2026-03-05 19:15:00', '2026-03-05 19:18:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-05 19:00:00', '2026-03-05 19:26:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-05 19:30:00', '2026-03-05 19:48:23'),
  ('ANA.FRAUD_HOURLY', '2026-03-05 19:45:00', '2026-03-05 20:03:20'),
  ('fin.events_hourly', '2026-03-05 20:00:00', '2026-03-05 20:09:37'),
  ('leg.search_daily', '2026-03-05 19:15:00', '2026-03-05 20:15:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-05 18:00:00', '2026-03-05 20:39:14'),
  ('ana.fraud_hourly', '2026-03-05 21:45:00', '2026-03-05 22:03:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-05 22:00:00', '2026-03-05 22:14:48'),
  ('fin.events_hourly', '2026-03-05 23:00:00', '2026-03-05 23:08:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-05 22:45:00', '2026-03-05 23:21:37'),
  ('fin.events_hourly', '2026-03-05 19:00:00', '2026-03-05 23:25:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-05 23:30:00', '2026-03-05 23:54:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-05 23:45:00', '2026-03-06 00:07:03'),
  ('fin.events_hourly', '2026-03-06 00:00:00', '2026-03-06 00:20:50'),
  ('fin.events_hourly', '2026-03-06 01:00:00', '2026-03-06 01:09:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-06 00:45:00', '2026-03-06 01:18:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-06 01:10:00', '2026-03-06 01:20:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-06 01:10:00', '2026-03-06 01:57:31'),
  ('leg.tickets_four_hourly', '2026-03-06 02:15:00', '2026-03-06 02:18:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-06 01:45:00', '2026-03-06 02:30:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-06 02:10:00', '2026-03-06 02:39:17'),
  ('fin.renewals_daily', '2026-03-06 01:20:00', '2026-03-06 02:46:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-06 03:00:00', '2026-03-06 03:03:35'),
  ('fin.events_hourly', '2026-03-06 00:00:00', '2026-03-06 03:09:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-06 03:30:00', '2026-03-06 03:47:08'),
  ('ana.fraud_hourly', '2026-03-06 00:45:00', '2026-03-06 04:13:30'),
  ('fin/events_hourly', '2026-03-06 04:00:00', '2026-03-06 04:15:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 03:00:00', '2026-03-06 04:18:37'),
  ('ana.fraud_hourly', '2026-03-06 03:45:00', '2026-03-06 04:19:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-06 04:45:00', '2026-03-06 05:21:23'),
  ('leg.tickets_four_hourly', '2026-03-06 06:15:00', '2026-03-06 06:17:35'),
  ('fin.events_hourly', '2026-03-06 06:00:00', '2026-03-06 06:57:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-06 06:45:00', '2026-03-06 06:58:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 07:00:00', '2026-03-06 07:15:27'),
  ('ana.renewals_four_hourly', '2026-03-06 07:30:00', '2026-03-06 07:40:51'),
  ('ana.fraud_hourly', '2026-03-06 07:45:00', '2026-03-06 07:57:37'),
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('lake.events_weekday', '2026-03-06 07:30:00', '2026-03-06 08:05:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 08:00:00', '2026-03-06 08:16:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-03-06 07:30:00', '2026-03-06 08:19:23'),
  ('LAKE.CLICKS_DAILY', '2026-03-06 08:20:00', '2026-03-06 08:26:39'),
  ('fin.events-hourly', '2026-03-06 09:00:00', '2026-03-06 09:52:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-06 09:45:00', '2026-03-06 09:57:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-06 10:15:00', '2026-03-06 10:17:11'),
  ('fin.events_hourly', '2026-03-06 10:00:00', '2026-03-06 10:42:11'),
  ('leg.exports-daily', '2026-03-06 10:05:00', '2026-03-06 10:57:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-06 10:45:00', '2026-03-06 11:01:04'),
  ('fin.events_hourly', '2026-03-06 11:00:00', '2026-03-06 11:13:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-06 09:00:00', '2026-03-06 11:39:44'),
  ('ana.renewals_four_hourly', '2026-03-06 11:30:00', '2026-03-06 11:42:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-06 11:45:00', '2026-03-06 11:58:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.search_weekly', '2026-03-06 13:05:00', '2026-03-06 13:23:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 13:00:00', '2026-03-06 13:24:14'),
  ('leg/quotes_daily', '2026-03-06 13:00:00', '2026-03-06 13:32:01'),
  ('ana.fraud-hourly', '2026-03-06 12:45:00', '2026-03-06 14:13:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-06 13:20:00', '2026-03-06 14:14:56'),
  ('fin.events_hourly', '2026-03-06 14:00:00', '2026-03-06 14:24:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/budgets_daily1', '2026-03-06 13:00:00', '2026-03-06 14:38:13'),
  ('ANA.FRAUD_HOURLY', '2026-03-06 14:45:00', '2026-03-06 15:02:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-03-06 13:30:00', '2026-03-06 15:09:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals-four-hourly', '2026-03-06 15:30:00', '2026-03-06 15:37:53'),
  ('lake.accounts_weekday', '2026-03-06 16:15:00', '2026-03-06 16:18:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 16:00:00', '2026-03-06 16:20:41'),
  ('ana.fraud_hourly', '2026-03-06 15:45:00', '2026-03-06 17:10:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 17:00:00', '2026-03-06 17:18:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-06 16:45:00', '2026-03-06 17:18:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 18:00:00', '2026-03-06 18:12:13'),
  ('leg.forecast_daily', '2026-03-06 18:05:00', '2026-03-06 18:34:25'),
  ('fin.events_hourly', '2026-03-06 19:00:00', '2026-03-06 19:26:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-06 19:30:00', '2026-03-06 19:36:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-06 18:45:00', '2026-03-06 19:40:29'),
  ('leg.search_daily', '2026-03-06 19:15:00', '2026-03-06 20:05:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-06 19:45:00', '2026-03-06 20:13:50'),
  ('fin.events_hourly', '2026-03-06 20:00:00', '2026-03-06 20:20:12'),
  ('ana.fraud_hourly', '2026-03-06 18:45:00', '2026-03-06 20:38:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-03-06 16:15:00', '2026-03-06 20:55:20'),
  ('fin.events_hourly', '2026-03-06 21:00:00', '2026-03-06 21:08:41'),
  ('ANA.FRAUD_HOURLY', '2026-03-06 20:45:00', '2026-03-06 21:09:41'),
  ('leg.tickets_four_hourly', '2026-03-06 18:15:00', '2026-03-06 21:12:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 22:00:00', '2026-03-06 22:10:23'),
  ('ana.fraud_hourly', '2026-03-06 21:45:00', '2026-03-06 22:12:04'),
  ('leg.tickets_four_hourly', '2026-03-06 22:15:00', '2026-03-06 22:17:02'),
  ('ANA.FRAUD_HOURLY', '2026-03-06 22:45:00', '2026-03-06 23:13:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-06 23:00:00', '2026-03-06 23:25:43'),
  ('ana.renewals_four_hourly', '2026-03-06 23:30:00', '2026-03-06 23:43:04'),
  ('ana.fraud_hourly', '2026-03-06 23:45:00', '2026-03-07 00:04:44'),
  ('fin.events_hourly', '2026-03-06 19:00:00', '2026-03-07 00:05:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-07 00:00:00', '2026-03-07 00:22:15'),
  ('fin.inventory_daily', '2026-03-07 01:10:00', '2026-03-07 01:22:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 00:45:00', '2026-03-07 01:34:30'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-07 02:15:00', '2026-03-07 02:16:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-07 01:20:00', '2026-03-07 02:29:47'),
  ('fin.exports_daily', '2026-03-07 01:10:00', '2026-03-07 02:35:01'),
  ('ana/fraud_hourly', '2026-03-07 01:45:00', '2026-03-07 02:37:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 02:45:00', '2026-03-07 03:10:48'),
  ('ana.renewals_four_hourly', '2026-03-07 03:30:00', '2026-03-07 03:45:32'),
  ('fin.events_hourly', '2026-03-07 03:00:00', '2026-03-07 04:09:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 03:45:00', '2026-03-07 04:14:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 04:45:00', '2026-03-07 05:04:24'),
  ('fin.events_hourly', '2026-03-07 05:00:00', '2026-03-07 05:22:38'),
  ('fin.inventory_daily', '2026-03-07 01:10:00', '2026-03-07 05:35:08'),
  ('leg.tickets_four_hourly', '2026-03-07 02:15:00', '2026-03-07 06:06:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 05:45:00', '2026-03-07 06:10:16'),
  ('ana.fraud_hourly', '2026-03-07 00:45:00', '2026-03-07 06:11:04'),
  ('leg.tickets_four_hourly', '2026-03-07 06:15:00', '2026-03-07 06:17:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-07 06:00:00', '2026-03-07 06:18:03'),
  ('fin.events_hourly', '2026-03-07 05:00:00', '2026-03-07 06:49:58'),
  ('ana.fraud_hourly', '2026-03-07 06:45:00', '2026-03-07 07:13:07'),
  ('fin.events_hourly', '2026-03-07 07:00:00', '2026-03-07 07:18:59'),
  ('ana.renewals_four_hourly', '2026-03-07 07:30:00', '2026-03-07 07:56:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 07:45:00', '2026-03-07 08:01:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-07 08:00:00', '2026-03-07 08:19:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-07 08:20:00', '2026-03-07 08:31:05'),
  ('fin.events_hourly', '2026-03-07 09:00:00', '2026-03-07 09:09:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 08:45:00', '2026-03-07 09:09:45'),
  ('ana.fraud_hourly', '2026-03-07 04:45:00', '2026-03-07 09:29:13'),
  ('ana.fraud_hourly', '2026-03-07 09:45:00', '2026-03-07 10:11:57'),
  ('ana.fraud-hourly', '2026-03-07 10:45:00', '2026-03-07 10:57:49'),
  ('fin.events_hourly', '2026-03-07 11:00:00', '2026-03-07 11:11:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-07 11:30:00', '2026-03-07 11:45:15'),
  ('fin.events_hourly', '2026-03-07 12:00:00', '2026-03-07 12:24:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 12:45:00', '2026-03-07 13:20:23'),
  ('leg.quotes_daily', '2026-03-07 13:00:00', '2026-03-07 13:21:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-07 13:00:00', '2026-03-07 13:34:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-07 14:15:00', '2026-03-07 14:17:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 13:45:00', '2026-03-07 14:41:26'),
  ('ana.churn_daily', '2026-03-07 13:30:00', '2026-03-07 15:02:27'),
  ('fin.events_hourly', '2026-03-07 14:00:00', '2026-03-07 15:04:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-07 15:00:00', '2026-03-07 15:25:24'),
  ('ana.renewals-four-hourly', '2026-03-07 15:30:00', '2026-03-07 15:44:22'),
  ('ana.fraud_hourly', '2026-03-07 15:45:00', '2026-03-07 15:55:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 13:45:00', '2026-03-07 15:58:41'),
  ('fin.events_hourly', '2026-03-07 16:00:00', '2026-03-07 16:53:51'),
  ('leg.quotes_daily', '2026-03-07 13:00:00', '2026-03-07 17:14:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-07 17:00:00', '2026-03-07 17:25:40'),
  ('ana.fraud_hourly', '2026-03-07 17:45:00', '2026-03-07 18:15:51'),
  ('fin.events-hourly', '2026-03-07 18:00:00', '2026-03-07 19:02:35'),
  ('ana.fraud_hourly', '2026-03-07 18:45:00', '2026-03-07 19:10:51'),
  ('fin.events_hourly', '2026-03-07 20:00:00', '2026-03-07 20:10:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-07 20:45:00', '2026-03-07 21:11:03'),
  ('fin.events_hourly', '2026-03-07 21:00:00', '2026-03-07 21:27:27'),
  ('leg.tickets_four_hourly', '2026-03-07 22:15:00', '2026-03-07 22:15:40'),
  ('ana.fraud_hourly', '2026-03-07 22:45:00', '2026-03-07 22:53:53'),
  ('fin.events-hourly', '2026-03-07 23:00:00', '2026-03-07 23:09:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-07 23:30:00', '2026-03-07 23:39:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-07 23:45:00', '2026-03-08 00:04:21'),
  ('fin.events-hourly', '2026-03-08 00:00:00', '2026-03-08 00:25:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-08 00:45:00', '2026-03-08 01:06:22'),
  ('fin.events-hourly', '2026-03-08 01:00:00', '2026-03-08 01:23:03'),
  ('fin.inventory_daily', '2026-03-08 01:10:00', '2026-03-08 01:35:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-08 02:00:00', '2026-03-08 02:13:47'),
  ('fin.exports_daily', '2026-03-08 01:10:00', '2026-03-08 02:17:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-08 02:15:00', '2026-03-08 02:17:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-08 01:45:00', '2026-03-08 02:20:13'),
  ('ana/fraud_hourly', '2026-03-08 02:45:00', '2026-03-08 03:09:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-08 03:00:00', '2026-03-08 03:20:21'),
  ('ana/renewals_four_hourly', '2026-03-08 03:30:00', '2026-03-08 03:55:08'),
  ('ana.fraud_hourly', '2026-03-08 03:45:00', '2026-03-08 04:14:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-08 04:00:00', '2026-03-08 05:05:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-08 04:45:00', '2026-03-08 05:18:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-08 05:00:00', '2026-03-08 06:12:28'),
  ('fin.events_hourly', '2026-03-08 06:00:00', '2026-03-08 06:13:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-08 06:15:00', '2026-03-08 06:33:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-08 05:45:00', '2026-03-08 06:59:39'),
  ('fin.events_hourly', '2026-03-08 07:00:00', '2026-03-08 07:26:29'),
  ('ana.renewals_four_hourly', '2026-03-08 07:30:00', '2026-03-08 07:41:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks-daily', '2026-03-08 08:00:00', '2026-03-08 08:15:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-08 09:00:00', '2026-03-08 09:08:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-08 08:45:00', '2026-03-08 09:09:55'),
  ('leg.tickets_four_hourly', '2026-03-08 10:00:00', '2026-03-08 10:01:08'),
  ('ana.fraud_hourly', '2026-03-08 09:45:00', '2026-03-08 10:07:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-08 10:00:00', '2026-03-08 10:34:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-08 10:45:00', '2026-03-08 11:01:03'),
  ('fin.events_hourly', '2026-03-08 11:00:00', '2026-03-08 11:22:09'),
  ('ana.renewals_four_hourly', '2026-03-08 11:30:00', '2026-03-08 11:50:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-08 12:00:00', '2026-03-08 12:20:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-08 13:15:00', '2026-03-08 13:17:41'),
  ('LEG.QUOTES_DAILY', '2026-03-08 13:00:00', '2026-03-08 13:38:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-08 13:45:00', '2026-03-08 13:55:16'),
  ('fin.budgets_daily1', '2026-03-08 13:00:00', '2026-03-08 14:22:44'),
  ('ana.fraud_hourly', '2026-03-08 14:45:00', '2026-03-08 15:08:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-08 15:00:00', '2026-03-08 15:23:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-08 15:30:00', '2026-03-08 15:43:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/churn_daily', '2026-03-08 13:30:00', '2026-03-08 16:05:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-08 16:00:00', '2026-03-08 16:22:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-08 16:45:00', '2026-03-08 17:06:08'),
  ('fin.events_hourly', '2026-03-08 17:00:00', '2026-03-08 17:21:28'),
  ('LEG.FORECAST_DAILY', '2026-03-08 17:05:00', '2026-03-08 17:21:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-08 17:45:00', '2026-03-08 17:59:18'),
  ('ana.renewals_four_hourly', '2026-03-08 15:30:00', '2026-03-08 18:03:23'),
  ('fin.events_hourly', '2026-03-08 18:00:00', '2026-03-08 18:17:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-08 13:00:00', '2026-03-08 18:24:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-08 18:45:00', '2026-03-08 19:04:31'),
  ('ANA.SHIPMENTS_WEEKDAY1', '2026-03-08 19:15:00', '2026-03-08 19:17:19'),
  ('fin.events_hourly', '2026-03-08 19:00:00', '2026-03-08 19:21:49'),
  ('fin.events_hourly', '2026-03-08 20:00:00', '2026-03-08 20:16:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-08 20:45:00', '2026-03-08 21:13:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-08 21:00:00', '2026-03-08 21:26:28'),
  ('fin.events_hourly', '2026-03-08 20:00:00', '2026-03-08 21:36:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/search_daily', '2026-03-08 18:15:00', '2026-03-08 21:45:00'),
  ('leg.tickets_four_hourly', '2026-03-08 21:15:00', '2026-03-08 21:48:31'),
  ('ana.fraud_hourly', '2026-03-08 21:45:00', '2026-03-08 22:00:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-08 22:00:00', '2026-03-08 22:11:36'),
  ('fin.events_hourly', '2026-03-08 23:00:00', '2026-03-08 23:25:50'),
  ('ana.fraud_hourly', '2026-03-08 22:45:00', '2026-03-08 23:52:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-08 23:30:00', '2026-03-08 23:53:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-09 00:00:00', '2026-03-09 00:37:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-09 01:15:00', '2026-03-09 01:16:52'),
  ('ana.fraud_hourly', '2026-03-09 00:45:00', '2026-03-09 01:16:55'),
  ('fin.inventory_daily', '2026-03-09 01:10:00', '2026-03-09 01:45:11'),
  ('ana.fraud_hourly', '2026-03-09 01:45:00', '2026-03-09 02:02:38'),
  ('fin.events_hourly', '2026-03-08 23:00:00', '2026-03-09 02:09:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-08 21:45:00', '2026-03-09 02:29:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.audits_twice_monthly', '2026-03-09 00:00:00', '2026-03-09 02:30:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-09 01:10:00', '2026-03-09 02:45:06'),
  ('fin.ads_weekday', '2026-03-09 02:10:00', '2026-03-09 02:51:29'),
  ('lake.alerts_daily', '2026-03-09 03:00:00', '2026-03-09 03:01:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 02:45:00', '2026-03-09 03:08:47'),
  ('fin.events_hourly', '2026-03-09 02:00:00', '2026-03-09 03:25:22'),
  ('fin.events_hourly', '2026-03-09 03:00:00', '2026-03-09 03:25:38'),
  ('ana.renewals_four_hourly', '2026-03-09 03:30:00', '2026-03-09 03:47:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 03:45:00', '2026-03-09 04:11:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 04:45:00', '2026-03-09 05:07:55'),
  ('ana.limits_weekday', '2026-03-09 04:20:00', '2026-03-09 05:13:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-09 05:15:00', '2026-03-09 05:28:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-09 05:00:00', '2026-03-09 05:38:25'),
  ('fin.events_hourly', '2026-03-09 06:00:00', '2026-03-09 06:07:29'),
  ('ana.fraud_hourly', '2026-03-09 05:45:00', '2026-03-09 06:09:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-09 05:45:00', '2026-03-09 06:17:58'),
  ('fin.refunds_daily', '2026-03-09 05:45:00', '2026-03-09 06:24:10'),
  ('scratch.tmp_events_7', '2026-03-09 06:00:00', '2026-03-09 06:25:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 06:45:00', '2026-03-09 07:19:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-03-09 06:30:00', '2026-03-09 07:21:09'),
  ('fin.events_hourly', '2026-03-09 07:00:00', '2026-03-09 07:35:35'),
  ('ana/renewals_four_hourly', '2026-03-09 07:30:00', '2026-03-09 07:43:58'),
  ('ana.fraud_hourly', '2026-03-09 07:45:00', '2026-03-09 08:15:02'),
  ('fin.events_hourly', '2026-03-09 08:00:00', '2026-03-09 08:45:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 08:45:00', '2026-03-09 09:11:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets-four-hourly', '2026-03-09 09:15:00', '2026-03-09 09:19:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 09:45:00', '2026-03-09 10:01:45'),
  ('leg.exports_daily', '2026-03-09 09:05:00', '2026-03-09 10:10:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 08:45:00', '2026-03-09 10:12:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-09 07:00:00', '2026-03-09 10:28:09'),
  ('ana.fraud_hourly', '2026-03-09 10:45:00', '2026-03-09 10:58:44'),
  ('fin.events_hourly', '2026-03-09 11:00:00', '2026-03-09 11:24:15'),
  ('ana.renewals_four_hourly', '2026-03-09 11:30:00', '2026-03-09 12:20:42'),
  ('ana.fraud_hourly', '2026-03-09 06:45:00', '2026-03-09 12:29:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-09 12:00:00', '2026-03-09 12:35:06'),
  ('ana.fraud-hourly', '2026-03-09 12:45:00', '2026-03-09 13:02:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-09 13:00:00', '2026-03-09 13:12:21'),
  ('fin.events_hourly', '2026-03-09 13:00:00', '2026-03-09 13:20:57'),
  ('fin.budgets_daily1', '2026-03-09 13:00:00', '2026-03-09 13:55:50'),
  ('ana.fraud_hourly', '2026-03-09 13:45:00', '2026-03-09 14:00:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-09 13:15:00', '2026-03-09 14:03:34'),
  ('FIN.EVENTS_HOURLY', '2026-03-09 14:00:00', '2026-03-09 14:19:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/churn_daily', '2026-03-09 13:30:00', '2026-03-09 14:50:04'),
  ('LAKE.ACCOUNTS_WEEKDAY', '2026-03-09 15:15:00', '2026-03-09 15:15:42'),
  ('fin/events_hourly', '2026-03-09 15:00:00', '2026-03-09 15:21:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 15:45:00', '2026-03-09 15:59:10'),
  ('fin.events_hourly', '2026-03-09 16:00:00', '2026-03-09 16:10:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-09 17:15:00', '2026-03-09 17:18:19'),
  ('fin.events_hourly', '2026-03-09 17:00:00', '2026-03-09 17:20:19'),
  ('leg.forecast_daily', '2026-03-09 17:05:00', '2026-03-09 17:29:30'),
  ('ana.fraud_hourly', '2026-03-09 16:45:00', '2026-03-09 18:03:19'),
  ('ana.fraud_hourly', '2026-03-09 17:45:00', '2026-03-09 18:15:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-09 18:00:00', '2026-03-09 18:20:35'),
  ('leg.search_daily', '2026-03-09 18:15:00', '2026-03-09 18:44:21'),
  ('fin/events_hourly', '2026-03-09 15:00:00', '2026-03-09 18:52:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-09 18:00:00', '2026-03-09 19:01:07'),
  ('fin/events_hourly', '2026-03-09 19:00:00', '2026-03-09 19:09:39'),
  ('leg.tickets_four_hourly', '2026-03-09 21:15:00', '2026-03-09 21:17:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-09 21:45:00', '2026-03-09 22:02:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-09 22:00:00', '2026-03-09 22:05:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-09 21:00:00', '2026-03-09 22:07:00'),
  ('fin.events_hourly', '2026-03-09 22:00:00', '2026-03-09 22:54:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-09 22:45:00', '2026-03-09 23:19:16'),
  ('ana.renewals_four_hourly', '2026-03-09 23:30:00', '2026-03-09 23:45:29'),
  ('ana.fraud_hourly', '2026-03-09 23:45:00', '2026-03-10 00:00:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 00:00:00', '2026-03-10 00:18:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 01:00:00', '2026-03-10 01:08:46'),
  ('ana.fraud-hourly', '2026-03-10 00:45:00', '2026-03-10 01:13:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-10 01:15:00', '2026-03-10 01:17:28'),
  ('fin.events-hourly', '2026-03-09 23:00:00', '2026-03-10 01:30:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-10 01:10:00', '2026-03-10 01:33:50'),
  ('fin.renewals-daily', '2026-03-10 01:20:00', '2026-03-10 01:43:52'),
  ('ana.fraud-hourly', '2026-03-10 01:45:00', '2026-03-10 02:00:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 02:00:00', '2026-03-10 02:21:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-10 02:10:00', '2026-03-10 02:55:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-10 03:00:00', '2026-03-10 03:01:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-10 02:45:00', '2026-03-10 03:21:58'),
  ('ana.renewals_four_hourly', '2026-03-10 03:30:00', '2026-03-10 03:38:56'),
  ('ana.fraud_hourly', '2026-03-10 03:45:00', '2026-03-10 04:20:24'),
  ('fin.events_hourly', '2026-03-10 04:00:00', '2026-03-10 04:27:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.LIMITS_WEEKDAY', '2026-03-10 04:20:00', '2026-03-10 05:09:51'),
  ('fin.exports_daily', '2026-03-10 01:10:00', '2026-03-10 05:10:00'),
  ('ANA.FRAUD_HOURLY', '2026-03-10 04:45:00', '2026-03-10 05:12:29'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-10 05:15:00', '2026-03-10 05:16:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-10 05:45:00', '2026-03-10 05:55:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-10 05:45:00', '2026-03-10 05:56:32'),
  ('fin.events_hourly', '2026-03-10 05:00:00', '2026-03-10 06:09:28'),
  ('fin.events_hourly', '2026-03-10 06:00:00', '2026-03-10 06:10:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-03-10 06:30:00', '2026-03-10 07:10:02'),
  ('ana.renewals_four_hourly', '2026-03-10 07:30:00', '2026-03-10 07:44:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-10 06:15:00', '2026-03-10 07:56:02'),
  ('ana.fraud_hourly', '2026-03-10 07:45:00', '2026-03-10 08:19:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-10 08:45:00', '2026-03-10 09:15:02'),
  ('leg.tickets_four_hourly', '2026-03-10 09:15:00', '2026-03-10 09:17:16'),
  ('leg.exports_daily', '2026-03-10 09:05:00', '2026-03-10 09:38:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-10 09:45:00', '2026-03-10 10:05:01'),
  ('fin.events-hourly', '2026-03-10 10:00:00', '2026-03-10 10:16:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-10 05:45:00', '2026-03-10 10:59:26'),
  ('ANA.FRAUD_HOURLY', '2026-03-10 10:45:00', '2026-03-10 11:05:16'),
  ('ana.fraud_hourly', '2026-03-10 11:45:00', '2026-03-10 12:13:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 12:00:00', '2026-03-10 12:21:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-10 12:45:00', '2026-03-10 13:05:02'),
  ('fin.events_hourly', '2026-03-10 13:00:00', '2026-03-10 13:15:04'),
  ('leg/quotes_daily', '2026-03-10 13:00:00', '2026-03-10 13:38:30'),
  ('fin.events_hourly', '2026-03-10 14:00:00', '2026-03-10 14:07:25'),
  ('ana.fraud_hourly', '2026-03-10 13:45:00', '2026-03-10 14:16:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 15:00:00', '2026-03-10 15:14:14'),
  ('lake.accounts_weekday', '2026-03-10 15:15:00', '2026-03-10 15:18:12'),
  ('fin/budgets_daily1', '2026-03-10 13:00:00', '2026-03-10 15:19:03'),
  ('ana.fraud_hourly', '2026-03-10 12:45:00', '2026-03-10 15:39:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_WEEKDAY', '2026-03-10 12:20:00', '2026-03-10 15:52:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-10 15:30:00', '2026-03-10 15:55:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-10 15:45:00', '2026-03-10 16:03:40'),
  ('fin.events_hourly', '2026-03-10 16:00:00', '2026-03-10 16:13:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-10 13:45:00', '2026-03-10 17:04:40'),
  ('ana.fraud_hourly', '2026-03-10 16:45:00', '2026-03-10 17:09:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-10 17:15:00', '2026-03-10 17:17:36'),
  ('leg.forecast_daily', '2026-03-10 17:05:00', '2026-03-10 17:20:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 17:00:00', '2026-03-10 17:51:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-10 17:45:00', '2026-03-10 18:20:34'),
  ('FIN.EVENTS_HOURLY', '2026-03-10 18:00:00', '2026-03-10 18:27:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/search_daily', '2026-03-10 18:15:00', '2026-03-10 19:14:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 19:00:00', '2026-03-10 19:14:26'),
  ('ana.shipments_weekday1', '2026-03-10 19:15:00', '2026-03-10 19:17:24'),
  ('ana.fraud_hourly', '2026-03-10 19:45:00', '2026-03-10 20:13:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-10 20:45:00', '2026-03-10 20:56:36'),
  ('fin.events_hourly', '2026-03-10 21:00:00', '2026-03-10 21:09:09'),
  ('ana.fraud_hourly', '2026-03-10 16:45:00', '2026-03-10 22:15:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 23:00:00', '2026-03-10 23:18:36'),
  ('ana.renewals_four_hourly', '2026-03-10 23:30:00', '2026-03-10 23:38:28'),
  ('fin.events_hourly', '2026-03-11 00:00:00', '2026-03-11 00:09:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-11 01:15:00', '2026-03-11 01:18:39'),
  ('fin.inventory_daily', '2026-03-11 01:10:00', '2026-03-11 01:21:21'),
  ('fin.events_hourly', '2026-03-11 01:00:00', '2026-03-11 01:25:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-11 01:10:00', '2026-03-11 01:40:18'),
  ('fin.renewals_daily', '2026-03-11 01:20:00', '2026-03-11 01:45:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-11 01:45:00', '2026-03-11 02:02:39'),
  ('ana.fraud_hourly', '2026-03-11 00:45:00', '2026-03-11 02:07:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-10 21:00:00', '2026-03-11 02:38:42'),
  ('fin.ads_weekday', '2026-03-11 02:10:00', '2026-03-11 02:48:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 02:00:00', '2026-03-11 02:55:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-11 03:00:00', '2026-03-11 03:04:11'),
  ('fin.events-hourly', '2026-03-11 03:00:00', '2026-03-11 03:16:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-11 02:00:00', '2026-03-11 03:33:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 04:00:00', '2026-03-11 04:19:59'),
  ('fin.events_hourly', '2026-03-11 05:00:00', '2026-03-11 05:11:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-11 05:15:00', '2026-03-11 05:16:48'),
  ('fin.catalog_weekday', '2026-03-11 04:45:00', '2026-03-11 05:24:26'),
  ('ana.limits_weekday', '2026-03-11 04:20:00', '2026-03-11 05:40:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 06:00:00', '2026-03-11 06:22:27'),
  ('ana.fraud_hourly', '2026-03-11 05:45:00', '2026-03-11 07:17:02'),
  ('fin.events_hourly', '2026-03-11 07:00:00', '2026-03-11 07:23:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-11 07:20:00', '2026-03-11 07:36:24'),
  ('ana.renewals-four-hourly', '2026-03-11 07:30:00', '2026-03-11 07:49:04'),
  ('ana.fraud_hourly', '2026-03-11 07:45:00', '2026-03-11 08:15:03'),
  ('fin.events_hourly', '2026-03-11 08:00:00', '2026-03-11 08:19:51'),
  ('lake.events_weekday', '2026-03-11 06:30:00', '2026-03-11 08:26:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-11 06:15:00', '2026-03-11 08:59:59'),
  ('ana.fraud_hourly', '2026-03-11 08:45:00', '2026-03-11 09:02:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 09:00:00', '2026-03-11 09:11:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-11 09:15:00', '2026-03-11 09:17:24'),
  ('ana.fraud_hourly', '2026-03-11 09:45:00', '2026-03-11 09:55:01'),
  ('leg.exports_daily', '2026-03-11 09:05:00', '2026-03-11 10:04:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 10:00:00', '2026-03-11 10:13:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 11:00:00', '2026-03-11 11:23:56'),
  ('ana.fraud_hourly', '2026-03-11 10:45:00', '2026-03-11 12:03:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-11 11:45:00', '2026-03-11 12:16:17'),
  ('ana.renewals_four_hourly', '2026-03-11 07:30:00', '2026-03-11 13:02:18'),
  ('ANA.FRAUD_HOURLY', '2026-03-11 12:45:00', '2026-03-11 13:12:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-11 13:15:00', '2026-03-11 13:16:32'),
  ('leg.tickets_weekday', '2026-03-11 12:20:00', '2026-03-11 13:30:47'),
  ('leg.quotes_daily', '2026-03-11 13:00:00', '2026-03-11 13:38:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search-weekday', '2026-03-11 06:15:00', '2026-03-11 13:52:04'),
  ('fin.events-hourly', '2026-03-11 13:00:00', '2026-03-11 13:54:22'),
  ('ana.fraud_hourly', '2026-03-11 13:45:00', '2026-03-11 13:59:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-11 10:45:00', '2026-03-11 14:19:03'),
  ('fin.events_hourly', '2026-03-11 14:00:00', '2026-03-11 14:24:03'),
  ('fin.budgets_daily1', '2026-03-11 13:00:00', '2026-03-11 14:33:39'),
  ('ana.fraud_hourly', '2026-03-11 14:45:00', '2026-03-11 14:59:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/churn_daily', '2026-03-11 13:30:00', '2026-03-11 15:16:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-03-11 15:15:00', '2026-03-11 15:17:45'),
  ('fin.events_hourly', '2026-03-11 15:00:00', '2026-03-11 15:38:58'),
  ('ana.renewals_four_hourly', '2026-03-11 15:30:00', '2026-03-11 15:56:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 16:00:00', '2026-03-11 16:26:16'),
  ('fin.events_hourly', '2026-03-11 11:00:00', '2026-03-11 16:32:46'),
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('fin.events_hourly', '2026-03-11 17:00:00', '2026-03-11 17:08:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-11 16:45:00', '2026-03-11 17:14:26'),
  ('leg.tickets_four_hourly', '2026-03-11 17:15:00', '2026-03-11 17:17:28'),
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('ana.fraud_hourly', '2026-03-11 17:45:00', '2026-03-11 17:54:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 18:00:00', '2026-03-11 18:08:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-11 19:00:00', '2026-03-11 19:13:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-11 19:15:00', '2026-03-11 19:16:42'),
  ('leg.search_daily', '2026-03-11 18:15:00', '2026-03-11 19:17:37'),
  ('ana.fraud_hourly', '2026-03-11 13:45:00', '2026-03-11 19:23:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-11 19:30:00', '2026-03-11 19:53:30'),
  ('ana.fraud_hourly', '2026-03-11 18:45:00', '2026-03-11 20:02:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-11 21:15:00', '2026-03-11 21:17:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-11 21:20:00', '2026-03-11 21:36:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-11 21:00:00', '2026-03-11 22:00:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-11 20:45:00', '2026-03-11 22:21:19'),
  ('fin.events_hourly', '2026-03-11 22:00:00', '2026-03-11 23:05:21'),
  ('fin.events-hourly', '2026-03-11 23:00:00', '2026-03-11 23:25:53'),
  ('ana.renewals_four_hourly', '2026-03-11 23:30:00', '2026-03-11 23:48:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-11 23:45:00', '2026-03-11 23:59:46'),
  ('leg.tickets-four-hourly', '2026-03-12 01:15:00', '2026-03-12 01:16:42'),
  ('fin.exports_daily', '2026-03-12 01:10:00', '2026-03-12 02:11:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-12 01:10:00', '2026-03-12 02:15:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 00:45:00', '2026-03-12 02:16:17'),
  ('ana.fraud_hourly', '2026-03-12 01:45:00', '2026-03-12 02:19:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-12 01:20:00', '2026-03-12 02:30:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-11 23:00:00', '2026-03-12 02:41:32'),
  ('ana.fraud_hourly', '2026-03-12 02:45:00', '2026-03-12 02:56:06'),
  ('lake.alerts_daily', '2026-03-12 03:00:00', '2026-03-12 03:00:59'),
  ('fin.inventory_daily', '2026-03-12 01:10:00', '2026-03-12 03:10:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-12 03:30:00', '2026-03-12 03:53:38'),
  ('ana.fraud-hourly', '2026-03-12 03:45:00', '2026-03-12 04:05:45'),
  ('ana.fraud_hourly', '2026-03-12 04:45:00', '2026-03-12 05:08:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-12 05:15:00', '2026-03-12 05:17:21'),
  ('leg.tickets-four-hourly', '2026-03-12 05:15:00', '2026-03-12 05:32:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 05:45:00', '2026-03-12 05:53:42'),
  ('lake.events_weekday', '2026-03-12 06:30:00', '2026-03-12 06:47:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 06:45:00', '2026-03-12 07:02:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-12 04:00:00', '2026-03-12 07:04:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-12 02:00:00', '2026-03-12 07:10:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-12 05:00:00', '2026-03-12 07:19:56'),
  ('fin.events_hourly', '2026-03-12 03:00:00', '2026-03-12 07:20:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-12 06:15:00', '2026-03-12 07:38:44'),
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-12 07:30:00', '2026-03-12 07:45:14'),
  ('ana.fraud_hourly', '2026-03-12 07:45:00', '2026-03-12 08:06:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-12 02:00:00', '2026-03-12 08:30:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 06:45:00', '2026-03-12 08:57:46'),
  ('fin.events-hourly', '2026-03-12 09:00:00', '2026-03-12 09:23:03'),
  ('fin.events_hourly', '2026-03-12 10:00:00', '2026-03-12 10:12:40'),
  ('ana.fraud_hourly', '2026-03-12 09:45:00', '2026-03-12 10:13:43'),
  ('leg.exports_daily', '2026-03-12 09:05:00', '2026-03-12 10:30:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 10:45:00', '2026-03-12 10:53:49'),
  ('fin.events_hourly', '2026-03-12 09:00:00', '2026-03-12 11:05:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-12 03:00:00', '2026-03-12 11:07:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-12 11:00:00', '2026-03-12 11:14:17'),
  ('ana.renewals_four_hourly', '2026-03-12 11:30:00', '2026-03-12 11:52:05'),
  ('fin.events_hourly', '2026-03-12 04:00:00', '2026-03-12 11:54:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-12 11:45:00', '2026-03-12 12:05:23'),
  ('fin.events_hourly', '2026-03-12 12:00:00', '2026-03-12 12:11:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-12 12:20:00', '2026-03-12 12:57:12'),
  ('fin.events_hourly', '2026-03-12 13:00:00', '2026-03-12 13:09:47'),
  ('leg.quotes_daily', '2026-03-12 13:00:00', '2026-03-12 13:35:40'),
  ('ana.fraud_hourly', '2026-03-12 12:45:00', '2026-03-12 14:07:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-12 13:45:00', '2026-03-12 14:13:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-03-12 15:15:00', '2026-03-12 15:17:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-03-12 13:30:00', '2026-03-12 15:43:21'),
  ('fin.events_hourly', '2026-03-12 16:00:00', '2026-03-12 16:15:49'),
  ('ana.fraud_hourly', '2026-03-12 14:45:00', '2026-03-12 16:18:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-12 15:30:00', '2026-03-12 16:42:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 16:45:00', '2026-03-12 16:54:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 15:45:00', '2026-03-12 17:02:03'),
  ('fin.events_hourly', '2026-03-12 17:00:00', '2026-03-12 17:07:43'),
  ('leg.tickets_four_hourly', '2026-03-12 17:15:00', '2026-03-12 17:16:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 17:45:00', '2026-03-12 17:53:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-03-12 18:15:00', '2026-03-12 19:17:56'),
  ('ana.shipments_weekday1', '2026-03-12 19:15:00', '2026-03-12 19:25:30'),
  ('ana.fraud_hourly', '2026-03-12 16:45:00', '2026-03-12 19:41:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 15:45:00', '2026-03-12 19:46:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/renewals_four_hourly', '2026-03-12 19:30:00', '2026-03-12 19:47:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 19:45:00', '2026-03-12 20:00:49'),
  ('fin.events_hourly', '2026-03-12 20:00:00', '2026-03-12 20:18:49'),
  ('ana.fraud_hourly', '2026-03-12 20:45:00', '2026-03-12 21:05:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-12 21:15:00', '2026-03-12 21:16:54'),
  ('fin.refunds_daily', '2026-03-12 21:20:00', '2026-03-12 21:44:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-12 21:45:00', '2026-03-12 22:07:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-12 22:00:00', '2026-03-12 22:26:32'),
  ('ana.fraud_hourly', '2026-03-12 22:45:00', '2026-03-12 23:00:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-12 23:00:00', '2026-03-12 23:15:11'),
  ('ANA.FRAUD_HOURLY', '2026-03-12 23:45:00', '2026-03-13 00:14:34'),
  ('fin.events_hourly', '2026-03-13 00:00:00', '2026-03-13 00:23:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-12 21:20:00', '2026-03-13 02:01:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 01:45:00', '2026-03-13 02:12:53'),
  ('fin.events_hourly', '2026-03-13 02:00:00', '2026-03-13 02:25:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-13 01:10:00', '2026-03-13 02:40:15'),
  ('fin.ads_weekday', '2026-03-13 02:10:00', '2026-03-13 02:53:19'),
  ('lake.alerts_daily', '2026-03-13 03:00:00', '2026-03-13 03:01:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-13 01:10:00', '2026-03-13 03:12:14'),
  ('fin/events_hourly', '2026-03-13 03:00:00', '2026-03-13 03:18:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 02:45:00', '2026-03-13 03:55:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-13 03:30:00', '2026-03-13 04:05:01'),
  ('ana.fraud_hourly', '2026-03-13 03:45:00', '2026-03-13 04:16:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-13 04:00:00', '2026-03-13 04:16:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-13 02:00:00', '2026-03-13 04:43:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.catalog_weekday', '2026-03-13 04:45:00', '2026-03-13 04:58:07'),
  ('ana.limits_weekday', '2026-03-13 04:20:00', '2026-03-13 05:03:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 04:45:00', '2026-03-13 05:15:02'),
  ('fin.events_hourly', '2026-03-13 05:00:00', '2026-03-13 05:17:05'),
  ('leg.tickets_four_hourly', '2026-03-13 05:15:00', '2026-03-13 05:23:51'),
  ('scratch.tmp_budgets_12', '2026-03-13 06:00:00', '2026-03-13 06:25:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake/events_weekday', '2026-03-13 06:30:00', '2026-03-13 06:54:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-13 06:00:00', '2026-03-13 07:07:57'),
  ('fin.events_hourly', '2026-03-13 07:00:00', '2026-03-13 07:16:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 06:45:00', '2026-03-13 07:19:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-13 03:00:00', '2026-03-13 07:27:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-13 07:20:00', '2026-03-13 07:30:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-13 06:15:00', '2026-03-13 07:37:14'),
  ('fin.renewals_daily', '2026-03-13 01:20:00', '2026-03-13 07:44:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-13 07:45:00', '2026-03-13 07:56:00'),
  ('fin.events_hourly', '2026-03-13 08:00:00', '2026-03-13 08:28:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 08:45:00', '2026-03-13 08:56:34'),
  ('fin.events_hourly', '2026-03-13 05:00:00', '2026-03-13 08:59:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-13 09:15:00', '2026-03-13 09:16:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-13 08:00:00', '2026-03-13 09:17:20'),
  ('fin.events_hourly', '2026-03-13 09:00:00', '2026-03-13 09:26:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.EXPORTS_DAILY', '2026-03-13 09:05:00', '2026-03-13 09:57:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 09:45:00', '2026-03-13 10:08:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-13 10:00:00', '2026-03-13 10:34:03'),
  ('fin.events_hourly', '2026-03-13 11:00:00', '2026-03-13 11:20:38'),
  ('ana.fraud_hourly', '2026-03-13 10:45:00', '2026-03-13 11:21:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-13 11:00:00', '2026-03-13 11:54:35'),
  ('ana.renewals-four-hourly', '2026-03-13 11:30:00', '2026-03-13 11:56:30'),
  ('fin.events_hourly', '2026-03-13 12:00:00', '2026-03-13 12:16:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-13 11:45:00', '2026-03-13 12:55:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 11:45:00', '2026-03-13 12:57:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 12:45:00', '2026-03-13 13:05:17'),
  ('leg.tickets_weekday', '2026-03-13 12:20:00', '2026-03-13 13:09:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-13 13:15:00', '2026-03-13 13:16:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.search_weekly', '2026-03-13 13:05:00', '2026-03-13 13:28:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 13:45:00', '2026-03-13 14:13:21'),
  ('fin.events_hourly', '2026-03-13 14:00:00', '2026-03-13 14:17:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-13 13:00:00', '2026-03-13 14:31:09'),
  ('ana.search_weekly', '2026-03-13 13:05:00', '2026-03-13 14:40:19'),
  ('ana/churn_daily', '2026-03-13 13:30:00', '2026-03-13 15:00:39'),
  ('lake.accounts_weekday', '2026-03-13 15:15:00', '2026-03-13 15:16:58'),
  ('fin.events_hourly', '2026-03-13 15:00:00', '2026-03-13 15:33:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-13 15:30:00', '2026-03-13 15:56:14'),
  ('ana.fraud_hourly', '2026-03-13 15:45:00', '2026-03-13 15:57:48'),
  ('fin.events_hourly', '2026-03-13 16:00:00', '2026-03-13 16:11:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-13 17:15:00', '2026-03-13 17:16:45'),
  ('fin.events_hourly', '2026-03-13 17:00:00', '2026-03-13 17:21:08'),
  ('leg.forecast_daily', '2026-03-13 17:05:00', '2026-03-13 17:26:06'),
  ('ana.fraud_hourly', '2026-03-13 17:45:00', '2026-03-13 18:04:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-13 18:00:00', '2026-03-13 18:12:51'),
  ('lake.accounts_weekday', '2026-03-13 15:15:00', '2026-03-13 18:13:41'),
  ('leg.search_daily', '2026-03-13 18:15:00', '2026-03-13 18:56:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 18:45:00', '2026-03-13 19:07:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-13 19:00:00', '2026-03-13 19:25:26'),
  ('ana.renewals_four_hourly', '2026-03-13 19:30:00', '2026-03-13 19:38:36'),
  ('leg.tickets_four_hourly', '2026-03-13 17:15:00', '2026-03-13 20:09:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-13 21:00:00', '2026-03-13 21:12:20'),
  ('leg.tickets_four_hourly', '2026-03-13 21:15:00', '2026-03-13 21:17:14'),
  ('fin.refunds_daily', '2026-03-13 21:20:00', '2026-03-13 21:50:33'),
  ('ana.fraud-hourly', '2026-03-13 21:45:00', '2026-03-13 22:09:48'),
  ('fin.events_hourly', '2026-03-13 22:00:00', '2026-03-13 22:18:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-13 23:00:00', '2026-03-13 23:20:45'),
  ('ana.fraud_hourly', '2026-03-13 23:45:00', '2026-03-14 00:06:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-13 23:45:00', '2026-03-14 00:24:42'),
  ('fin.events_hourly', '2026-03-14 00:00:00', '2026-03-14 00:36:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-13 23:30:00', '2026-03-14 00:42:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-14 01:15:00', '2026-03-14 01:17:27'),
  ('ana.fraud_hourly', '2026-03-14 00:45:00', '2026-03-14 01:19:33'),
  ('fin.inventory_daily', '2026-03-14 01:10:00', '2026-03-14 01:20:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-14 01:45:00', '2026-03-14 02:06:57'),
  ('fin.events-hourly', '2026-03-14 02:00:00', '2026-03-14 02:52:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-14 02:45:00', '2026-03-14 03:06:31'),
  ('fin.events_hourly', '2026-03-14 03:00:00', '2026-03-14 03:20:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-14 03:30:00', '2026-03-14 03:51:58'),
  ('fin.renewals_daily', '2026-03-14 01:20:00', '2026-03-14 04:01:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-14 05:15:00', '2026-03-14 05:31:34'),
  ('fin.events_hourly', '2026-03-14 05:00:00', '2026-03-14 06:00:00'),
  ('ana.fraud-hourly', '2026-03-14 04:45:00', '2026-03-14 06:18:01'),
  ('ana/fraud_hourly', '2026-03-14 06:45:00', '2026-03-14 07:04:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-14 07:00:00', '2026-03-14 07:09:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-14 05:45:00', '2026-03-14 07:13:08'),
  ('ana.renewals_four_hourly', '2026-03-14 07:30:00', '2026-03-14 07:50:49'),
  ('fin.events_hourly', '2026-03-14 08:00:00', '2026-03-14 08:11:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-14 07:45:00', '2026-03-14 08:15:58'),
  ('ana.fraud-hourly', '2026-03-14 09:45:00', '2026-03-14 10:03:38'),
  ('fin.events_hourly', '2026-03-14 10:00:00', '2026-03-14 10:22:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/exports_daily', '2026-03-14 09:05:00', '2026-03-14 10:42:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-14 10:45:00', '2026-03-14 10:59:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-14 11:00:00', '2026-03-14 11:15:44'),
  ('ana/fraud_hourly', '2026-03-14 11:45:00', '2026-03-14 12:13:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-14 12:00:00', '2026-03-14 12:24:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-14 11:30:00', '2026-03-14 12:35:47'),
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('ana.fraud_hourly', '2026-03-14 12:45:00', '2026-03-14 12:55:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-14 13:00:00', '2026-03-14 13:19:54'),
  ('leg.quotes_daily', '2026-03-14 13:00:00', '2026-03-14 13:33:23'),
  ('ana.renewals_four_hourly', '2026-03-14 11:30:00', '2026-03-14 13:57:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-14 15:00:00', '2026-03-14 15:15:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-14 11:00:00', '2026-03-14 16:05:56'),
  ('ana.fraud-hourly', '2026-03-14 15:45:00', '2026-03-14 16:18:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-14 16:00:00', '2026-03-14 16:23:22'),
  ('ana.churn_daily', '2026-03-14 13:30:00', '2026-03-14 16:51:52'),
  ('leg.tickets-four-hourly', '2026-03-14 17:15:00', '2026-03-14 17:16:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-14 16:45:00', '2026-03-14 17:26:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-14 13:00:00', '2026-03-14 17:32:16'),
  ('fin.events_hourly', '2026-03-14 17:00:00', '2026-03-14 18:02:19'),
  ('fin.events_hourly', '2026-03-14 18:00:00', '2026-03-14 18:06:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-14 18:45:00', '2026-03-14 18:58:44'),
  ('ana.renewals_four_hourly', '2026-03-14 19:30:00', '2026-03-14 20:00:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-14 21:00:00', '2026-03-14 21:14:53'),
  ('leg.tickets_four_hourly', '2026-03-14 21:15:00', '2026-03-14 21:16:56'),
  ('leg.search-daily', '2026-03-14 18:15:00', '2026-03-14 21:26:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-14 21:20:00', '2026-03-14 21:32:10'),
  ('ana.fraud_hourly', '2026-03-14 20:45:00', '2026-03-14 21:54:55'),
  ('fin.events_hourly', '2026-03-14 22:00:00', '2026-03-14 22:23:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-14 22:45:00', '2026-03-14 23:02:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-14 23:00:00', '2026-03-14 23:10:16'),
  ('ana.renewals_four_hourly', '2026-03-14 23:30:00', '2026-03-14 23:38:57'),
  ('fin.events_hourly', '2026-03-15 00:00:00', '2026-03-15 00:18:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-15 01:00:00', '2026-03-15 01:09:42'),
  ('lake.audits_twice_monthly', '2026-03-15 00:00:00', '2026-03-15 01:15:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.INVENTORY_DAILY', '2026-03-15 01:10:00', '2026-03-15 01:44:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-15 01:10:00', '2026-03-15 01:47:50'),
  ('ana.fraud_hourly', '2026-03-15 01:45:00', '2026-03-15 02:00:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-15 02:00:00', '2026-03-15 02:24:41'),
  ('fin.events_hourly', '2026-03-15 03:00:00', '2026-03-15 03:08:55'),
  ('ana.renewals_four_hourly', '2026-03-15 03:30:00', '2026-03-15 03:47:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-15 03:45:00', '2026-03-15 04:12:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals-four-hourly', '2026-03-14 23:30:00', '2026-03-15 04:37:52'),
  ('ana.fraud_hourly', '2026-03-15 04:45:00', '2026-03-15 05:10:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-15 05:00:00', '2026-03-15 05:10:48'),
  ('leg.tickets_four_hourly', '2026-03-15 05:15:00', '2026-03-15 05:17:30'),
  ('fin.exports_daily', '2026-03-15 01:10:00', '2026-03-15 05:18:08'),
  ('fin.renewals_daily', '2026-03-15 01:20:00', '2026-03-15 05:37:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-15 05:45:00', '2026-03-15 06:07:41'),
  ('fin.events_hourly', '2026-03-15 06:00:00', '2026-03-15 07:03:16'),
  ('fin.events_hourly', '2026-03-15 07:00:00', '2026-03-15 07:14:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-15 07:20:00', '2026-03-15 07:58:40'),
  ('ana.fraud-hourly', '2026-03-15 05:45:00', '2026-03-15 08:10:56'),
  ('ana.fraud_hourly', '2026-03-15 07:45:00', '2026-03-15 08:11:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-15 08:00:00', '2026-03-15 08:12:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-15 08:45:00', '2026-03-15 09:18:01'),
  ('fin.events-hourly', '2026-03-15 09:00:00', '2026-03-15 09:26:00'),
  ('leg.tickets_four_hourly', '2026-03-15 09:15:00', '2026-03-15 09:40:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-03-15 09:05:00', '2026-03-15 09:52:03'),
  ('fin.events_hourly', '2026-03-15 10:00:00', '2026-03-15 10:16:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-15 07:45:00', '2026-03-15 10:45:34'),
  ('ana.fraud_hourly', '2026-03-15 09:45:00', '2026-03-15 11:01:50'),
  ('ana.fraud_hourly', '2026-03-15 10:45:00', '2026-03-15 11:02:06'),
  ('FIN.EVENTS_HOURLY', '2026-03-15 11:00:00', '2026-03-15 11:26:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-15 11:30:00', '2026-03-15 11:43:40'),
  ('ANA.FRAUD_HOURLY', '2026-03-15 11:45:00', '2026-03-15 12:02:06'),
  ('leg.quotes_daily', '2026-03-15 13:00:00', '2026-03-15 13:11:40'),
  ('leg.tickets_four_hourly', '2026-03-15 13:15:00', '2026-03-15 13:17:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-15 13:00:00', '2026-03-15 13:26:05'),
  ('fin.events_hourly', '2026-03-15 14:00:00', '2026-03-15 14:10:22'),
  ('ana.fraud-hourly', '2026-03-15 13:45:00', '2026-03-15 14:11:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-15 15:00:00', '2026-03-15 15:10:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-15 15:30:00', '2026-03-15 15:36:18'),
  ('ana.fraud_hourly', '2026-03-15 14:45:00', '2026-03-15 16:11:46'),
  ('ana.fraud_hourly', '2026-03-15 15:45:00', '2026-03-15 16:17:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-15 16:00:00', '2026-03-15 16:20:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-15 13:00:00', '2026-03-15 17:00:00'),
  ('ana.fraud_hourly', '2026-03-15 16:45:00', '2026-03-15 17:14:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-15 17:15:00', '2026-03-15 17:16:00'),
  ('leg.forecast_daily', '2026-03-15 17:05:00', '2026-03-15 17:16:08'),
  ('fin.events_hourly', '2026-03-15 17:00:00', '2026-03-15 17:26:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-03-15 18:15:00', '2026-03-15 19:12:18'),
  ('ana.shipments_weekday1', '2026-03-15 19:15:00', '2026-03-15 19:18:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-15 19:00:00', '2026-03-15 19:24:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-15 19:30:00', '2026-03-15 19:55:02'),
  ('fin.events_hourly', '2026-03-15 20:00:00', '2026-03-15 20:13:33'),
  ('ana.fraud-hourly', '2026-03-15 19:45:00', '2026-03-15 21:00:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-15 21:00:00', '2026-03-15 21:11:59'),
  ('ana.fraud_hourly', '2026-03-15 20:45:00', '2026-03-15 21:12:18'),
  ('leg.forecast_daily', '2026-03-15 17:05:00', '2026-03-15 21:28:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-15 21:20:00', '2026-03-15 21:51:23'),
  ('ana.fraud_hourly', '2026-03-15 21:45:00', '2026-03-15 22:17:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-15 22:00:00', '2026-03-15 22:24:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-15 23:00:00', '2026-03-15 23:10:50'),
  ('ana.renewals_four_hourly', '2026-03-15 23:30:00', '2026-03-15 23:46:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-15 23:45:00', '2026-03-16 00:03:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 00:00:00', '2026-03-16 00:14:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-16 01:15:00', '2026-03-16 01:17:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-16 00:45:00', '2026-03-16 01:28:00'),
  ('fin.inventory_daily', '2026-03-16 01:10:00', '2026-03-16 01:40:38'),
  ('lake.audits_twice_monthly', '2026-03-16 00:00:00', '2026-03-16 02:11:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.audits_twice_monthly', '2026-03-16 00:00:00', '2026-03-16 02:27:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-16 01:10:00', '2026-03-16 02:40:11'),
  ('lake.alerts_daily', '2026-03-16 03:00:00', '2026-03-16 03:02:57'),
  ('fin.ads-weekday', '2026-03-16 02:10:00', '2026-03-16 03:09:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-16 01:20:00', '2026-03-16 03:12:46'),
  ('ana.fraud_hourly', '2026-03-16 02:45:00', '2026-03-16 03:18:43'),
  ('ana.renewals_four_hourly', '2026-03-16 03:30:00', '2026-03-16 03:38:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-16 03:45:00', '2026-03-16 04:10:14'),
  ('fin.events_hourly', '2026-03-16 04:00:00', '2026-03-16 04:17:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 03:00:00', '2026-03-16 04:22:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 02:00:00', '2026-03-16 04:24:09'),
  ('fin.catalog_weekday', '2026-03-16 04:45:00', '2026-03-16 05:06:29'),
  ('ana.limits_weekday', '2026-03-16 04:20:00', '2026-03-16 05:09:01'),
  ('leg.tickets_four_hourly', '2026-03-16 05:15:00', '2026-03-16 05:18:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-16 06:00:00', '2026-03-16 06:13:39'),
  ('ana.fraud_hourly', '2026-03-16 05:45:00', '2026-03-16 06:18:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-16 01:15:00', '2026-03-16 06:28:11'),
  ('lake.events_weekday', '2026-03-16 06:30:00', '2026-03-16 06:48:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-16 07:20:00', '2026-03-16 07:22:33'),
  ('ana.fraud_hourly', '2026-03-16 07:45:00', '2026-03-16 08:08:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-16 07:30:00', '2026-03-16 08:12:00'),
  ('fin.events-hourly', '2026-03-16 08:00:00', '2026-03-16 08:24:43'),
  ('ana.fraud_hourly', '2026-03-16 08:45:00', '2026-03-16 09:15:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-16 09:15:00', '2026-03-16 09:16:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 10:00:00', '2026-03-16 10:27:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-16 10:45:00', '2026-03-16 11:10:23'),
  ('fin.events-hourly', '2026-03-16 12:00:00', '2026-03-16 12:24:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 13:00:00', '2026-03-16 13:12:01'),
  ('leg.tickets_weekday', '2026-03-16 12:20:00', '2026-03-16 13:14:31'),
  ('leg.tickets_four_hourly', '2026-03-16 13:15:00', '2026-03-16 13:17:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-16 13:00:00', '2026-03-16 13:27:34'),
  ('leg.exports_daily', '2026-03-16 09:05:00', '2026-03-16 13:45:14'),
  ('ana.fraud_hourly', '2026-03-16 13:45:00', '2026-03-16 14:01:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 14:00:00', '2026-03-16 14:12:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.BUDGETS_DAILY1', '2026-03-16 13:00:00', '2026-03-16 14:33:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-16 14:45:00', '2026-03-16 15:15:27'),
  ('lake.accounts_weekday', '2026-03-16 15:15:00', '2026-03-16 15:16:42'),
  ('fin.events_hourly', '2026-03-16 15:00:00', '2026-03-16 15:16:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-16 15:30:00', '2026-03-16 15:37:37'),
  ('ana.fraud_hourly', '2026-03-16 14:45:00', '2026-03-16 15:52:57'),
  ('fin.events_hourly', '2026-03-16 16:00:00', '2026-03-16 16:09:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-16 16:45:00', '2026-03-16 16:55:53'),
  ('leg.forecast_daily', '2026-03-16 17:05:00', '2026-03-16 17:21:50'),
  ('ana.fraud-hourly', '2026-03-16 17:45:00', '2026-03-16 18:10:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-03-16 13:30:00', '2026-03-16 18:11:43'),
  ('FIN.EVENTS_HOURLY', '2026-03-16 18:00:00', '2026-03-16 18:25:51'),
  ('ana.shipments_weekday1', '2026-03-16 19:15:00', '2026-03-16 19:18:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 16:00:00', '2026-03-16 19:28:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-16 18:45:00', '2026-03-16 19:37:55'),
  ('ana.renewals_four_hourly', '2026-03-16 19:30:00', '2026-03-16 19:40:05'),
  ('ana.fraud_hourly', '2026-03-16 19:45:00', '2026-03-16 20:03:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 20:00:00', '2026-03-16 20:14:09'),
  ('ana.fraud_hourly', '2026-03-16 20:45:00', '2026-03-16 21:12:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-16 21:15:00', '2026-03-16 21:17:32'),
  ('fin.events_hourly', '2026-03-16 21:00:00', '2026-03-16 21:25:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-16 21:20:00', '2026-03-16 21:36:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-16 21:45:00', '2026-03-16 21:55:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-16 18:00:00', '2026-03-16 22:04:06'),
  ('fin.events_hourly', '2026-03-16 22:00:00', '2026-03-16 22:36:02'),
  ('ana.fraud_hourly', '2026-03-16 22:45:00', '2026-03-16 23:03:31'),
  ('fin/events_hourly', '2026-03-16 23:00:00', '2026-03-16 23:12:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-16 23:30:00', '2026-03-16 23:53:40'),
  ('fin.events_hourly', '2026-03-17 00:00:00', '2026-03-17 01:00:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-17 01:00:00', '2026-03-17 01:12:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets-four-hourly', '2026-03-17 01:15:00', '2026-03-17 01:16:28'),
  ('fin.inventory_daily', '2026-03-17 01:10:00', '2026-03-17 01:27:33'),
  ('fin.events_hourly', '2026-03-17 01:00:00', '2026-03-17 02:21:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-16 23:00:00', '2026-03-17 02:25:24'),
  ('fin.renewals-daily', '2026-03-17 01:20:00', '2026-03-17 02:35:26'),
  ('fin.events_hourly', '2026-03-17 02:00:00', '2026-03-17 02:49:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-17 02:10:00', '2026-03-17 02:54:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-17 02:45:00', '2026-03-17 03:19:42'),
  ('fin.events_hourly', '2026-03-17 03:00:00', '2026-03-17 03:26:28'),
  ('ana.renewals_four_hourly', '2026-03-17 03:30:00', '2026-03-17 03:57:42'),
  ('fin.events_hourly', '2026-03-17 04:00:00', '2026-03-17 04:21:34'),
  ('ana.limits_weekday', '2026-03-17 04:20:00', '2026-03-17 04:48:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.catalog_weekday', '2026-03-17 04:45:00', '2026-03-17 05:06:24'),
  ('fin.events_hourly', '2026-03-17 05:00:00', '2026-03-17 05:15:58'),
  ('leg.tickets_four_hourly', '2026-03-17 05:15:00', '2026-03-17 05:17:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-17 01:10:00', '2026-03-17 06:10:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-17 06:00:00', '2026-03-17 06:19:43'),
  ('ana.fraud_hourly', '2026-03-17 05:45:00', '2026-03-17 06:37:17'),
  ('lake.search-weekday', '2026-03-17 06:15:00', '2026-03-17 06:53:59'),
  ('ana.fraud_hourly', '2026-03-17 06:45:00', '2026-03-17 07:08:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-03-17 06:30:00', '2026-03-17 07:20:17'),
  ('fin.events_hourly', '2026-03-17 07:00:00', '2026-03-17 07:22:44'),
  ('ana.renewals_four_hourly', '2026-03-17 07:30:00', '2026-03-17 07:47:41'),
  ('fin.events_hourly', '2026-03-17 08:00:00', '2026-03-17 08:17:49'),
  ('ana.fraud_hourly', '2026-03-17 07:45:00', '2026-03-17 08:25:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-17 07:45:00', '2026-03-17 09:01:01'),
  ('fin.events_hourly', '2026-03-17 09:00:00', '2026-03-17 09:09:25'),
  ('ana.fraud_hourly', '2026-03-17 05:45:00', '2026-03-17 09:27:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-17 06:45:00', '2026-03-17 09:45:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-17 09:45:00', '2026-03-17 10:19:06'),
  ('fin.events-hourly', '2026-03-17 10:00:00', '2026-03-17 11:09:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-17 11:00:00', '2026-03-17 11:19:03'),
  ('fin.events_hourly', '2026-03-17 06:00:00', '2026-03-17 11:32:44'),
  ('ana.renewals_four_hourly', '2026-03-17 11:30:00', '2026-03-17 11:43:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-17 11:45:00', '2026-03-17 12:04:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-17 10:45:00', '2026-03-17 12:09:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-17 12:00:00', '2026-03-17 12:19:14'),
  ('leg/tickets_four_hourly', '2026-03-17 13:15:00', '2026-03-17 13:16:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-17 13:00:00', '2026-03-17 13:18:26'),
  ('leg.tickets_weekday', '2026-03-17 12:20:00', '2026-03-17 13:23:55'),
  ('leg.quotes_daily', '2026-03-17 13:00:00', '2026-03-17 13:27:34'),
  ('fin.events_hourly', '2026-03-17 14:00:00', '2026-03-17 14:13:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-17 13:45:00', '2026-03-17 14:20:42'),
  ('ana.fraud_hourly', '2026-03-17 14:45:00', '2026-03-17 15:06:02'),
  ('lake.accounts-weekday', '2026-03-17 15:15:00', '2026-03-17 15:17:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-17 15:00:00', '2026-03-17 15:19:23'),
  ('ana/renewals_four_hourly', '2026-03-17 15:30:00', '2026-03-17 15:53:48'),
  ('fin.budgets_daily1', '2026-03-17 13:00:00', '2026-03-17 15:54:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/churn_daily', '2026-03-17 13:30:00', '2026-03-17 16:06:49'),
  ('fin.events_hourly', '2026-03-17 16:00:00', '2026-03-17 16:18:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-17 16:45:00', '2026-03-17 17:12:18'),
  ('fin.events_hourly', '2026-03-17 17:00:00', '2026-03-17 17:23:02'),
  ('leg.forecast_daily', '2026-03-17 17:05:00', '2026-03-17 17:54:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-17 16:00:00', '2026-03-17 18:32:40'),
  ('fin.events_hourly', '2026-03-17 18:00:00', '2026-03-17 18:52:30'),
  ('ana.fraud_hourly', '2026-03-17 18:45:00', '2026-03-17 18:54:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-17 17:45:00', '2026-03-17 19:08:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-17 19:15:00', '2026-03-17 19:16:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-17 19:00:00', '2026-03-17 19:26:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-17 19:30:00', '2026-03-17 19:51:01'),
  ('ana.fraud_hourly', '2026-03-17 19:45:00', '2026-03-17 20:14:52'),
  ('ana.fraud_hourly', '2026-03-17 20:45:00', '2026-03-17 20:54:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-03-17 18:15:00', '2026-03-17 21:09:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-17 21:15:00', '2026-03-17 21:18:15'),
  ('fin.events-hourly', '2026-03-17 21:00:00', '2026-03-17 21:20:57'),
  ('fin.refunds_daily', '2026-03-17 21:20:00', '2026-03-17 21:38:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-17 21:45:00', '2026-03-17 22:13:57'),
  ('fin.events-hourly', '2026-03-17 22:00:00', '2026-03-17 22:16:47'),
  ('ana.fraud-hourly', '2026-03-17 22:45:00', '2026-03-17 23:17:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-17 23:00:00', '2026-03-17 23:51:12'),
  ('ana.renewals_four_hourly', '2026-03-17 23:30:00', '2026-03-17 23:52:52'),
  ('fin.events_hourly', '2026-03-18 00:00:00', '2026-03-18 00:17:43'),
  ('ana.fraud_hourly', '2026-03-17 23:45:00', '2026-03-18 00:38:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-17 19:30:00', '2026-03-18 00:42:45'),
  ('leg.tickets_four_hourly', '2026-03-18 01:15:00', '2026-03-18 01:16:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-18 01:00:00', '2026-03-18 01:22:47'),
  ('FIN.EXPORTS_DAILY', '2026-03-18 01:10:00', '2026-03-18 01:35:09'),
  ('ANA.FRAUD_HOURLY', '2026-03-18 00:45:00', '2026-03-18 01:42:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-18 01:10:00', '2026-03-18 01:50:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-18 01:20:00', '2026-03-18 02:04:25'),
  ('fin.ads_weekday', '2026-03-18 02:10:00', '2026-03-18 02:31:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-18 01:45:00', '2026-03-18 02:41:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LAKE.ALERTS_DAILY', '2026-03-18 03:00:00', '2026-03-18 03:01:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-18 02:45:00', '2026-03-18 03:05:26'),
  ('fin.events_hourly', '2026-03-18 01:00:00', '2026-03-18 03:37:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-18 03:30:00', '2026-03-18 03:45:38'),
  ('ana.fraud_hourly', '2026-03-18 03:45:00', '2026-03-18 04:19:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-18 04:00:00', '2026-03-18 04:28:16'),
  ('leg/tickets_four_hourly', '2026-03-18 05:15:00', '2026-03-18 05:16:50'),
  ('ana.fraud_hourly', '2026-03-18 04:45:00', '2026-03-18 05:38:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-18 06:00:00', '2026-03-18 06:07:44'),
  ('lake.events_weekday', '2026-03-18 06:30:00', '2026-03-18 06:58:00'),
  ('lake.clicks_daily', '2026-03-18 07:20:00', '2026-03-18 07:21:52'),
  ('FIN.EVENTS_HOURLY', '2026-03-18 07:00:00', '2026-03-18 07:26:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.LIMITS_WEEKDAY', '2026-03-18 04:20:00', '2026-03-18 07:47:18'),
  ('ana.renewals_four_hourly', '2026-03-18 07:30:00', '2026-03-18 07:47:21'),
  ('ana.fraud_hourly', '2026-03-18 06:45:00', '2026-03-18 08:04:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-18 07:45:00', '2026-03-18 08:19:40'),
  ('ana.fraud_hourly', '2026-03-18 08:45:00', '2026-03-18 09:07:27'),
  ('leg.tickets_four_hourly', '2026-03-18 09:15:00', '2026-03-18 09:16:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-18 09:00:00', '2026-03-18 09:27:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-18 10:00:00', '2026-03-18 10:05:17'),
  ('ana.fraud_hourly', '2026-03-18 09:45:00', '2026-03-18 10:19:46'),
  ('fin.events_hourly', '2026-03-18 11:00:00', '2026-03-18 11:18:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-18 10:45:00', '2026-03-18 11:51:07'),
  ('ana.renewals_four_hourly', '2026-03-18 11:30:00', '2026-03-18 11:51:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-18 11:45:00', '2026-03-18 12:34:59'),
  ('lake.clicks_daily', '2026-03-18 07:20:00', '2026-03-18 12:45:34'),
  ('LEG.EXPORTS_DAILY', '2026-03-18 09:05:00', '2026-03-18 13:04:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-18 13:00:00', '2026-03-18 13:07:25'),
  ('fin/events_hourly', '2026-03-18 12:00:00', '2026-03-18 13:09:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-18 13:00:00', '2026-03-18 13:18:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-18 13:00:00', '2026-03-18 13:23:11'),
  ('leg.tickets-weekday', '2026-03-18 12:20:00', '2026-03-18 13:24:28'),
  ('ana.fraud_hourly', '2026-03-18 13:45:00', '2026-03-18 14:07:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-18 14:00:00', '2026-03-18 14:26:14'),
  ('ana.fraud-hourly', '2026-03-18 14:45:00', '2026-03-18 15:02:08'),
  ('fin.events_hourly', '2026-03-18 15:00:00', '2026-03-18 15:09:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-03-18 15:15:00', '2026-03-18 15:16:40'),
  ('fin.events_hourly', '2026-03-18 11:00:00', '2026-03-18 15:18:06'),
  ('ana.churn_daily', '2026-03-18 13:30:00', '2026-03-18 15:44:50'),
  ('ana.renewals_four_hourly', '2026-03-18 15:30:00', '2026-03-18 15:51:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-18 15:45:00', '2026-03-18 16:05:55'),
  ('fin.events-hourly', '2026-03-18 16:00:00', '2026-03-18 16:18:43'),
  ('ana.fraud_hourly', '2026-03-18 16:45:00', '2026-03-18 17:01:04'),
  ('leg.tickets_four_hourly', '2026-03-18 17:15:00', '2026-03-18 17:15:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-18 17:00:00', '2026-03-18 17:41:01'),
  ('ana.fraud_hourly', '2026-03-18 17:45:00', '2026-03-18 18:16:58'),
  ('fin.events_hourly', '2026-03-18 18:00:00', '2026-03-18 18:19:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-18 18:45:00', '2026-03-18 19:02:51'),
  ('fin.events_hourly', '2026-03-18 19:00:00', '2026-03-18 19:12:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.SHIPMENTS_WEEKDAY1', '2026-03-18 19:15:00', '2026-03-18 19:17:57'),
  ('ana.fraud_hourly', '2026-03-18 19:45:00', '2026-03-18 20:13:36'),
  ('fin.events_hourly', '2026-03-18 20:00:00', '2026-03-18 20:17:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-18 18:00:00', '2026-03-18 20:57:17'),
  ('ana.fraud-hourly', '2026-03-18 20:45:00', '2026-03-18 21:04:35'),
  ('leg.tickets_four_hourly', '2026-03-18 21:15:00', '2026-03-18 21:16:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-18 21:00:00', '2026-03-18 21:20:47'),
  ('fin.refunds_daily', '2026-03-18 21:20:00', '2026-03-18 21:40:38'),
  ('ana.fraud_hourly', '2026-03-18 21:45:00', '2026-03-18 22:03:53'),
  ('leg.tickets_four_hourly', '2026-03-18 21:15:00', '2026-03-18 22:04:01'),
  ('fin.events-hourly', '2026-03-18 22:00:00', '2026-03-18 22:16:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-18 19:15:00', '2026-03-18 22:24:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-18 22:45:00', '2026-03-18 22:56:16'),
  ('ana.renewals_four_hourly', '2026-03-18 23:30:00', '2026-03-18 23:50:07'),
  ('ana.fraud_hourly', '2026-03-18 23:45:00', '2026-03-19 00:12:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-19 00:00:00', '2026-03-19 00:26:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-19 01:00:00', '2026-03-19 01:14:06'),
  ('leg.tickets_four_hourly', '2026-03-19 01:15:00', '2026-03-19 01:18:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-19 01:10:00', '2026-03-19 01:22:50'),
  ('ana/fraud_hourly', '2026-03-19 00:45:00', '2026-03-19 02:08:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-19 02:45:00', '2026-03-19 02:54:48'),
  ('lake.alerts_daily', '2026-03-19 03:00:00', '2026-03-19 03:02:27'),
  ('fin.events_hourly', '2026-03-19 03:00:00', '2026-03-19 03:13:17'),
  ('fin.events_hourly', '2026-03-18 22:00:00', '2026-03-19 03:13:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-19 02:10:00', '2026-03-19 03:15:48'),
  ('ana.renewals_four_hourly', '2026-03-19 03:30:00', '2026-03-19 03:55:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-19 03:45:00', '2026-03-19 04:08:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.catalog_weekday', '2026-03-19 04:45:00', '2026-03-19 04:58:57'),
  ('ana.fraud_hourly', '2026-03-19 04:45:00', '2026-03-19 05:20:19'),
  ('fin.events_hourly', '2026-03-19 05:00:00', '2026-03-19 06:09:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.limits_weekday', '2026-03-19 04:20:00', '2026-03-19 06:09:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-19 06:00:00', '2026-03-19 06:38:22'),
  ('ana.fraud-hourly', '2026-03-19 05:45:00', '2026-03-19 07:05:48'),
  ('ana.fraud_hourly', '2026-03-19 06:45:00', '2026-03-19 07:09:42'),
  ('fin.events_hourly', '2026-03-19 07:00:00', '2026-03-19 07:09:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-19 07:20:00', '2026-03-19 07:21:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-19 06:15:00', '2026-03-19 07:22:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-19 07:30:00', '2026-03-19 07:47:04'),
  ('fin.events-hourly', '2026-03-19 08:00:00', '2026-03-19 08:15:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-19 07:45:00', '2026-03-19 08:17:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-19 03:45:00', '2026-03-19 08:27:09'),
  ('leg.tickets_four_hourly', '2026-03-19 09:15:00', '2026-03-19 09:16:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-19 08:45:00', '2026-03-19 09:17:49'),
  ('ana.fraud_hourly', '2026-03-19 09:45:00', '2026-03-19 10:00:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-19 10:00:00', '2026-03-19 10:41:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-19 10:45:00', '2026-03-19 11:12:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-19 11:00:00', '2026-03-19 11:25:11'),
  ('ana.fraud_hourly', '2026-03-19 11:45:00', '2026-03-19 12:13:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-19 12:00:00', '2026-03-19 12:26:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-19 12:45:00', '2026-03-19 12:53:59'),
  ('fin.events-hourly', '2026-03-19 13:00:00', '2026-03-19 13:47:41'),
  ('ana.fraud_hourly', '2026-03-19 08:45:00', '2026-03-19 13:59:53'),
  ('ana.fraud_hourly', '2026-03-19 13:45:00', '2026-03-19 14:16:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-19 13:00:00', '2026-03-19 14:33:57'),
  ('fin.events_hourly', '2026-03-19 12:00:00', '2026-03-19 14:57:49'),
  ('ana.fraud_hourly', '2026-03-19 14:45:00', '2026-03-19 14:59:54'),
  ('fin.events_hourly', '2026-03-19 15:00:00', '2026-03-19 15:14:11'),
  ('leg.tickets_four_hourly', '2026-03-19 13:15:00', '2026-03-19 15:15:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-03-19 15:15:00', '2026-03-19 15:17:27'),
  ('ana.fraud_hourly', '2026-03-19 13:45:00', '2026-03-19 15:19:24'),
  ('ana.churn_daily', '2026-03-19 13:30:00', '2026-03-19 15:27:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-19 15:30:00', '2026-03-19 15:51:04'),
  ('ana.fraud-hourly', '2026-03-19 15:45:00', '2026-03-19 16:18:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-19 17:15:00', '2026-03-19 17:16:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-19 17:00:00', '2026-03-19 17:23:53'),
  ('fin.events_hourly', '2026-03-19 18:00:00', '2026-03-19 18:24:01'),
  ('ana.fraud_hourly', '2026-03-19 18:45:00', '2026-03-19 19:11:04'),
  ('ana.shipments-weekday1', '2026-03-19 19:15:00', '2026-03-19 19:17:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-19 19:30:00', '2026-03-19 19:46:19'),
  ('ana.fraud-hourly', '2026-03-19 19:45:00', '2026-03-19 19:56:33'),
  ('fin.events_hourly', '2026-03-19 20:00:00', '2026-03-19 20:11:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-19 18:45:00', '2026-03-19 20:31:33'),
  ('ana.fraud_hourly', '2026-03-19 20:45:00', '2026-03-19 20:53:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-19 21:00:00', '2026-03-19 21:12:10'),
  ('fin.refunds_daily', '2026-03-19 21:20:00', '2026-03-19 21:40:01'),
  ('leg.tickets-four-hourly', '2026-03-19 21:15:00', '2026-03-19 21:47:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-19 22:00:00', '2026-03-19 22:27:05'),
  ('leg.tickets_four_hourly', '2026-03-19 21:15:00', '2026-03-19 22:33:24'),
  ('ana.fraud_hourly', '2026-03-19 22:45:00', '2026-03-19 23:12:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-19 23:00:00', '2026-03-19 23:14:47'),
  ('ana.fraud_hourly', '2026-03-19 23:45:00', '2026-03-20 00:05:38'),
  ('fin.events_hourly', '2026-03-20 00:00:00', '2026-03-20 00:27:11'),
  ('fin.events_hourly', '2026-03-20 01:00:00', '2026-03-20 01:07:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-20 01:15:00', '2026-03-20 01:15:12'),
  ('fin.inventory_daily', '2026-03-20 01:10:00', '2026-03-20 01:45:12'),
  ('fin/exports_daily', '2026-03-20 01:10:00', '2026-03-20 02:51:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-20 03:00:00', '2026-03-20 03:00:53'),
  ('ana.fraud_hourly', '2026-03-20 02:45:00', '2026-03-20 03:17:34'),
  ('fin.ads_weekday', '2026-03-20 02:10:00', '2026-03-20 03:52:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-20 03:45:00', '2026-03-20 04:07:44'),
  ('ana.renewals_four_hourly', '2026-03-20 03:30:00', '2026-03-20 04:12:46'),
  ('fin.events_hourly', '2026-03-20 01:00:00', '2026-03-20 04:52:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-20 04:45:00', '2026-03-20 05:09:51'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-20 05:15:00', '2026-03-20 05:17:14'),
  ('fin.ads_weekday', '2026-03-20 02:10:00', '2026-03-20 05:42:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-20 05:45:00', '2026-03-20 06:08:29'),
  ('scratch.tmp_vendors_2', '2026-03-20 06:00:00', '2026-03-20 06:25:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-20 06:15:00', '2026-03-20 06:56:21'),
  ('fin.events_hourly', '2026-03-20 06:00:00', '2026-03-20 07:03:38'),
  ('fin.events_hourly', '2026-03-20 05:00:00', '2026-03-20 07:06:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-20 06:45:00', '2026-03-20 07:09:58'),
  ('lake.events_weekday', '2026-03-20 06:30:00', '2026-03-20 07:16:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-20 07:00:00', '2026-03-20 07:17:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-20 02:00:00', '2026-03-20 07:17:15'),
  ('ana.limits_weekday', '2026-03-20 04:20:00', '2026-03-20 07:30:01'),
  ('lake.clicks-daily', '2026-03-20 07:20:00', '2026-03-20 07:32:07'),
  ('ana.renewals_four_hourly', '2026-03-20 07:30:00', '2026-03-20 07:50:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-20 02:00:00', '2026-03-20 07:53:55'),
  ('fin.events_hourly', '2026-03-20 08:00:00', '2026-03-20 08:13:53'),
  ('ana.fraud_hourly', '2026-03-20 08:45:00', '2026-03-20 08:59:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-20 09:15:00', '2026-03-20 09:17:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-03-20 09:05:00', '2026-03-20 09:55:14'),
  ('fin.events_hourly', '2026-03-20 09:00:00', '2026-03-20 10:03:33'),
  ('ana.fraud_hourly', '2026-03-20 09:45:00', '2026-03-20 10:14:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-20 05:15:00', '2026-03-20 10:14:34'),
  ('fin.events_hourly', '2026-03-20 10:00:00', '2026-03-20 10:24:25'),
  ('fin.events_hourly', '2026-03-20 11:00:00', '2026-03-20 11:15:21'),
  ('ana.fraud-hourly', '2026-03-20 10:45:00', '2026-03-20 11:15:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-20 12:00:00', '2026-03-20 12:15:31'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-20 09:15:00', '2026-03-20 12:22:12'),
  ('fin.events_hourly', '2026-03-20 13:00:00', '2026-03-20 13:13:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.search_weekly', '2026-03-20 13:05:00', '2026-03-20 13:16:29'),
  ('ana.fraud_hourly', '2026-03-20 12:45:00', '2026-03-20 13:27:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-20 13:00:00', '2026-03-20 13:34:29'),
  ('fin/budgets_daily1', '2026-03-20 13:00:00', '2026-03-20 13:50:44'),
  ('ana.fraud_hourly', '2026-03-20 13:45:00', '2026-03-20 14:18:59'),
  ('ana.churn_daily', '2026-03-20 13:30:00', '2026-03-20 14:47:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-20 14:45:00', '2026-03-20 14:57:07'),
  ('fin.events_hourly', '2026-03-20 14:00:00', '2026-03-20 15:01:58'),
  ('ana.renewals_four_hourly', '2026-03-20 15:30:00', '2026-03-20 16:04:24'),
  ('ana.fraud_hourly', '2026-03-20 15:45:00', '2026-03-20 16:07:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-20 12:20:00', '2026-03-20 16:17:54'),
  ('ana.fraud_hourly', '2026-03-20 16:45:00', '2026-03-20 17:02:19'),
  ('fin.events_hourly', '2026-03-20 17:00:00', '2026-03-20 17:11:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-20 17:15:00', '2026-03-20 17:16:38'),
  ('leg.forecast_daily', '2026-03-20 17:05:00', '2026-03-20 17:17:12'),
  ('fin.events_hourly', '2026-03-20 18:00:00', '2026-03-20 18:19:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-20 17:45:00', '2026-03-20 18:37:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-20 18:45:00', '2026-03-20 18:58:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-03-20 18:15:00', '2026-03-20 18:59:36'),
  ('fin.events_hourly', '2026-03-20 19:00:00', '2026-03-20 19:12:15'),
  ('ana.renewals-four-hourly', '2026-03-20 19:30:00', '2026-03-20 19:57:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-20 20:00:00', '2026-03-20 20:19:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-20 12:20:00', '2026-03-20 21:07:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-20 21:15:00', '2026-03-20 21:16:54'),
  ('fin.refunds_daily', '2026-03-20 21:20:00', '2026-03-20 21:33:08'),
  ('ana.fraud_hourly', '2026-03-20 20:45:00', '2026-03-20 21:46:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-20 21:45:00', '2026-03-20 21:59:58'),
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-20 19:30:00', '2026-03-20 22:11:30'),
  ('fin.events_hourly', '2026-03-20 22:00:00', '2026-03-20 22:12:08'),
  ('fin.events-hourly', '2026-03-20 23:00:00', '2026-03-20 23:25:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-20 23:30:00', '2026-03-20 23:57:35'),
  ('ANA.FRAUD_HOURLY', '2026-03-20 23:45:00', '2026-03-21 00:03:52'),
  ('ana.fraud_hourly', '2026-03-21 00:45:00', '2026-03-21 01:02:02'),
  ('fin.events_hourly', '2026-03-21 01:00:00', '2026-03-21 01:11:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-21 01:15:00', '2026-03-21 01:16:21'),
  ('fin.inventory_daily', '2026-03-21 01:10:00', '2026-03-21 01:20:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-21 01:10:00', '2026-03-21 01:45:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 01:45:00', '2026-03-21 02:55:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-21 03:00:00', '2026-03-21 03:01:10'),
  ('ana.fraud-hourly', '2026-03-21 02:45:00', '2026-03-21 03:09:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals-four-hourly', '2026-03-21 03:30:00', '2026-03-21 03:39:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-21 02:00:00', '2026-03-21 03:58:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-21 03:45:00', '2026-03-21 04:01:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-21 05:15:00', '2026-03-21 05:16:39'),
  ('ana.fraud_hourly', '2026-03-21 04:45:00', '2026-03-21 05:21:53'),
  ('ana.fraud_hourly', '2026-03-21 03:45:00', '2026-03-21 06:01:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-21 05:00:00', '2026-03-21 06:03:42'),
  ('fin.exports_daily', '2026-03-21 01:10:00', '2026-03-21 06:09:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-21 06:00:00', '2026-03-21 06:21:20'),
  ('ana.fraud_hourly', '2026-03-21 06:45:00', '2026-03-21 07:17:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-21 07:20:00', '2026-03-21 07:22:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-21 07:00:00', '2026-03-21 08:04:33'),
  ('ana.fraud_hourly', '2026-03-21 07:45:00', '2026-03-21 08:15:51'),
  ('fin.events_hourly', '2026-03-21 08:00:00', '2026-03-21 08:26:05'),
  ('leg.tickets_four_hourly', '2026-03-21 09:15:00', '2026-03-21 09:35:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports_daily', '2026-03-21 09:05:00', '2026-03-21 09:50:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-21 09:00:00', '2026-03-21 10:06:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 09:45:00', '2026-03-21 10:09:50'),
  ('ANA.FRAUD_HOURLY', '2026-03-21 10:45:00', '2026-03-21 11:03:50'),
  ('fin.events_hourly', '2026-03-21 10:00:00', '2026-03-21 11:07:15'),
  ('fin.events_hourly', '2026-03-21 11:00:00', '2026-03-21 11:08:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 11:45:00', '2026-03-21 12:07:47'),
  ('fin.events_hourly', '2026-03-21 13:00:00', '2026-03-21 13:14:28'),
  ('leg.tickets_four_hourly', '2026-03-21 13:15:00', '2026-03-21 13:16:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 12:45:00', '2026-03-21 13:39:21'),
  ('leg.tickets_four_hourly', '2026-03-21 09:15:00', '2026-03-21 14:04:25'),
  ('fin.budgets_daily1', '2026-03-21 13:00:00', '2026-03-21 14:07:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 13:45:00', '2026-03-21 14:14:26'),
  ('fin.events_hourly', '2026-03-21 14:00:00', '2026-03-21 14:24:40'),
  ('ana.fraud-hourly', '2026-03-21 14:45:00', '2026-03-21 15:07:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-21 15:00:00', '2026-03-21 15:10:29'),
  ('ana.fraud_hourly', '2026-03-21 11:45:00', '2026-03-21 15:35:09'),
  ('ana.renewals_four_hourly', '2026-03-21 15:30:00', '2026-03-21 15:54:48'),
  ('ANA.FRAUD_HOURLY', '2026-03-21 15:45:00', '2026-03-21 16:19:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 16:45:00', '2026-03-21 17:09:47'),
  ('fin.events_hourly', '2026-03-21 17:00:00', '2026-03-21 17:22:53'),
  ('leg.forecast_daily', '2026-03-21 17:05:00', '2026-03-21 17:27:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 14:45:00', '2026-03-21 17:41:07'),
  ('ana/fraud_hourly', '2026-03-21 18:45:00', '2026-03-21 18:55:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-21 19:00:00', '2026-03-21 19:10:02'),
  ('leg.search_daily', '2026-03-21 18:15:00', '2026-03-21 19:32:18'),
  ('ana.renewals_four_hourly', '2026-03-21 19:30:00', '2026-03-21 19:49:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-21 20:00:00', '2026-03-21 20:06:52'),
  ('ana.fraud-hourly', '2026-03-21 19:45:00', '2026-03-21 20:08:19'),
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('leg.tickets_four_hourly', '2026-03-21 17:15:00', '2026-03-21 20:22:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 20:45:00', '2026-03-21 21:09:11'),
  ('leg.tickets_four_hourly', '2026-03-21 21:15:00', '2026-03-21 21:24:21'),
  ('fin.refunds_daily', '2026-03-21 21:20:00', '2026-03-21 21:54:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-03-21 17:05:00', '2026-03-21 22:11:51'),
  ('ana.fraud-hourly', '2026-03-21 21:45:00', '2026-03-21 22:15:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-21 22:00:00', '2026-03-21 22:24:32'),
  ('fin.events_hourly', '2026-03-21 19:00:00', '2026-03-21 22:28:15'),
  ('ana.fraud_hourly', '2026-03-21 22:45:00', '2026-03-21 23:07:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-21 23:30:00', '2026-03-21 23:36:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 23:45:00', '2026-03-22 00:20:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-22 00:00:00', '2026-03-22 00:24:47'),
  ('fin.events_hourly', '2026-03-22 01:00:00', '2026-03-22 01:08:26'),
  ('ana.fraud_hourly', '2026-03-22 00:45:00', '2026-03-22 01:13:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 22:45:00', '2026-03-22 01:29:25'),
  ('leg.tickets_four_hourly', '2026-03-22 01:15:00', '2026-03-22 01:34:14'),
  ('fin.inventory_daily', '2026-03-22 01:10:00', '2026-03-22 01:35:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-21 23:45:00', '2026-03-22 02:16:24'),
  ('fin.exports_daily', '2026-03-22 01:10:00', '2026-03-22 02:26:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-22 01:20:00', '2026-03-22 02:30:10'),
  ('ana.fraud_hourly', '2026-03-22 01:45:00', '2026-03-22 03:21:47'),
  ('fin.events_hourly', '2026-03-22 00:00:00', '2026-03-22 03:39:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals-four-hourly', '2026-03-22 03:30:00', '2026-03-22 03:47:09'),
  ('ana/fraud_hourly', '2026-03-22 03:45:00', '2026-03-22 04:13:06'),
  ('leg.tickets_four_hourly', '2026-03-22 05:15:00', '2026-03-22 05:21:14'),
  ('ana.fraud_hourly', '2026-03-22 05:45:00', '2026-03-22 06:17:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-22 03:00:00', '2026-03-22 06:35:05'),
  ('fin.events-hourly', '2026-03-22 06:00:00', '2026-03-22 06:41:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-22 02:00:00', '2026-03-22 06:42:34'),
  ('fin.events_hourly', '2026-03-22 04:00:00', '2026-03-22 06:47:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-22 05:00:00', '2026-03-22 07:10:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-22 07:20:00', '2026-03-22 07:22:27'),
  ('ANA.FRAUD_HOURLY', '2026-03-22 06:45:00', '2026-03-22 07:55:19'),
  ('ana.renewals_four_hourly', '2026-03-22 07:30:00', '2026-03-22 07:57:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-22 07:00:00', '2026-03-22 08:10:22'),
  ('FIN.EVENTS_HOURLY', '2026-03-22 08:00:00', '2026-03-22 09:14:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 08:45:00', '2026-03-22 09:14:43'),
  ('leg.tickets_four_hourly', '2026-03-22 09:15:00', '2026-03-22 09:17:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 09:45:00', '2026-03-22 10:02:56'),
  ('ana.fraud_hourly', '2026-03-22 05:45:00', '2026-03-22 10:11:47'),
  ('leg.exports_daily', '2026-03-22 09:05:00', '2026-03-22 10:42:34'),
  ('fin.events_hourly', '2026-03-22 10:00:00', '2026-03-22 10:58:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 10:45:00', '2026-03-22 11:05:08'),
  ('ana.renewals_four_hourly', '2026-03-22 11:30:00', '2026-03-22 11:40:14'),
  ('ana.fraud_hourly', '2026-03-22 11:45:00', '2026-03-22 12:03:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-22 13:00:00', '2026-03-22 13:05:59'),
  ('leg.tickets_four_hourly', '2026-03-22 13:15:00', '2026-03-22 13:16:43'),
  ('leg.quotes_daily', '2026-03-22 13:00:00', '2026-03-22 13:17:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 13:45:00', '2026-03-22 13:59:40'),
  ('fin.budgets_daily1', '2026-03-22 13:00:00', '2026-03-22 14:27:53'),
  ('ana.fraud_hourly', '2026-03-22 13:45:00', '2026-03-22 14:37:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-22 14:00:00', '2026-03-22 14:45:11'),
  ('ana.churn-daily', '2026-03-22 13:30:00', '2026-03-22 14:51:13'),
  ('ana.fraud_hourly', '2026-03-22 14:45:00', '2026-03-22 15:06:58'),
  ('fin.events_hourly', '2026-03-22 15:00:00', '2026-03-22 15:24:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-22 15:30:00', '2026-03-22 16:06:16'),
  ('ana.fraud_hourly', '2026-03-22 15:45:00', '2026-03-22 16:10:48'),
  ('fin.events_hourly', '2026-03-22 16:00:00', '2026-03-22 16:23:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 16:45:00', '2026-03-22 17:12:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-03-22 17:05:00', '2026-03-22 17:16:22'),
  ('fin.events_hourly', '2026-03-22 17:00:00', '2026-03-22 17:26:22'),
  ('fin.events_hourly', '2026-03-22 18:00:00', '2026-03-22 18:26:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 17:45:00', '2026-03-22 18:27:12'),
  ('leg.tickets_four_hourly', '2026-03-22 17:15:00', '2026-03-22 18:41:21'),
  ('fin.events_hourly', '2026-03-22 19:00:00', '2026-03-22 19:09:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/shipments_weekday1', '2026-03-22 19:15:00', '2026-03-22 19:28:28'),
  ('ana.fraud_hourly', '2026-03-22 19:45:00', '2026-03-22 20:01:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-22 20:00:00', '2026-03-22 20:10:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-22 21:15:00', '2026-03-22 21:16:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-22 19:15:00', '2026-03-22 21:31:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 21:45:00', '2026-03-22 22:01:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-22 22:00:00', '2026-03-22 22:14:56'),
  ('ana.fraud_hourly', '2026-03-22 22:45:00', '2026-03-22 23:10:58'),
  ('ana.renewals_four_hourly', '2026-03-22 23:30:00', '2026-03-22 23:39:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-22 23:00:00', '2026-03-22 23:43:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 23:45:00', '2026-03-23 00:02:14'),
  ('fin.events_hourly', '2026-03-23 00:00:00', '2026-03-23 00:20:53'),
  ('lake.audits_twice_monthly', '2026-03-23 00:00:00', '2026-03-23 00:47:49'),
  ('ana.fraud_hourly', '2026-03-23 00:45:00', '2026-03-23 00:56:28'),
  ('fin.inventory_daily', '2026-03-23 01:10:00', '2026-03-23 01:32:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-22 23:45:00', '2026-03-23 01:34:23'),
  ('ana.fraud_hourly', '2026-03-23 01:45:00', '2026-03-23 02:16:09'),
  ('fin.exports_daily', '2026-03-23 01:10:00', '2026-03-23 02:24:44'),
  ('fin.renewals_daily', '2026-03-23 01:20:00', '2026-03-23 02:31:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-23 02:45:00', '2026-03-23 02:56:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-23 03:00:00', '2026-03-23 03:02:03'),
  ('fin.ads_weekday', '2026-03-23 02:10:00', '2026-03-23 03:16:11'),
  ('fin.events_hourly', '2026-03-23 02:00:00', '2026-03-23 03:44:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 03:45:00', '2026-03-23 04:02:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-23 03:30:00', '2026-03-23 04:30:35'),
  ('fin.catalog_weekday', '2026-03-23 04:45:00', '2026-03-23 04:55:56'),
  ('fin.events_hourly', '2026-03-23 05:00:00', '2026-03-23 05:09:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-23 05:15:00', '2026-03-23 05:18:16'),
  ('ana.fraud_hourly', '2026-03-23 04:45:00', '2026-03-23 05:18:39'),
  ('ana.fraud_hourly', '2026-03-23 05:45:00', '2026-03-23 06:02:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-23 06:00:00', '2026-03-23 06:08:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 06:45:00', '2026-03-23 07:05:23'),
  ('lake.events_weekday', '2026-03-23 06:30:00', '2026-03-23 07:11:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-23 07:20:00', '2026-03-23 07:22:30'),
  ('fin.events_hourly', '2026-03-23 07:00:00', '2026-03-23 07:26:52'),
  ('fin.ads_weekday', '2026-03-23 02:10:00', '2026-03-23 07:27:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-23 06:15:00', '2026-03-23 07:32:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 07:45:00', '2026-03-23 07:58:53'),
  ('ana.renewals_four_hourly', '2026-03-23 07:30:00', '2026-03-23 08:12:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-23 08:00:00', '2026-03-23 08:24:01'),
  ('ana.fraud-hourly', '2026-03-23 08:45:00', '2026-03-23 09:07:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-23 09:15:00', '2026-03-23 09:17:29'),
  ('fin.events_hourly', '2026-03-23 09:00:00', '2026-03-23 09:17:52'),
  ('ana.fraud_hourly', '2026-03-23 09:45:00', '2026-03-23 10:02:06'),
  ('leg.exports_daily', '2026-03-23 09:05:00', '2026-03-23 10:28:08'),
  ('ana.renewals_four_hourly', '2026-03-23 11:30:00', '2026-03-23 11:38:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 11:45:00', '2026-03-23 12:15:22'),
  ('ana.fraud_hourly', '2026-03-23 10:45:00', '2026-03-23 12:19:16'),
  ('fin.events_hourly', '2026-03-23 12:00:00', '2026-03-23 12:40:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-23 13:00:00', '2026-03-23 13:10:17'),
  ('leg.tickets-four-hourly', '2026-03-23 13:15:00', '2026-03-23 13:16:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-23 13:00:00', '2026-03-23 13:27:55'),
  ('fin.budgets_daily1', '2026-03-23 13:00:00', '2026-03-23 13:58:08'),
  ('ANA.FRAUD_HOURLY', '2026-03-23 13:45:00', '2026-03-23 14:12:32'),
  ('fin.events_hourly', '2026-03-23 14:00:00', '2026-03-23 14:25:08'),
  ('lake.accounts_weekday', '2026-03-23 15:15:00', '2026-03-23 15:16:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 14:45:00', '2026-03-23 15:17:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-23 16:00:00', '2026-03-23 16:14:24'),
  ('ana.fraud_hourly', '2026-03-23 15:45:00', '2026-03-23 17:12:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-23 17:15:00', '2026-03-23 17:16:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-03-23 17:05:00', '2026-03-23 17:31:11'),
  ('fin.events_hourly', '2026-03-23 18:00:00', '2026-03-23 18:16:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 18:45:00', '2026-03-23 18:59:09'),
  ('leg.search_daily', '2026-03-23 18:15:00', '2026-03-23 19:09:56'),
  ('fin.events_hourly', '2026-03-23 19:00:00', '2026-03-23 19:10:05'),
  ('ana.churn_daily', '2026-03-23 13:30:00', '2026-03-23 19:23:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 19:45:00', '2026-03-23 20:06:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-23 20:00:00', '2026-03-23 20:17:58'),
  ('ana.fraud_hourly', '2026-03-23 20:45:00', '2026-03-23 21:01:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-23 21:00:00', '2026-03-23 21:23:00'),
  ('fin/refunds_daily', '2026-03-23 21:20:00', '2026-03-23 21:59:54'),
  ('ana.fraud_hourly', '2026-03-23 21:45:00', '2026-03-23 22:13:00'),
  ('fin.events_hourly', '2026-03-23 22:00:00', '2026-03-23 22:25:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 22:45:00', '2026-03-23 22:55:59'),
  ('fin.events_hourly', '2026-03-23 23:00:00', '2026-03-23 23:09:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-23 20:45:00', '2026-03-23 23:34:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-23 23:30:00', '2026-03-24 00:44:21'),
  ('ana.fraud_hourly', '2026-03-24 00:45:00', '2026-03-24 01:12:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-24 01:15:00', '2026-03-24 01:17:28'),
  ('fin.events_hourly', '2026-03-24 01:00:00', '2026-03-24 01:20:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-24 01:10:00', '2026-03-24 01:39:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-24 01:10:00', '2026-03-24 02:40:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-24 03:00:00', '2026-03-24 03:01:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-24 02:00:00', '2026-03-24 03:55:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-24 03:00:00', '2026-03-24 03:57:58'),
  ('fin.events_hourly', '2026-03-24 04:00:00', '2026-03-24 04:19:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-03-24 01:10:00', '2026-03-24 04:42:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.catalog_weekday', '2026-03-24 04:45:00', '2026-03-24 04:53:10'),
  ('ana.fraud_hourly', '2026-03-24 03:45:00', '2026-03-24 04:56:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-24 05:00:00', '2026-03-24 05:26:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.limits_weekday', '2026-03-24 04:20:00', '2026-03-24 05:26:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-24 04:45:00', '2026-03-24 05:55:00'),
  ('fin.events_hourly', '2026-03-24 06:00:00', '2026-03-24 06:24:18'),
  ('lake.events_weekday', '2026-03-24 06:30:00', '2026-03-24 06:49:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-24 05:45:00', '2026-03-24 06:52:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-24 06:45:00', '2026-03-24 07:05:09'),
  ('lake.search_weekday', '2026-03-24 06:15:00', '2026-03-24 07:11:28'),
  ('lake.clicks_daily', '2026-03-24 07:20:00', '2026-03-24 07:22:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-24 07:00:00', '2026-03-24 07:24:20'),
  ('lake/alerts_daily', '2026-03-24 03:00:00', '2026-03-24 07:39:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-24 08:00:00', '2026-03-24 08:21:41'),
  ('ana.fraud_hourly', '2026-03-24 08:45:00', '2026-03-24 09:13:18'),
  ('leg.tickets_four_hourly', '2026-03-24 09:15:00', '2026-03-24 09:17:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-24 09:00:00', '2026-03-24 09:17:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.exports-daily', '2026-03-24 09:05:00', '2026-03-24 09:58:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-24 09:45:00', '2026-03-24 10:10:20'),
  ('fin.events-hourly', '2026-03-24 11:00:00', '2026-03-24 11:24:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-24 11:30:00', '2026-03-24 12:17:51'),
  ('fin.events_hourly', '2026-03-24 12:00:00', '2026-03-24 12:25:46'),
  ('ana.fraud_hourly', '2026-03-24 12:45:00', '2026-03-24 13:02:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-24 11:45:00', '2026-03-24 13:06:50'),
  ('fin.events_hourly', '2026-03-24 13:00:00', '2026-03-24 13:10:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-24 12:20:00', '2026-03-24 13:14:29'),
  ('leg.tickets_four_hourly', '2026-03-24 13:15:00', '2026-03-24 13:16:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-03-24 13:00:00', '2026-03-24 13:31:13'),
  ('fin.events_hourly', '2026-03-24 14:00:00', '2026-03-24 14:09:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-24 13:45:00', '2026-03-24 14:20:05'),
  ('fin.events_hourly', '2026-03-24 13:00:00', '2026-03-24 14:56:58'),
  ('ana.fraud_hourly', '2026-03-24 14:45:00', '2026-03-24 15:03:56'),
  ('fin.events_hourly', '2026-03-24 15:00:00', '2026-03-24 15:31:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-24 15:45:00', '2026-03-24 15:56:45'),
  ('ana.renewals_four_hourly', '2026-03-24 15:30:00', '2026-03-24 16:39:14'),
  ('ana.fraud_hourly', '2026-03-24 16:45:00', '2026-03-24 17:13:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-24 17:15:00', '2026-03-24 17:18:21'),
  ('LEG.FORECAST_DAILY', '2026-03-24 17:05:00', '2026-03-24 17:23:53'),
  ('ana.fraud_hourly', '2026-03-24 12:45:00', '2026-03-24 17:41:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/budgets_daily1', '2026-03-24 13:00:00', '2026-03-24 17:48:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-24 17:45:00', '2026-03-24 18:18:52'),
  ('fin.events_hourly', '2026-03-24 18:00:00', '2026-03-24 18:24:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-24 16:00:00', '2026-03-24 18:30:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-24 19:00:00', '2026-03-24 19:17:12'),
  ('ana.shipments_weekday1', '2026-03-24 19:15:00', '2026-03-24 19:17:37'),
  ('leg.search_daily', '2026-03-24 18:15:00', '2026-03-24 19:29:59'),
  ('ana.fraud_hourly', '2026-03-24 18:45:00', '2026-03-24 19:43:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-24 19:30:00', '2026-03-24 19:44:03'),
  ('fin.events_hourly', '2026-03-24 18:00:00', '2026-03-24 19:47:48'),
  ('ana.fraud-hourly', '2026-03-24 19:45:00', '2026-03-24 20:05:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-24 20:00:00', '2026-03-24 20:17:33'),
  ('ana.fraud_hourly', '2026-03-24 18:45:00', '2026-03-24 20:27:34'),
  ('fin.events_hourly', '2026-03-24 21:00:00', '2026-03-24 21:17:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-24 21:20:00', '2026-03-24 23:07:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-24 21:45:00', '2026-03-24 23:10:24'),
  ('ana.fraud_hourly', '2026-03-24 22:45:00', '2026-03-24 23:34:16'),
  ('ana.fraud_hourly', '2026-03-24 23:45:00', '2026-03-24 23:55:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-25 00:00:00', '2026-03-25 00:20:00'),
  ('ana.renewals_four_hourly', '2026-03-24 23:30:00', '2026-03-25 00:20:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 00:45:00', '2026-03-25 01:04:03'),
  ('leg.tickets_four_hourly', '2026-03-25 01:15:00', '2026-03-25 01:17:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-25 01:00:00', '2026-03-25 01:53:52'),
  ('fin.refunds_daily', '2026-03-24 21:20:00', '2026-03-25 02:10:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 01:45:00', '2026-03-25 02:10:27'),
  ('fin/ads_weekday', '2026-03-25 02:10:00', '2026-03-25 03:03:57'),
  ('ana.fraud_hourly', '2026-03-25 02:45:00', '2026-03-25 03:17:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-25 03:00:00', '2026-03-25 03:24:03'),
  ('fin.events_hourly', '2026-03-25 02:00:00', '2026-03-25 03:35:07'),
  ('ana.fraud-hourly', '2026-03-25 03:45:00', '2026-03-25 04:00:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-25 04:00:00', '2026-03-25 04:14:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-25 03:00:00', '2026-03-25 04:25:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-25 02:45:00', '2026-03-25 04:38:25'),
  ('ana.limits_weekday', '2026-03-25 04:20:00', '2026-03-25 05:00:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-25 04:45:00', '2026-03-25 05:04:48'),
  ('fin.catalog_weekday', '2026-03-25 04:45:00', '2026-03-25 05:11:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-25 05:15:00', '2026-03-25 05:16:52'),
  ('fin.events_hourly', '2026-03-25 05:00:00', '2026-03-25 05:19:43'),
  ('ana.fraud_hourly', '2026-03-25 05:45:00', '2026-03-25 05:55:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-25 06:00:00', '2026-03-25 06:13:33'),
  ('fin.events_hourly', '2026-03-25 07:00:00', '2026-03-25 07:17:18'),
  ('lake.search_weekday', '2026-03-25 06:15:00', '2026-03-25 07:37:25'),
  ('ana.renewals_four_hourly', '2026-03-25 07:30:00', '2026-03-25 07:38:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 06:45:00', '2026-03-25 08:09:04'),
  ('ana.fraud_hourly', '2026-03-25 07:45:00', '2026-03-25 08:22:35'),
  ('fin.events-hourly', '2026-03-25 08:00:00', '2026-03-25 08:23:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets-four-hourly', '2026-03-25 09:15:00', '2026-03-25 09:18:09'),
  ('ana.fraud-hourly', '2026-03-25 08:45:00', '2026-03-25 09:27:37'),
  ('leg.exports_daily', '2026-03-25 09:05:00', '2026-03-25 09:37:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 09:45:00', '2026-03-25 09:56:01'),
  ('fin/events_hourly', '2026-03-25 09:00:00', '2026-03-25 10:00:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 10:45:00', '2026-03-25 10:59:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-25 11:00:00', '2026-03-25 11:07:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-25 12:00:00', '2026-03-25 12:07:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 09:45:00', '2026-03-25 12:32:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-25 11:45:00', '2026-03-25 12:47:00'),
  ('ana.fraud_hourly', '2026-03-25 12:45:00', '2026-03-25 13:05:09'),
  ('leg.tickets_four_hourly', '2026-03-25 13:15:00', '2026-03-25 13:17:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-25 13:00:00', '2026-03-25 13:23:26'),
  ('leg.quotes_daily', '2026-03-25 13:00:00', '2026-03-25 13:25:37'),
  ('leg.tickets_weekday', '2026-03-25 12:20:00', '2026-03-25 13:26:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 13:45:00', '2026-03-25 13:55:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.BUDGETS_DAILY1', '2026-03-25 13:00:00', '2026-03-25 14:17:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-03-25 13:30:00', '2026-03-25 14:34:51'),
  ('fin.events_hourly', '2026-03-25 14:00:00', '2026-03-25 14:42:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-25 11:00:00', '2026-03-25 14:54:23'),
  ('lake.accounts_weekday', '2026-03-25 15:15:00', '2026-03-25 15:15:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-25 13:00:00', '2026-03-25 15:32:44'),
  ('FIN.EVENTS_HOURLY', '2026-03-25 16:00:00', '2026-03-25 16:09:24'),
  ('ana.fraud_hourly', '2026-03-25 15:45:00', '2026-03-25 16:13:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-25 15:30:00', '2026-03-25 16:19:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-03-25 17:00:00', '2026-03-25 17:07:47'),
  ('leg.tickets_four_hourly', '2026-03-25 17:15:00', '2026-03-25 17:18:07'),
  ('ana.fraud_hourly', '2026-03-25 16:45:00', '2026-03-25 17:18:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-03-25 17:05:00', '2026-03-25 17:20:12'),
  ('ana.fraud_hourly', '2026-03-25 17:45:00', '2026-03-25 18:05:11'),
  ('leg.search_daily', '2026-03-25 18:15:00', '2026-03-25 18:45:56'),
  ('ana.fraud_hourly', '2026-03-25 18:45:00', '2026-03-25 18:55:56'),
  ('ana.fraud_hourly', '2026-03-25 16:45:00', '2026-03-25 19:22:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-25 19:15:00', '2026-03-25 19:45:00'),
  ('fin/events_hourly', '2026-03-25 20:00:00', '2026-03-25 20:10:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 20:45:00', '2026-03-25 21:08:26'),
  ('ana.fraud_hourly', '2026-03-25 19:45:00', '2026-03-25 21:16:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('fin.events_hourly', '2026-03-25 21:00:00', '2026-03-25 21:20:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-03-25 21:20:00', '2026-03-25 21:38:53'),
  ('leg.search_daily', '2026-03-25 18:15:00', '2026-03-25 22:04:20'),
  ('fin.events_hourly', '2026-03-25 22:00:00', '2026-03-25 22:08:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-25 21:45:00', '2026-03-25 22:19:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-03-25 17:05:00', '2026-03-25 22:21:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-25 22:45:00', '2026-03-25 23:03:20'),
  ('fin.events_hourly', '2026-03-25 23:00:00', '2026-03-25 23:08:32'),
  ('ana.renewals_four_hourly', '2026-03-25 23:30:00', '2026-03-25 23:45:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 00:00:00', '2026-03-26 00:10:38'),
  ('ana/fraud_hourly', '2026-03-25 23:45:00', '2026-03-26 00:16:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 01:00:00', '2026-03-26 01:17:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-26 01:15:00', '2026-03-26 01:17:57'),
  ('ana.fraud_hourly', '2026-03-26 00:45:00', '2026-03-26 01:19:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-26 01:10:00', '2026-03-26 01:42:53'),
  ('fin.exports_daily', '2026-03-26 01:10:00', '2026-03-26 01:50:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts-daily', '2026-03-26 03:00:00', '2026-03-26 03:03:06'),
  ('ana.fraud_hourly', '2026-03-26 02:45:00', '2026-03-26 03:14:31'),
  ('ana.fraud_hourly', '2026-03-26 01:45:00', '2026-03-26 03:22:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 03:00:00', '2026-03-26 03:36:12'),
  ('ana.renewals_four_hourly', '2026-03-26 03:30:00', '2026-03-26 03:46:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-26 02:10:00', '2026-03-26 03:50:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 02:00:00', '2026-03-26 03:53:44'),
  ('ana.fraud-hourly', '2026-03-26 03:45:00', '2026-03-26 04:13:29'),
  ('fin.events_hourly', '2026-03-26 04:00:00', '2026-03-26 04:24:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-26 04:45:00', '2026-03-26 04:59:10'),
  ('ana.limits_weekday', '2026-03-26 04:20:00', '2026-03-26 05:09:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-26 05:15:00', '2026-03-26 05:15:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 05:00:00', '2026-03-26 05:25:46'),
  ('fin.catalog_weekday', '2026-03-26 04:45:00', '2026-03-26 05:40:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 06:00:00', '2026-03-26 06:12:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 05:45:00', '2026-03-26 06:13:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-26 04:00:00', '2026-03-26 07:07:22'),
  ('fin.events_hourly', '2026-03-26 07:00:00', '2026-03-26 07:11:44'),
  ('fin.events_hourly', '2026-03-26 05:00:00', '2026-03-26 07:31:05'),
  ('ana.renewals_four_hourly', '2026-03-26 07:30:00', '2026-03-26 07:52:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 04:45:00', '2026-03-26 08:16:20'),
  ('fin.events_hourly', '2026-03-26 08:00:00', '2026-03-26 08:25:48'),
  ('ana.fraud_hourly', '2026-03-26 07:45:00', '2026-03-26 08:27:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 08:45:00', '2026-03-26 09:05:49');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-26 09:15:00', '2026-03-26 09:17:35'),
  ('fin.events_hourly', '2026-03-26 09:00:00', '2026-03-26 09:26:59'),
  ('lake.search_weekday', '2026-03-26 06:15:00', '2026-03-26 09:30:02'),
  ('ana.fraud_hourly', '2026-03-26 09:45:00', '2026-03-26 10:18:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-26 09:15:00', '2026-03-26 10:37:46'),
  ('fin.events-hourly', '2026-03-26 10:00:00', '2026-03-26 10:40:07'),
  ('leg.exports-daily', '2026-03-26 09:05:00', '2026-03-26 10:43:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 10:45:00', '2026-03-26 10:57:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 11:00:00', '2026-03-26 11:23:28'),
  ('ana.fraud_hourly', '2026-03-26 11:45:00', '2026-03-26 12:05:08'),
  ('fin.events_hourly', '2026-03-26 12:00:00', '2026-03-26 12:12:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-26 13:15:00', '2026-03-26 13:18:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 13:00:00', '2026-03-26 13:22:10'),
  ('leg.quotes_daily', '2026-03-26 13:00:00', '2026-03-26 13:36:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/budgets_daily1', '2026-03-26 13:00:00', '2026-03-26 13:40:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-26 12:20:00', '2026-03-26 13:44:27'),
  ('ana.fraud-hourly', '2026-03-26 13:45:00', '2026-03-26 14:06:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-03-26 13:30:00', '2026-03-26 14:19:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-26 14:00:00', '2026-03-26 14:22:22'),
  ('fin.events_hourly', '2026-03-26 15:00:00', '2026-03-26 15:16:55'),
  ('lake/accounts_weekday', '2026-03-26 15:15:00', '2026-03-26 15:17:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 16:00:00', '2026-03-26 16:23:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 16:45:00', '2026-03-26 17:02:07'),
  ('fin.events_hourly', '2026-03-26 17:00:00', '2026-03-26 17:17:34'),
  ('ana.fraud_hourly', '2026-03-26 15:45:00', '2026-03-26 17:17:58'),
  ('leg.tickets_four_hourly', '2026-03-26 17:15:00', '2026-03-26 17:47:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 17:45:00', '2026-03-26 18:06:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 18:00:00', '2026-03-26 18:08:37'),
  ('LEG.QUOTES_DAILY', '2026-03-26 13:00:00', '2026-03-26 18:28:12'),
  ('fin.events_hourly', '2026-03-26 19:00:00', '2026-03-26 19:14:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-26 19:15:00', '2026-03-26 19:16:36'),
  ('ana.renewals_four_hourly', '2026-03-26 19:30:00', '2026-03-26 19:39:33'),
  ('ana.fraud_hourly', '2026-03-26 18:45:00', '2026-03-26 19:41:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 20:00:00', '2026-03-26 20:09:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-26 15:45:00', '2026-03-26 20:57:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 19:45:00', '2026-03-26 21:00:12'),
  ('leg.tickets_four_hourly', '2026-03-26 21:15:00', '2026-03-26 21:15:50'),
  ('ana.fraud_hourly', '2026-03-26 20:45:00', '2026-03-26 21:16:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 21:00:00', '2026-03-26 21:17:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 22:45:00', '2026-03-26 23:12:19'),
  ('ana.fraud_hourly', '2026-03-26 21:45:00', '2026-03-26 23:18:40'),
  ('fin.events_hourly', '2026-03-26 23:00:00', '2026-03-26 23:21:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-26 23:30:00', '2026-03-26 23:45:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-26 23:45:00', '2026-03-27 00:12:29'),
  ('fin.events_hourly', '2026-03-27 00:00:00', '2026-03-27 00:26:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-26 22:00:00', '2026-03-27 00:30:00'),
  ('ana.fraud_hourly', '2026-03-27 00:45:00', '2026-03-27 01:00:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-27 01:15:00', '2026-03-27 01:17:10'),
  ('fin.events_hourly', '2026-03-27 01:00:00', '2026-03-27 01:29:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.renewals_daily', '2026-03-27 01:20:00', '2026-03-27 02:06:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.INVENTORY_DAILY', '2026-03-27 01:10:00', '2026-03-27 02:22:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-27 02:00:00', '2026-03-27 02:35:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-27 03:00:00', '2026-03-27 03:02:12'),
  ('ana.renewals-four-hourly', '2026-03-27 03:30:00', '2026-03-27 03:53:13'),
  ('fin.events_hourly', '2026-03-27 03:00:00', '2026-03-27 04:00:00'),
  ('ana.fraud_hourly', '2026-03-27 02:45:00', '2026-03-27 04:04:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-27 03:00:00', '2026-03-27 04:37:46'),
  ('fin.exports_daily', '2026-03-27 01:10:00', '2026-03-27 04:53:53'),
  ('ana.fraud_hourly', '2026-03-27 04:45:00', '2026-03-27 05:14:59'),
  ('leg.tickets_four_hourly', '2026-03-27 05:15:00', '2026-03-27 05:17:34'),
  ('ana.fraud_hourly', '2026-03-26 23:45:00', '2026-03-27 05:31:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-27 05:00:00', '2026-03-27 05:38:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-27 05:45:00', '2026-03-27 06:01:30'),
  ('fin.events-hourly', '2026-03-27 06:00:00', '2026-03-27 06:17:04'),
  ('ana.limits_weekday', '2026-03-27 04:20:00', '2026-03-27 06:53:09'),
  ('lake.events_weekday', '2026-03-27 06:30:00', '2026-03-27 07:00:20'),
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-27 07:30:00', '2026-03-27 07:38:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-27 08:00:00', '2026-03-27 08:56:16'),
  ('ana.fraud_hourly', '2026-03-27 07:45:00', '2026-03-27 09:09:26'),
  ('leg.tickets_four_hourly', '2026-03-27 09:15:00', '2026-03-27 09:16:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-27 09:00:00', '2026-03-27 09:18:38'),
  ('fin.events_hourly', '2026-03-27 10:00:00', '2026-03-27 10:14:41'),
  ('leg.exports_daily', '2026-03-27 09:05:00', '2026-03-27 10:36:04'),
  ('ana.fraud_hourly', '2026-03-27 10:45:00', '2026-03-27 11:07:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/renewals_four_hourly', '2026-03-27 11:30:00', '2026-03-27 11:44:08'),
  ('fin.events_hourly', '2026-03-27 11:00:00', '2026-03-27 12:00:00'),
  ('ana.fraud_hourly', '2026-03-27 11:45:00', '2026-03-27 12:00:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-27 12:00:00', '2026-03-27 12:10:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-27 12:20:00', '2026-03-27 12:56:00'),
  ('ana.fraud_hourly', '2026-03-27 12:45:00', '2026-03-27 13:09:25'),
  ('fin.events_hourly', '2026-03-27 13:00:00', '2026-03-27 13:15:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-27 13:15:00', '2026-03-27 13:17:43'),
  ('ana.search_weekly', '2026-03-27 13:05:00', '2026-03-27 13:23:03'),
  ('ana.fraud-hourly', '2026-03-27 13:45:00', '2026-03-27 14:32:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-27 15:00:00', '2026-03-27 15:13:57'),
  ('lake.accounts_weekday', '2026-03-27 15:15:00', '2026-03-27 15:16:23'),
  ('ana.fraud_hourly', '2026-03-27 14:45:00', '2026-03-27 15:21:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-27 15:30:00', '2026-03-27 15:49:23'),
  ('ana.churn_daily', '2026-03-27 13:30:00', '2026-03-27 15:51:07'),
  ('fin.events_hourly', '2026-03-27 16:00:00', '2026-03-27 16:09:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-27 15:45:00', '2026-03-27 16:15:41'),
  ('ana.fraud_hourly', '2026-03-27 16:45:00', '2026-03-27 16:56:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.FRAUD_HOURLY', '2026-03-27 12:45:00', '2026-03-27 16:58:13'),
  ('fin.events_hourly', '2026-03-27 18:00:00', '2026-03-27 18:06:43'),
  ('LAKE.ACCOUNTS_WEEKDAY', '2026-03-27 15:15:00', '2026-03-27 18:19:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-27 17:45:00', '2026-03-27 18:25:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-27 15:30:00', '2026-03-27 18:26:50'),
  ('ana.fraud_hourly', '2026-03-27 18:45:00', '2026-03-27 19:11:07');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search-daily', '2026-03-27 18:15:00', '2026-03-27 19:25:22'),
  ('fin.events_hourly', '2026-03-27 19:00:00', '2026-03-27 19:26:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/renewals_four_hourly', '2026-03-27 19:30:00', '2026-03-27 19:39:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-27 19:45:00', '2026-03-27 20:10:08'),
  ('fin.events_hourly', '2026-03-27 20:00:00', '2026-03-27 20:52:10'),
  ('ana.fraud_hourly', '2026-03-27 20:45:00', '2026-03-27 20:53:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-27 21:00:00', '2026-03-27 21:12:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-27 21:15:00', '2026-03-27 21:16:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-27 19:30:00', '2026-03-27 21:52:26'),
  ('fin.refunds_daily', '2026-03-27 21:20:00', '2026-03-27 21:53:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-27 21:45:00', '2026-03-27 22:11:34'),
  ('fin.events_hourly', '2026-03-27 22:00:00', '2026-03-27 22:23:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-27 22:45:00', '2026-03-27 23:09:02'),
  ('fin.events_hourly', '2026-03-27 23:00:00', '2026-03-27 23:11:27'),
  ('ana.renewals_four_hourly', '2026-03-27 23:30:00', '2026-03-27 23:38:43'),
  ('ana.fraud_hourly', '2026-03-27 23:45:00', '2026-03-27 23:55:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-28 00:00:00', '2026-03-28 00:34:37'),
  ('ana.fraud_hourly', '2026-03-28 00:45:00', '2026-03-28 01:19:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-28 01:00:00', '2026-03-28 01:19:23'),
  ('FIN.INVENTORY_DAILY', '2026-03-28 01:10:00', '2026-03-28 01:49:43'),
  ('ana.fraud_hourly', '2026-03-28 01:45:00', '2026-03-28 02:06:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-28 02:45:00', '2026-03-28 03:07:37'),
  ('lake.alerts_daily', '2026-03-28 03:00:00', '2026-03-28 03:10:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-28 02:00:00', '2026-03-28 03:22:11'),
  ('fin.events_hourly', '2026-03-28 03:00:00', '2026-03-28 03:25:01'),
  ('ana.renewals_four_hourly', '2026-03-28 03:30:00', '2026-03-28 03:40:05'),
  ('fin.events_hourly', '2026-03-28 04:00:00', '2026-03-28 04:16:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-28 01:45:00', '2026-03-28 04:29:38'),
  ('ana.fraud_hourly', '2026-03-28 04:45:00', '2026-03-28 05:10:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-28 05:15:00', '2026-03-28 05:17:10'),
  ('fin/events_hourly', '2026-03-28 06:00:00', '2026-03-28 06:27:08'),
  ('ana.fraud_hourly', '2026-03-28 06:45:00', '2026-03-28 06:54:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('fin.events_hourly', '2026-03-28 07:00:00', '2026-03-28 07:12:36'),
  ('ana.renewals_four_hourly', '2026-03-28 07:30:00', '2026-03-28 07:53:14'),
  ('ANA.FRAUD_HOURLY', '2026-03-28 07:45:00', '2026-03-28 08:01:25'),
  ('fin/events_hourly', '2026-03-28 08:00:00', '2026-03-28 08:11:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-28 08:45:00', '2026-03-28 08:56:56'),
  ('leg/tickets_four_hourly', '2026-03-28 09:15:00', '2026-03-28 09:17:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-28 09:00:00', '2026-03-28 09:49:55'),
  ('fin.events_hourly', '2026-03-28 10:00:00', '2026-03-28 10:20:23'),
  ('fin.events_hourly', '2026-03-28 10:00:00', '2026-03-28 11:10:04'),
  ('ana/fraud_hourly', '2026-03-28 10:45:00', '2026-03-28 11:12:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-28 11:00:00', '2026-03-28 11:13:03'),
  ('ana.renewals_four_hourly', '2026-03-28 11:30:00', '2026-03-28 11:52:49'),
  ('ana.fraud_hourly', '2026-03-28 11:45:00', '2026-03-28 12:04:18'),
  ('fin/events_hourly', '2026-03-28 12:00:00', '2026-03-28 12:05:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-28 09:45:00', '2026-03-28 12:25:00'),
  ('leg.tickets_four_hourly', '2026-03-28 09:15:00', '2026-03-28 12:31:33'),
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('ana.fraud_hourly', '2026-03-28 12:45:00', '2026-03-28 13:16:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-28 13:15:00', '2026-03-28 13:16:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-28 13:00:00', '2026-03-28 13:47:14'),
  ('ana.fraud_hourly', '2026-03-28 13:45:00', '2026-03-28 14:16:32'),
  ('fin.events_hourly', '2026-03-28 14:00:00', '2026-03-28 14:19:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-28 15:00:00', '2026-03-28 15:09:40'),
  ('ana.renewals_four_hourly', '2026-03-28 15:30:00', '2026-03-28 15:54:04'),
  ('ANA.CHURN_DAILY', '2026-03-28 13:30:00', '2026-03-28 15:57:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-28 16:00:00', '2026-03-28 16:08:05'),
  ('ana.fraud_hourly', '2026-03-28 15:45:00', '2026-03-28 16:20:39'),
  ('ana/fraud_hourly', '2026-03-28 16:45:00', '2026-03-28 17:11:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-28 17:15:00', '2026-03-28 17:16:17'),
  ('leg.forecast_daily', '2026-03-28 17:05:00', '2026-03-28 17:17:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-28 17:00:00', '2026-03-28 17:23:48');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-28 18:00:00', '2026-03-28 18:14:00'),
  ('ana/fraud_hourly', '2026-03-28 16:45:00', '2026-03-28 18:38:21'),
  ('ana.fraud_hourly', '2026-03-28 18:45:00', '2026-03-28 19:12:04'),
  ('fin.events_hourly', '2026-03-28 19:00:00', '2026-03-28 19:17:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-28 19:30:00', '2026-03-28 19:37:54');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-03-28 18:15:00', '2026-03-28 19:51:57'),
  ('fin.events_hourly', '2026-03-28 20:00:00', '2026-03-28 20:15:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-28 19:45:00', '2026-03-28 20:20:34'),
  ('leg/tickets_four_hourly', '2026-03-28 21:15:00', '2026-03-28 21:18:05'),
  ('fin.refunds_daily', '2026-03-28 21:20:00', '2026-03-28 21:53:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-28 21:00:00', '2026-03-28 21:54:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-28 21:45:00', '2026-03-28 22:16:19'),
  ('ana.fraud_hourly', '2026-03-28 22:45:00', '2026-03-28 22:58:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-28 23:00:00', '2026-03-28 23:27:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-28 19:30:00', '2026-03-28 23:53:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-28 23:30:00', '2026-03-28 23:57:13'),
  ('ana.fraud_hourly', '2026-03-28 23:45:00', '2026-03-29 00:15:39'),
  ('fin.events-hourly', '2026-03-29 00:00:00', '2026-03-29 00:22:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-29 01:15:00', '2026-03-29 01:17:59'),
  ('fin.events-hourly', '2026-03-29 01:00:00', '2026-03-29 01:26:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-29 01:45:00', '2026-03-29 02:16:27'),
  ('fin.renewals_daily', '2026-03-29 01:00:00', '2026-03-29 02:33:37'),
  ('ana.fraud_hourly', '2026-03-29 02:45:00', '2026-03-29 02:58:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LAKE.ALERTS_DAILY', '2026-03-29 03:00:00', '2026-03-29 03:01:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 03:00:00', '2026-03-29 03:11:12'),
  ('ana.fraud-hourly', '2026-03-29 00:45:00', '2026-03-29 03:25:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-03-29 01:15:00', '2026-03-29 03:55:27'),
  ('ana.fraud_hourly', '2026-03-29 03:45:00', '2026-03-29 04:08:07'),
  ('fin.events_hourly', '2026-03-29 02:00:00', '2026-03-29 04:30:00'),
  ('ana.renewals_four_hourly', '2026-03-29 03:30:00', '2026-03-29 04:30:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 00:00:00', '2026-03-29 04:36:47'),
  ('FIN.EVENTS_HOURLY', '2026-03-29 05:00:00', '2026-03-29 05:10:16'),
  ('ANA.FRAUD_HOURLY', '2026-03-29 04:45:00', '2026-03-29 05:10:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-29 05:15:00', '2026-03-29 05:16:48'),
  ('fin.events_hourly', '2026-03-29 03:00:00', '2026-03-29 05:27:22'),
  ('ana.fraud_hourly', '2026-03-29 03:45:00', '2026-03-29 06:33:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 07:00:00', '2026-03-29 07:13:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-03-29 07:20:00', '2026-03-29 07:33:58'),
  ('ana.fraud_hourly', '2026-03-29 06:45:00', '2026-03-29 07:49:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 08:00:00', '2026-03-29 08:19:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 09:00:00', '2026-03-29 09:07:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-29 09:15:00', '2026-03-29 09:16:39');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-29 09:45:00', '2026-03-29 10:20:31'),
  ('ana.fraud_hourly', '2026-03-29 08:45:00', '2026-03-29 10:23:14'),
  ('leg.exports_daily', '2026-03-29 09:05:00', '2026-03-29 10:24:01'),
  ('FIN.EVENTS_HOURLY', '2026-03-29 10:00:00', '2026-03-29 10:27:20'),
  ('ana/fraud_hourly', '2026-03-29 10:45:00', '2026-03-29 11:55:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-29 11:45:00', '2026-03-29 12:05:01'),
  ('leg.quotes_daily', '2026-03-29 12:00:00', '2026-03-29 12:12:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-29 13:15:00', '2026-03-29 13:16:16');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-29 12:45:00', '2026-03-29 13:19:38'),
  ('fin.events_hourly', '2026-03-29 13:00:00', '2026-03-29 14:00:00'),
  ('fin.budgets_daily1', '2026-03-29 12:00:00', '2026-03-29 14:00:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-29 13:45:00', '2026-03-29 14:48:58'),
  ('ana.fraud_hourly', '2026-03-29 14:45:00', '2026-03-29 15:02:17'),
  ('fin.events_hourly', '2026-03-29 14:00:00', '2026-03-29 15:02:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 15:00:00', '2026-03-29 15:20:24'),
  ('ANA.RENEWALS_FOUR_HOURLY', '2026-03-29 15:30:00', '2026-03-29 15:56:51'),
  ('ana.churn_daily', '2026-03-29 13:30:00', '2026-03-29 16:12:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 16:00:00', '2026-03-29 16:14:26'),
  ('ana.fraud_hourly', '2026-03-29 15:45:00', '2026-03-29 17:06:27'),
  ('ana.fraud_hourly', '2026-03-29 16:45:00', '2026-03-29 17:17:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-03-29 17:05:00', '2026-03-29 17:20:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets-four-hourly', '2026-03-29 13:15:00', '2026-03-29 17:27:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 17:00:00', '2026-03-29 17:28:53'),
  ('leg/forecast_daily', '2026-03-29 17:05:00', '2026-03-29 17:52:29'),
  ('fin.events_hourly', '2026-03-29 15:00:00', '2026-03-29 18:30:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-29 17:45:00', '2026-03-29 18:32:53'),
  ('fin.events_hourly', '2026-03-29 19:00:00', '2026-03-29 19:11:23'),
  ('ana.shipments_weekday1', '2026-03-29 19:15:00', '2026-03-29 19:17:08'),
  ('leg.search_daily', '2026-03-29 18:15:00', '2026-03-29 19:20:23'),
  ('ana.fraud_hourly', '2026-03-29 18:45:00', '2026-03-29 19:36:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/renewals_four_hourly', '2026-03-29 19:30:00', '2026-03-29 19:44:44'),
  ('ana.fraud_hourly', '2026-03-29 19:45:00', '2026-03-29 20:11:50'),
  ('fin.refunds_daily', '2026-03-29 20:20:00', '2026-03-29 20:46:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-29 20:45:00', '2026-03-29 20:56:42'),
  ('ana.shipments_weekday1', '2026-03-29 19:15:00', '2026-03-29 21:03:26'),
  ('fin.events_hourly', '2026-03-29 21:00:00', '2026-03-29 21:09:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 20:00:00', '2026-03-29 21:13:00'),
  ('leg.tickets_four_hourly', '2026-03-29 21:15:00', '2026-03-29 21:22:34'),
  ('ana.fraud_hourly', '2026-03-29 18:45:00', '2026-03-29 21:45:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-29 21:45:00', '2026-03-29 21:54:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 22:00:00', '2026-03-29 22:11:55'),
  ('ana.fraud_hourly', '2026-03-29 20:45:00', '2026-03-29 22:44:48'),
  ('ana.fraud_hourly', '2026-03-29 22:45:00', '2026-03-29 23:07:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-29 23:00:00', '2026-03-29 23:34:47'),
  ('ana.fraud-hourly', '2026-03-29 23:45:00', '2026-03-30 00:02:48'),
  ('fin.events_hourly', '2026-03-30 00:00:00', '2026-03-30 00:14:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/renewals_daily', '2026-03-30 00:20:00', '2026-03-30 00:41:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports-daily', '2026-03-30 00:10:00', '2026-03-30 00:42:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-03-30 00:10:00', '2026-03-30 00:45:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets-four-hourly', '2026-03-30 01:15:00', '2026-03-30 01:17:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 01:45:00', '2026-03-30 01:55:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.audits_twice_monthly', '2026-03-30 00:00:00', '2026-03-30 02:07:45'),
  ('FIN.EVENTS_HOURLY', '2026-03-30 02:00:00', '2026-03-30 02:11:00'),
  ('fin.events_hourly', '2026-03-30 01:00:00', '2026-03-30 02:32:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-30 03:00:00', '2026-03-30 03:02:34'),
  ('ana.fraud_hourly', '2026-03-30 02:45:00', '2026-03-30 03:11:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-30 03:00:00', '2026-03-30 03:18:31');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads_weekday', '2026-03-30 01:10:00', '2026-03-30 03:26:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 03:45:00', '2026-03-30 03:53:02'),
  ('ana.renewals_four_hourly', '2026-03-30 03:30:00', '2026-03-30 03:55:44'),
  ('fin.catalog_weekday', '2026-03-30 03:45:00', '2026-03-30 03:59:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 04:45:00', '2026-03-30 05:00:03'),
  ('leg.tickets_four_hourly', '2026-03-30 05:15:00', '2026-03-30 05:16:56'),
  ('fin.events_hourly', '2026-03-30 05:00:00', '2026-03-30 06:00:22'),
  ('ana.fraud_hourly', '2026-03-30 05:45:00', '2026-03-30 06:09:08');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-30 06:00:00', '2026-03-30 06:14:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('ana.limits_weekday', '2026-03-30 04:20:00', '2026-03-30 06:16:19'),
  ('ana.fraud_hourly', '2026-03-30 06:45:00', '2026-03-30 07:04:46'),
  ('fin.events_hourly', '2026-03-30 07:00:00', '2026-03-30 07:10:37'),
  ('lake.clicks_daily', '2026-03-30 07:20:00', '2026-03-30 07:21:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-03-30 06:30:00', '2026-03-30 07:22:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-30 06:15:00', '2026-03-30 07:41:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-03-30 04:45:00', '2026-03-30 07:45:34'),
  ('ana.renewals_four_hourly', '2026-03-30 07:30:00', '2026-03-30 08:04:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-03-30 07:45:00', '2026-03-30 08:11:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 06:45:00', '2026-03-30 08:58:50'),
  ('FIN.EVENTS_HOURLY', '2026-03-30 09:00:00', '2026-03-30 09:22:00'),
  ('ana.fraud_hourly', '2026-03-30 09:45:00', '2026-03-30 10:16:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-30 07:00:00', '2026-03-30 10:29:14');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-30 11:00:00', '2026-03-30 11:22:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-30 12:00:00', '2026-03-30 12:09:43'),
  ('ana.fraud_hourly', '2026-03-30 11:45:00', '2026-03-30 12:26:37'),
  ('leg.exports_daily', '2026-03-30 09:05:00', '2026-03-30 12:29:19');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 12:45:00', '2026-03-30 12:52:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-03-30 12:00:00', '2026-03-30 13:01:33'),
  ('leg.tickets_four_hourly', '2026-03-30 13:15:00', '2026-03-30 13:18:54'),
  ('leg.tickets_weekday', '2026-03-30 12:20:00', '2026-03-30 13:23:04'),
  ('fin.events_hourly', '2026-03-30 12:00:00', '2026-03-30 13:51:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 13:45:00', '2026-03-30 14:00:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 14:45:00', '2026-03-30 15:12:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts_weekday', '2026-03-30 15:15:00', '2026-03-30 15:18:14'),
  ('fin.events_hourly', '2026-03-30 15:00:00', '2026-03-30 15:25:55'),
  ('ana/renewals_four_hourly', '2026-03-30 15:30:00', '2026-03-30 15:43:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 15:45:00', '2026-03-30 16:00:26'),
  ('ANA.FRAUD_HOURLY', '2026-03-30 16:45:00', '2026-03-30 16:53:59');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-30 17:00:00', '2026-03-30 17:10:47'),
  ('FIN.EVENTS_HOURLY', '2026-03-30 16:00:00', '2026-03-30 17:12:23');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-30 17:15:00', '2026-03-30 17:17:56'),
  ('ana.fraud_hourly', '2026-03-30 17:45:00', '2026-03-30 18:02:21');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.forecast_daily', '2026-03-30 17:05:00', '2026-03-30 18:16:50');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-30 18:00:00', '2026-03-30 18:52:34'),
  ('fin.events_hourly', '2026-03-30 19:00:00', '2026-03-30 19:12:12'),
  ('ana.fraud_hourly', '2026-03-30 18:45:00', '2026-03-30 19:17:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-30 19:15:00', '2026-03-30 19:17:25');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/renewals_four_hourly', '2026-03-30 19:30:00', '2026-03-30 19:45:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 19:45:00', '2026-03-30 20:04:43');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-30 20:45:00', '2026-03-30 21:09:07'),
  ('fin.events_hourly', '2026-03-30 20:00:00', '2026-03-30 21:09:51'),
  ('leg.tickets_four_hourly', '2026-03-30 21:15:00', '2026-03-30 21:15:57'),
  ('ana.fraud_hourly', '2026-03-30 21:45:00', '2026-03-30 22:01:15'),
  ('fin.events-hourly', '2026-03-30 16:00:00', '2026-03-30 22:05:46');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-30 22:00:00', '2026-03-30 22:07:08'),
  ('ana.fraud_hourly', '2026-03-30 22:45:00', '2026-03-30 23:17:30'),
  ('fin.events_hourly', '2026-03-30 23:00:00', '2026-03-30 23:23:13'),
  ('ana.fraud_hourly', '2026-03-30 23:45:00', '2026-03-31 00:02:09');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-03-31 00:00:00', '2026-03-31 00:13:51'),
  ('fin.inventory_daily', '2026-03-31 00:10:00', '2026-03-31 00:35:58'),
  ('ana.renewals_four_hourly', '2026-03-30 23:30:00', '2026-03-31 00:41:16'),
  ('ana.fraud_hourly', '2026-03-31 00:45:00', '2026-03-31 01:04:43'),
  ('fin/renewals_daily', '2026-03-31 00:20:00', '2026-03-31 01:04:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.ads-weekday', '2026-03-31 01:10:00', '2026-03-31 01:25:07'),
  ('fin.exports_daily', '2026-03-31 00:10:00', '2026-03-31 01:40:20'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-03-30 21:15:00', '2026-03-31 01:58:45'),
  ('ana.fraud_hourly', '2026-03-31 01:45:00', '2026-03-31 01:59:09'),
  ('fin.events_hourly', '2026-03-31 02:00:00', '2026-03-31 02:48:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-30 23:30:00', '2026-03-31 02:51:04'),
  ('FIN.EVENTS_HOURLY', '2026-03-31 01:00:00', '2026-03-31 03:01:30');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.alerts_daily', '2026-03-31 03:00:00', '2026-03-31 03:03:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-31 02:45:00', '2026-03-31 03:04:50'),
  ('fin.events_hourly', '2026-03-31 03:00:00', '2026-03-31 03:24:27');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-31 03:30:00', '2026-03-31 03:55:20'),
  ('fin.catalog_weekday', '2026-03-31 03:45:00', '2026-03-31 04:24:33');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-03-31 04:00:00', '2026-03-31 04:28:02'),
  ('ana.limits_weekday', '2026-03-31 04:20:00', '2026-03-31 04:49:47'),
  ('ana.fraud_hourly', '2026-03-31 04:45:00', '2026-03-31 05:08:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-31 05:15:00', '2026-03-31 05:16:58'),
  ('ana.fraud_hourly', '2026-03-31 05:45:00', '2026-03-31 06:07:35'),
  ('lake.events-weekday', '2026-03-31 06:30:00', '2026-03-31 07:08:04'),
  ('lake.clicks_daily', '2026-03-31 07:20:00', '2026-03-31 07:23:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.search_weekday', '2026-03-31 06:15:00', '2026-03-31 07:39:00'),
  ('FIN.EVENTS_HOURLY', '2026-03-31 07:00:00', '2026-03-31 07:43:01'),
  ('ana.renewals_four_hourly', '2026-03-31 07:30:00', '2026-03-31 08:27:41'),
  ('ana.fraud_hourly', '2026-03-31 07:45:00', '2026-03-31 09:01:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-31 08:00:00', '2026-03-31 09:11:28'),
  ('fin.events_hourly', '2026-03-31 09:00:00', '2026-03-31 09:11:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-31 08:45:00', '2026-03-31 09:16:09'),
  ('leg.tickets_four_hourly', '2026-03-31 09:15:00', '2026-03-31 09:16:31'),
  ('ana.fraud_hourly', '2026-03-31 09:45:00', '2026-03-31 10:00:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-31 10:45:00', '2026-03-31 11:17:54'),
  ('fin.events_hourly', '2026-03-31 11:00:00', '2026-03-31 11:21:11'),
  ('ana.renewals_four_hourly', '2026-03-31 11:30:00', '2026-03-31 11:49:26'),
  ('FIN.EVENTS_HOURLY', '2026-03-31 12:00:00', '2026-03-31 12:15:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-03-31 12:20:00', '2026-03-31 13:00:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-31 12:45:00', '2026-03-31 13:00:31'),
  ('ANA.FRAUD_HOURLY', '2026-03-31 13:45:00', '2026-03-31 14:17:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn-daily', '2026-03-31 13:30:00', '2026-03-31 14:34:22'),
  ('ANA.FRAUD_HOURLY', '2026-03-31 14:45:00', '2026-03-31 15:11:10'),
  ('lake.broken', 'not a time', '2026-03-04 05:00:00'),
  ('lake.accounts_weekday', '2026-03-31 15:15:00', '2026-03-31 15:17:38'),
  ('ana.renewals_four_hourly', '2026-03-31 15:30:00', '2026-03-31 15:42:56');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-31 15:45:00', '2026-03-31 16:10:48'),
  ('fin/budgets_daily1', '2026-03-31 12:00:00', '2026-03-31 16:16:17'),
  ('ana.fraud_hourly', '2026-03-31 16:45:00', '2026-03-31 17:07:37');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-31 17:00:00', '2026-03-31 17:14:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-31 17:15:00', '2026-03-31 17:16:08'),
  ('leg.forecast_daily', '2026-03-31 17:05:00', '2026-03-31 17:29:59'),
  ('ana.fraud_hourly', '2026-03-31 17:45:00', '2026-03-31 18:00:17'),
  ('fin.events_hourly', '2026-03-31 18:00:00', '2026-03-31 18:26:40');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.shipments_weekday1', '2026-03-31 19:15:00', '2026-03-31 19:16:29'),
  ('ana.fraud_hourly', '2026-03-31 18:45:00', '2026-03-31 19:16:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-03-31 18:15:00', '2026-03-31 19:42:02'),
  ('ana.renewals_four_hourly', '2026-03-31 19:30:00', '2026-03-31 19:42:30'),
  ('fin.events_hourly', '2026-03-31 20:00:00', '2026-03-31 20:14:07'),
  ('ana/fraud_hourly', '2026-03-31 19:45:00', '2026-03-31 20:41:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-03-31 20:45:00', '2026-03-31 21:12:11'),
  ('fin.events_hourly', '2026-03-31 21:00:00', '2026-03-31 21:17:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-03-31 21:15:00', '2026-03-31 21:17:47'),
  ('ana.fraud-hourly', '2026-03-31 21:45:00', '2026-03-31 22:02:27'),
  ('fin.refunds-daily', '2026-03-31 20:20:00', '2026-03-31 22:09:47'),
  ('fin.events_hourly', '2026-03-31 22:00:00', '2026-03-31 22:19:32');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-03-31 23:00:00', '2026-03-31 23:11:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-03-31 23:30:00', '2026-03-31 23:48:22');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-01 00:00:00', '2026-04-01 00:14:13'),
  ('fin.inventory_daily', '2026-04-01 00:10:00', '2026-04-01 00:24:22'),
  ('ana.fraud_hourly', '2026-03-31 23:45:00', '2026-04-01 00:34:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.audits_twice_monthly', '2026-04-01 00:00:00', '2026-04-01 00:37:50'),
  ('fin.renewals_daily', '2026-04-01 00:20:00', '2026-04-01 00:56:27'),
  ('leg.tickets_four_hourly', '2026-04-01 01:15:00', '2026-04-01 01:17:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-04-01 00:45:00', '2026-04-01 01:32:09'),
  ('fin.exports_daily', '2026-04-01 00:10:00', '2026-04-01 01:43:24'),
  ('ana.fraud_hourly', '2026-04-01 01:45:00', '2026-04-01 02:20:33'),
  ('fin.events_hourly', '2026-04-01 02:00:00', '2026-04-01 02:49:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-01 02:45:00', '2026-04-01 02:58:22'),
  ('fin.events_hourly', '2026-04-01 03:00:00', '2026-04-01 03:26:29'),
  ('fin.events-hourly', '2026-04-01 01:00:00', '2026-04-01 03:44:28'),
  ('ana.renewals-four-hourly', '2026-04-01 03:30:00', '2026-04-01 04:01:38');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.catalog_weekday', '2026-04-01 03:45:00', '2026-04-01 04:04:00'),
  ('fin.events-hourly', '2026-04-01 04:00:00', '2026-04-01 04:24:46'),
  ('fin.events_hourly', '2026-04-01 05:00:00', '2026-04-01 05:16:55');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg/tickets_four_hourly', '2026-04-01 05:15:00', '2026-04-01 05:17:50'),
  ('ana.fraud_hourly', '2026-04-01 04:45:00', '2026-04-01 05:46:55'),
  ('ana.fraud_hourly', '2026-04-01 05:45:00', '2026-04-01 06:17:09'),
  ('lake.search_weekday', '2026-04-01 06:15:00', '2026-04-01 07:00:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-01 06:45:00', '2026-04-01 07:20:31'),
  ('fin.events_hourly', '2026-04-01 07:00:00', '2026-04-01 07:23:29'),
  ('ana.renewals_four_hourly', '2026-04-01 07:30:00', '2026-04-01 07:44:35'),
  ('lake.events_weekday', '2026-04-01 06:30:00', '2026-04-01 08:14:14'),
  ('fin.events-hourly', '2026-04-01 08:00:00', '2026-04-01 08:23:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-04-01 09:15:00', '2026-04-01 09:17:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-01 09:00:00', '2026-04-01 09:18:14'),
  ('ana.fraud_hourly', '2026-04-01 07:45:00', '2026-04-01 09:22:28'),
  ('ana.fraud_hourly', '2026-04-01 10:45:00', '2026-04-01 11:16:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/renewals_four_hourly', '2026-04-01 11:30:00', '2026-04-01 11:37:51'),
  ('fin.events_hourly', '2026-04-01 11:00:00', '2026-04-01 12:13:05'),
  ('ana.fraud_hourly', '2026-04-01 11:45:00', '2026-04-01 12:14:35'),
  ('leg.quotes_daily', '2026-04-01 12:00:00', '2026-04-01 12:15:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('FIN.EVENTS_HOURLY', '2026-04-01 12:00:00', '2026-04-01 12:16:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_weekday', '2026-04-01 12:20:00', '2026-04-01 12:48:59'),
  ('fin.events-hourly', '2026-04-01 13:00:00', '2026-04-01 13:10:20'),
  ('leg.tickets-four-hourly', '2026-04-01 13:15:00', '2026-04-01 13:17:04'),
  ('ana.fraud_hourly', '2026-04-01 13:45:00', '2026-04-01 14:02:41');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-01 12:45:00', '2026-04-01 14:12:44');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-01 14:00:00', '2026-04-01 14:19:11');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.accounts-weekday', '2026-04-01 15:15:00', '2026-04-01 15:16:38'),
  ('ana.fraud_hourly', '2026-04-01 14:45:00', '2026-04-01 15:23:20'),
  ('fin.events_hourly', '2026-04-01 15:00:00', '2026-04-01 15:24:04');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-04-01 15:30:00', '2026-04-01 15:44:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-01 16:00:00', '2026-04-01 16:16:43'),
  ('ana.fraud_hourly', '2026-04-01 15:45:00', '2026-04-01 16:17:03'),
  ('ana.churn_daily', '2026-04-01 13:30:00', '2026-04-01 16:36:44'),
  ('ana.fraud_hourly', '2026-04-01 16:45:00', '2026-04-01 17:11:17');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-04-01 17:15:00', '2026-04-01 17:16:48'),
  ('leg.forecast_daily', '2026-04-01 17:05:00', '2026-04-01 17:28:52'),
  ('fin/events_hourly', '2026-04-01 17:00:00', '2026-04-01 17:40:08'),
  ('ana.fraud_hourly', '2026-04-01 17:45:00', '2026-04-01 17:59:13');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin/events_hourly', '2026-04-01 18:00:00', '2026-04-01 18:23:34'),
  ('leg.search_daily', '2026-04-01 18:15:00', '2026-04-01 18:48:36'),
  ('ana.shipments_weekday1', '2026-04-01 19:15:00', '2026-04-01 19:16:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-01 18:45:00', '2026-04-01 19:17:42'),
  ('fin.events_hourly', '2026-04-01 19:00:00', '2026-04-01 19:23:11'),
  ('ana/renewals_four_hourly', '2026-04-01 19:30:00', '2026-04-01 19:40:08'),
  ('ana.fraud-hourly', '2026-04-01 19:45:00', '2026-04-01 20:01:10');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-01 20:00:00', '2026-04-01 20:13:19'),
  ('ana.fraud_hourly', '2026-04-01 20:45:00', '2026-04-01 21:14:51'),
  ('LEG.TICKETS_FOUR_HOURLY', '2026-04-01 21:15:00', '2026-04-01 21:16:40'),
  ('fin.events_hourly', '2026-04-01 21:00:00', '2026-04-01 21:20:06');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-01 21:45:00', '2026-04-01 22:16:23'),
  ('fin.events-hourly', '2026-04-01 22:00:00', '2026-04-01 22:18:07'),
  ('fin/events_hourly', '2026-04-01 23:00:00', '2026-04-01 23:16:40'),
  ('ana.fraud_hourly', '2026-04-01 23:45:00', '2026-04-02 00:03:48'),
  ('fin.events_hourly', '2026-04-02 00:00:00', '2026-04-02 00:26:51');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.inventory_daily', '2026-04-02 00:10:00', '2026-04-02 00:33:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.exports_daily', '2026-04-02 00:10:00', '2026-04-02 00:42:06'),
  ('leg.tickets_four_hourly', '2026-04-02 01:15:00', '2026-04-02 01:16:54'),
  ('fin.renewals_daily', '2026-04-02 00:20:00', '2026-04-02 01:19:40'),
  ('fin.ads_weekday', '2026-04-02 01:10:00', '2026-04-02 01:33:34');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-02 01:45:00', '2026-04-02 02:08:08'),
  ('lake.alerts_daily', '2026-04-02 03:00:00', '2026-04-02 03:01:36');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-04-02 02:45:00', '2026-04-02 03:10:17'),
  ('fin.catalog_weekday', '2026-04-02 03:45:00', '2026-04-02 03:51:53'),
  ('FIN.EVENTS_HOURLY', '2026-04-02 03:00:00', '2026-04-02 04:05:05'),
  ('fin.events_hourly', '2026-04-02 04:00:00', '2026-04-02 04:14:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.limits_weekday', '2026-04-02 04:20:00', '2026-04-02 04:56:45'),
  ('ana.fraud_hourly', '2026-04-02 04:45:00', '2026-04-02 05:01:52'),
  ('ana.fraud_hourly', '2026-04-02 03:45:00', '2026-04-02 05:05:28');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-02 05:00:00', '2026-04-02 05:10:53'),
  ('fin.events_hourly', '2026-04-02 06:00:00', '2026-04-02 06:10:35'),
  ('ana.fraud_hourly', '2026-04-02 05:45:00', '2026-04-02 06:48:26');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.events_weekday', '2026-04-02 06:30:00', '2026-04-02 07:05:35'),
  ('lake.search-weekday', '2026-04-02 06:15:00', '2026-04-02 07:11:01');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-02 06:45:00', '2026-04-02 07:18:02');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('lake.clicks_daily', '2026-04-02 07:20:00', '2026-04-02 07:21:25'),
  ('fin.events_hourly', '2026-04-02 07:00:00', '2026-04-02 07:21:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-04-02 07:30:00', '2026-04-02 07:55:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events-hourly', '2026-04-02 08:00:00', '2026-04-02 08:06:29');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-02 07:45:00', '2026-04-02 08:11:27'),
  ('ANA.FRAUD_HOURLY', '2026-04-02 08:45:00', '2026-04-02 09:00:52');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-02 09:00:00', '2026-04-02 09:08:25'),
  ('leg.tickets_four_hourly', '2026-04-02 09:15:00', '2026-04-02 09:16:35'),
  ('ana/fraud_hourly', '2026-04-02 09:45:00', '2026-04-02 10:04:42');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-02 10:00:00', '2026-04-02 10:09:20'),
  ('LEG.EXPORTS_DAILY', '2026-04-02 09:05:00', '2026-04-02 10:22:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-02 10:45:00', '2026-04-02 11:16:00'),
  ('fin.events_hourly', '2026-04-02 11:00:00', '2026-04-02 11:25:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud-hourly', '2026-04-02 11:45:00', '2026-04-02 12:07:15');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.quotes_daily', '2026-04-02 12:00:00', '2026-04-02 12:32:19'),
  ('ana.fraud_hourly', '2026-04-02 12:45:00', '2026-04-02 12:59:25'),
  ('leg.tickets_weekday', '2026-04-02 12:20:00', '2026-04-02 13:04:00');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.budgets_daily1', '2026-04-02 12:00:00', '2026-04-02 13:16:05');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.tickets_four_hourly', '2026-04-02 13:15:00', '2026-04-02 13:16:37'),
  ('fin.events-hourly', '2026-04-02 13:00:00', '2026-04-02 13:22:50'),
  ('ana.fraud_hourly', '2026-04-02 13:45:00', '2026-04-02 13:55:58');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.churn_daily', '2026-04-02 13:30:00', '2026-04-02 14:36:12');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-02 14:45:00', '2026-04-02 15:00:19'),
  ('ana.fraud_hourly', '2026-04-02 15:45:00', '2026-04-02 15:57:20'),
  ('fin.events_hourly', '2026-04-02 16:00:00', '2026-04-02 16:14:47');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-02 16:45:00', '2026-04-02 17:01:55'),
  ('ana.fraud_hourly', '2026-04-02 17:45:00', '2026-04-02 18:07:50'),
  ('fin.events_hourly', '2026-04-02 18:00:00', '2026-04-02 18:08:24');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('LEG.FORECAST_DAILY', '2026-04-02 17:05:00', '2026-04-02 18:14:18');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('leg.search_daily', '2026-04-02 18:15:00', '2026-04-02 18:51:04'),
  ('ana.fraud_hourly', '2026-04-02 18:45:00', '2026-04-02 19:03:35');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-04-02 19:30:00', '2026-04-02 19:38:34'),
  ('ana.fraud_hourly', '2026-04-02 19:45:00', '2026-04-02 19:55:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-02 20:00:00', '2026-04-02 20:26:45');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.refunds_daily', '2026-04-02 20:20:00', '2026-04-02 20:40:03');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.fraud_hourly', '2026-04-02 20:45:00', '2026-04-02 20:55:20');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('fin.events_hourly', '2026-04-02 21:00:00', '2026-04-02 21:25:54'),
  ('fin/events_hourly', '2026-04-02 22:00:00', '2026-04-02 22:09:53');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana/fraud_hourly', '2026-04-02 21:45:00', '2026-04-02 22:14:31'),
  ('ana.fraud_hourly', '2026-04-02 22:45:00', '2026-04-02 23:04:57');
INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES
  ('ana.renewals_four_hourly', '2026-04-02 23:30:00', '2026-04-02 23:40:31'),
  ('ana.fraud_hourly', '2026-04-02 23:45:00', '2026-04-03 00:21:37');
