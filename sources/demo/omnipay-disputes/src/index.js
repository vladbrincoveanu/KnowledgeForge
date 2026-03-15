/** Dispute management service. */

const express = require('express');
const { Pool } = require('pg');
const { createClient } = require('redis');
require('dotenv').config();

const app = express();
app.use(express.json());

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://localhost:5432/disputes',
});

const redisClient = createClient({
  url: process.env.REDIS_URL || 'redis://localhost:6379',
});

redisClient.on('error', (err) => console.error('Redis error:', err));
redisClient.connect().catch(console.error);

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'disputes' });
});

app.post('/api/v1/disputes', async (req, res) => {
  const { transaction_id, reason, amount } = req.body;

  try {
    const result = await pool.query(
      `INSERT INTO disputes (transaction_id, reason, amount, status)
       VALUES ($1, $2, $3, 'pending')
       RETURNING id`,
      [transaction_id, reason, amount]
    );

    res.json({ dispute_id: result.rows[0].id, status: 'pending' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/v1/disputes/:id', async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT * FROM disputes WHERE id = $1',
      [req.params.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Dispute not found' });
    }

    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1/disputes/:id/respond', async (req, res) => {
  const { response, evidence } = req.body;

  try {
    await pool.query(
      `UPDATE disputes
       SET response = evidence, status = 'under_review', updated_at = NOW()
       WHERE id = $1`,
      [req.params.id, response, evidence]
    );

    res.json({ status: 'under_review' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

const PORT = process.env.PORT || 3003;
app.listen(PORT, () => {
  console.log(`Disputes service listening on port ${PORT}`);
});

module.exports = app;
