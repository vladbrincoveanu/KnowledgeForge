/** Analytics service using Mixpanel. */

const express = require('express');
const Mixpanel = require('mixpanel');
const { Pool } = require('pg');
require('dotenv').config();

const app = express();
app.use(express.json());

const mixpanel = Mixpanel.init(process.env.MIXPANEL_TOKEN || 'your-token-here');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://localhost:5432/analytics',
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'analytics' });
});

app.post('/api/v1/track', (req, res) => {
  const { event, properties } = req.body;

  mixpanel.track(event, {
    ...properties,
    distinct_id: properties?.userId || 'anonymous',
    time: Date.now(),
  });

  res.json({ success: true });
});

app.get('/api/v1/analytics/events', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT event_name, COUNT(*) as count
      FROM events
      GROUP BY event_name
      ORDER BY count DESC
      LIMIT 100
    `);
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/v1/analytics/users', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT DISTINCT user_id, COUNT(*) as event_count
      FROM events
      GROUP BY user_id
      ORDER BY event_count DESC
      LIMIT 50
    `);
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Analytics service listening on port ${PORT}`);
});

module.exports = app;
