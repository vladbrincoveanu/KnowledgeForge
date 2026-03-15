/** Authentication service using Auth0. */

const express = require('express');
const { auth, requiredScopes } = require('express-oauth2-jwt-bearer');
const { createClient } = require('redis');
require('dotenv').config();

const app = express();
app.use(express.json());

// Redis client for session storage
const redisClient = createClient({
  url: process.env.REDIS_URL || 'redis://localhost:6379',
});

redisClient.on('error', (err) => console.error('Redis error:', err));
redisClient.connect().catch(console.error);

// Auth0 JWT validation
const checkJwt = auth({
  audience: process.env.AUTH0_AUDIENCE || 'https://api.omnipay.com',
  issuerBaseURL: `https://${process.env.AUTH0_DOMAIN || 'example.auth0.com'}/`,
  tokenSigningAlg: 'RS256',
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'auth' });
});

app.get('/api/v1/auth/validate', checkJwt, (req, res) => {
  res.json({
    valid: true,
    user: req.auth.payload,
  });
});

app.post('/api/v1/auth/logout', async (req, res) => {
  const { token } = req.body;

  // Blacklist the token
  if (token) {
    await redisClient.set(`blacklist:${token}`, '1', { EX: 3600 });
  }

  res.json({ success: true });
});

app.get('/api/v1/auth/userinfo', checkJwt, (req, res) => {
  res.json({
    sub: req.auth.payload.sub,
    email: req.auth.payload.email,
    permissions: req.auth.payload.permissions || [],
  });
});

const PORT = process.env.PORT || 3002;
app.listen(PORT, () => {
  console.log(`Auth service listening on port ${PORT}`);
});

module.exports = app;
